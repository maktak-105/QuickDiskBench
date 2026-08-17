#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <cstdint>
#include <vector>
#include <random>
#include <chrono>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <algorithm>

// Alignment requirements for Direct I/O (4096 bytes / 4KiB)
constexpr size_t SECTOR_SIZE = 4096;

enum TestType {
    TEST_SEQ_WRITE = 1,
    TEST_SEQ_READ = 2,
    TEST_RND_WRITE = 3,
    TEST_RND_READ = 4
};

typedef void (*ProgressCallback)(const char* test_name, double speed_mbs, double iops, double progress_percent);

// High-resolution timer helper
struct PerfTimer {
    LARGE_INTEGER freq;
    LARGE_INTEGER start;

    PerfTimer() {
        QueryPerformanceFrequency(&freq);
        QueryPerformanceCounter(&start);
    }

    void reset() {
        QueryPerformanceCounter(&start);
    }

    double elapsed_sec() const {
        LARGE_INTEGER now;
        QueryPerformanceCounter(&now);
        return static_cast<double>(now.QuadPart - start.QuadPart) / static_cast<double>(freq.QuadPart);
    }
};

// Aligned Memory Allocator
struct AlignedMemory {
    void* ptr = nullptr;
    size_t size = 0;

    AlignedMemory(size_t sz, unsigned char fill_val = 0xAA) : size(sz) {
        // VirtualAlloc returns memory page-aligned (4KiB), which satisfies Direct I/O
        ptr = VirtualAlloc(nullptr, sz, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        if (ptr && fill_val != 0) {
            std::memset(ptr, fill_val, sz);
        }
    }

    ~AlignedMemory() {
        if (ptr) {
            VirtualFree(ptr, 0, MEM_RELEASE);
            ptr = nullptr;
        }
    }

    AlignedMemory(const AlignedMemory&) = delete;
    AlignedMemory& operator=(const AlignedMemory&) = delete;
};

// Pre-allocate file on disk to prevent filesystem metadata expansion overhead
bool preallocate_file(HANDLE hFile, uint64_t file_size) {
    LARGE_INTEGER li;
    li.QuadPart = static_cast<LONGLONG>(file_size);
    if (!SetFilePointerEx(hFile, li, nullptr, FILE_BEGIN)) {
        return false;
    }
    if (!SetEndOfFile(hFile)) {
        return false;
    }
    // Rewind back to beginning
    li.QuadPart = 0;
    SetFilePointerEx(hFile, li, nullptr, FILE_BEGIN);
    return true;
}

extern "C" {

__declspec(dllexport) int run_benchmark_test(
    const wchar_t* filepath,
    int test_type,
    uint64_t file_size_bytes,
    int block_size_bytes,
    int queue_depth,
    int write_through,
    ProgressCallback callback,
    const int* stop_flag,
    double* out_speed_mbs,
    double* out_iops
) {
    if (!filepath || file_size_bytes < SECTOR_SIZE || block_size_bytes < SECTOR_SIZE) {
        return -1;
    }

    queue_depth = std::max(1, std::min(queue_depth, 64));
    
    // Configure Win32 Direct I/O flags
    DWORD flags = FILE_ATTRIBUTE_NORMAL | FILE_FLAG_NO_BUFFERING | FILE_FLAG_OVERLAPPED;
    if (write_through) {
        flags |= FILE_FLAG_WRITE_THROUGH;
    }

    bool is_write = (test_type == TEST_SEQ_WRITE || test_type == TEST_RND_WRITE);
    bool is_random = (test_type == TEST_RND_WRITE || test_type == TEST_RND_READ);

    DWORD desired_access = is_write ? (GENERIC_READ | GENERIC_WRITE) : GENERIC_READ;
    DWORD creation_disposition = is_write ? CREATE_ALWAYS : OPEN_ALWAYS;

    HANDLE hFile = CreateFileW(
        filepath,
        desired_access,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr,
        creation_disposition,
        flags,
        nullptr
    );

    if (hFile == INVALID_HANDLE_VALUE) {
        return static_cast<int>(GetLastError());
    }

    // Pre-allocate file space for write tests
    if (is_write) {
        preallocate_file(hFile, file_size_bytes);
    }

    // Prepare I/O buffers and Overlapped structures for Queue Depth
    std::vector<AlignedMemory*> buffers(queue_depth);
    std::vector<OVERLAPPED> overlapped(queue_depth);
    std::vector<HANDLE> events(queue_depth);
    std::vector<uint64_t> current_offsets(queue_depth, 0);
    std::vector<bool> active_slots(queue_depth, false);

    for (int i = 0; i < queue_depth; ++i) {
        buffers[i] = new AlignedMemory(block_size_bytes, static_cast<unsigned char>((i * 17 + 0xA5) & 0xFF));
        events[i] = CreateEventW(nullptr, TRUE, FALSE, nullptr);
        std::memset(&overlapped[i], 0, sizeof(OVERLAPPED));
        overlapped[i].hEvent = events[i];
    }

    uint64_t total_blocks = file_size_bytes / block_size_bytes;
    if (total_blocks == 0) total_blocks = 1;

    // For random test, define total operations (e.g. 10000 ops or based on file size)
    uint64_t total_ops = is_random ? std::min<uint64_t>(10000, std::max<uint64_t>(2000, total_blocks * 2)) : total_blocks;
    
    // Random generator setup
    std::mt19937_64 rng(1337);
    std::uniform_int_distribution<uint64_t> dist(0, total_blocks - 1);

    uint64_t issued_ops = 0;
    uint64_t completed_ops = 0;
    uint64_t total_bytes_transferred = 0;

    auto get_next_offset = [&](uint64_t op_index) -> uint64_t {
        if (is_random) {
            return dist(rng) * block_size_bytes;
        } else {
            return (op_index % total_blocks) * block_size_bytes;
        }
    };

    const char* test_name_str = "";
    if (test_type == TEST_SEQ_WRITE) test_name_str = "SEQ Write";
    else if (test_type == TEST_SEQ_READ) test_name_str = "SEQ Read";
    else if (test_type == TEST_RND_WRITE) test_name_str = "RND Write";
    else if (test_type == TEST_RND_READ) test_name_str = "RND Read";

    PerfTimer timer;
    double last_callback_time = 0;
    const double max_duration_sec = is_random ? 3.0 : 30.0;

    // Initial dispatch up to Queue Depth
    for (int i = 0; i < queue_depth && issued_ops < total_ops; ++i) {
        uint64_t offset = get_next_offset(issued_ops);
        current_offsets[i] = offset;
        overlapped[i].Offset = static_cast<DWORD>(offset & 0xFFFFFFFF);
        overlapped[i].OffsetHigh = static_cast<DWORD>((offset >> 32) & 0xFFFFFFFF);
        ResetEvent(events[i]);

        BOOL res = FALSE;
        if (is_write) {
            res = WriteFile(hFile, buffers[i]->ptr, block_size_bytes, nullptr, &overlapped[i]);
        } else {
            res = ReadFile(hFile, buffers[i]->ptr, block_size_bytes, nullptr, &overlapped[i]);
        }

        if (res || GetLastError() == ERROR_IO_PENDING) {
            active_slots[i] = true;
            issued_ops++;
        }
    }

    // Main completion loop
    while (completed_ops < total_ops) {
        if (stop_flag && *stop_flag != 0) {
            break;
        }

        double elapsed = timer.elapsed_sec();
        if (elapsed >= max_duration_sec) {
            break;
        }

        // Wait for any active I/O slot to complete
        DWORD wait_result = WaitForMultipleObjects(queue_depth, events.data(), FALSE, 50);
        if (wait_result >= WAIT_OBJECT_0 && wait_result < WAIT_OBJECT_0 + queue_depth) {
            int slot = wait_result - WAIT_OBJECT_0;
            DWORD bytes_transferred = 0;
            if (GetOverlappedResult(hFile, &overlapped[slot], &bytes_transferred, FALSE)) {
                completed_ops++;
                total_bytes_transferred += bytes_transferred;
                active_slots[slot] = false;
                ResetEvent(events[slot]);

                // Issue next operation on this slot if remaining
                if (issued_ops < total_ops && !(stop_flag && *stop_flag != 0) && (timer.elapsed_sec() < max_duration_sec)) {
                    uint64_t offset = get_next_offset(issued_ops);
                    current_offsets[slot] = offset;
                    overlapped[slot].Offset = static_cast<DWORD>(offset & 0xFFFFFFFF);
                    overlapped[slot].OffsetHigh = static_cast<DWORD>((offset >> 32) & 0xFFFFFFFF);

                    BOOL next_res = FALSE;
                    if (is_write) {
                        next_res = WriteFile(hFile, buffers[slot]->ptr, block_size_bytes, nullptr, &overlapped[slot]);
                    } else {
                        next_res = ReadFile(hFile, buffers[slot]->ptr, block_size_bytes, nullptr, &overlapped[slot]);
                    }

                    if (next_res || GetLastError() == ERROR_IO_PENDING) {
                        active_slots[slot] = true;
                        issued_ops++;
                    }
                }
            }
        }

        // Progress update throttle (every ~50ms)
        elapsed = timer.elapsed_sec();
        if (elapsed - last_callback_time >= 0.05 && elapsed > 0) {
            double current_speed = (total_bytes_transferred / (1024.0 * 1024.0)) / elapsed;
            double current_iops = completed_ops / elapsed;
            double pct = std::min(100.0, std::max(static_cast<double>(completed_ops) / total_ops, elapsed / max_duration_sec) * 100.0);

            if (callback) {
                callback(test_name_str, current_speed, current_iops, pct);
            }
            last_callback_time = elapsed;
        }
    }

    // Cancel pending I/O if stopped
    if (stop_flag && *stop_flag != 0) {
        CancelIo(hFile);
        for (int i = 0; i < queue_depth; ++i) {
            if (active_slots[i]) {
                DWORD bytes = 0;
                GetOverlappedResult(hFile, &overlapped[i], &bytes, TRUE);
            }
        }
    }

    double final_elapsed = timer.elapsed_sec();
    double final_speed = (final_elapsed > 0) ? ((total_bytes_transferred / (1024.0 * 1024.0)) / final_elapsed) : 0.0;
    double final_iops = (final_elapsed > 0) ? (completed_ops / final_elapsed) : 0.0;

    if (out_speed_mbs) *out_speed_mbs = final_speed;
    if (out_iops) *out_iops = final_iops;

    if (callback) {
        callback(test_name_str, final_speed, final_iops, 100.0);
    }

    // Cleanup resources
    for (int i = 0; i < queue_depth; ++i) {
        CloseHandle(events[i]);
        delete buffers[i];
    }

    CloseHandle(hFile);
    return 0;
}

} // extern "C"
