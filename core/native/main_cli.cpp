#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <iostream>
#include <vector>
#include <string>
#include <iomanip>
#include <cmath>
#include <numeric>
#include <algorithm>
#include <fstream>

// Import prototype from engine.cpp logic
enum TestType {
    TEST_SEQ_WRITE = 1,
    TEST_SEQ_READ = 2,
    TEST_RND_WRITE = 3,
    TEST_RND_READ = 4
};

typedef void (*ProgressCallback)(const char* test_name, double speed_mbs, double iops, double progress_percent);

extern "C" int run_benchmark_test(
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
);

extern "C" int set_benchmark_timeout_sec(double timeout_sec);

struct StatResult {
    double mean = 0.0;
    double std_dev = 0.0;
    double max_val = 0.0;
    double min_val = 0.0;
    double mean_iops = 0.0;
};

StatResult calc_stats(const std::vector<double>& vals, const std::vector<double>& iops_vals = {}) {
    StatResult r;
    if (vals.empty()) return r;
    double sum = std::accumulate(vals.begin(), vals.end(), 0.0);
    r.mean = sum / vals.size();
    r.max_val = *std::max_element(vals.begin(), vals.end());
    r.min_val = *std::min_element(vals.begin(), vals.end());

    if (vals.size() > 1) {
        double sq_sum = 0.0;
        for (double v : vals) sq_sum += (v - r.mean) * (v - r.mean);
        r.std_dev = std::sqrt(sq_sum / (vals.size() - 1));
    }

    if (!iops_vals.empty()) {
        double isum = std::accumulate(iops_vals.begin(), iops_vals.end(), 0.0);
        r.mean_iops = isum / iops_vals.size();
    }
    return r;
}

void print_header() {
    std::cout << "\033[1;36m============================================================\033[0m\n";
    std::cout << "\033[1;37m   QuickDiskBench Native C++ Benchmark Engine v2.1.1 (LLVM Clang)\033[0m\n";
    std::cout << "\033[1;36m============================================================\033[0m\n\n";
}

void progress_cb(const char* test_name, double speed_mbs, double iops, double pct) {
    std::cout << "\r \033[1;33m[" << std::setw(5) << std::fixed << std::setprecision(1) << pct << "%]\033[0m "
              << std::setw(18) << std::left << test_name 
              << " | Speed: \033[1;32m" << std::setw(8) << std::fixed << std::setprecision(2) << speed_mbs << " MB/s\033[0m"
              << " | IOPS: \033[1;35m" << std::setw(8) << std::fixed << std::setprecision(0) << iops << "\033[0m"
              << std::flush;
}

void print_help() {
    std::cout << "QuickDiskBench CLI - SSD/HDD benchmark\n\n"
              << "Usage: QuickDiskBench_cli.exe [options]\n\n"
              << "Options:\n"
              << "  -d, --drive PATH     Test location, e.g. C:\\ or D:\\ (default: C:\\)\n"
              << "  -s, --size MiB       Test file size, minimum 64 MiB (default: 256)\n"
              << "  -n, --passes N       Repeat each test 1-9 times (default: 1)\n"
              << "      --timeout SEC    Per-test timeout in seconds (default: 60; max: 3600)\n"
              << "      --raw            Write-through mode; reduces device write-cache effects\n"
              << "      --csv PATH       Write the result summary as UTF-8 CSV\n"
              << "  -h, --help           Show this help\n\n"
              << "Cache behavior: Windows OS cache is bypassed. Normal mode allows device cache;\n"
              << "--raw additionally requests write-through. The benchmark writes a temporary file.\n"
              << "If a test fails with Win32 error 1460, retry with a larger --timeout value.\n";
}

int main(int argc, char* argv[]) {
    // Enable ANSI Virtual Terminal processing in Windows Console
    HANDLE hOut = GetStdHandle(STD_OUTPUT_HANDLE);
    DWORD dwMode = 0;
    GetConsoleMode(hOut, &dwMode);
    SetConsoleMode(hOut, dwMode | ENABLE_VIRTUAL_TERMINAL_PROCESSING);

    print_header();

    std::wstring target_dir = L"C:\\";
    int size_mb = 256;
    int passes = 1;
    int write_through = 0;
    double timeout_sec = 60.0;
    std::string csv_path;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-h" || arg == "--help") { print_help(); return 0; }
        if ((arg == "-d" || arg == "--drive") && i + 1 < argc) {
            std::string d = argv[++i];
            target_dir = std::wstring(d.begin(), d.end());
            if (target_dir.back() != L'\\' && target_dir.back() != L'/') target_dir += L'\\';
        } else if ((arg == "-s" || arg == "--size") && i + 1 < argc) {
            size_mb = std::max(64, std::atoi(argv[++i]));
        } else if ((arg == "-n" || arg == "--passes") && i + 1 < argc) {
            passes = std::max(1, std::min(9, std::atoi(argv[++i])));
        } else if (arg == "--timeout" && i + 1 < argc) {
            timeout_sec = std::atof(argv[++i]);
        } else if (arg == "--raw") {
            write_through = 1;
        } else if (arg == "--csv" && i + 1 < argc) {
            csv_path = argv[++i];
        }
    }

    int timeout_result = set_benchmark_timeout_sec(timeout_sec);
    if (timeout_result != 0) {
        std::cerr << "Invalid --timeout value. Use a number from 1 to 3600 seconds.\n";
        return 2;
    }

    std::wstring test_file = target_dir + L"QuickDiskBench_cli_test.dat";
    HANDLE hCheck = CreateFileW(test_file.c_str(), GENERIC_READ | GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hCheck == INVALID_HANDLE_VALUE) {
        wchar_t temp_path[MAX_PATH];
        GetTempPathW(MAX_PATH, temp_path);
        test_file = std::wstring(temp_path) + L"QuickDiskBench_cli_test.dat";
    } else {
        CloseHandle(hCheck);
        DeleteFileW(test_file.c_str());
    }

    uint64_t file_size_bytes = static_cast<uint64_t>(size_mb) * 1024 * 1024;

    std::wcout << L"Target Drive : " << target_dir << L"\n";
    std::wcout << L"Test File    : " << test_file << L"\n";
    std::cout << "Test Size    : " << size_mb << " MiB\n";
    std::cout << "Test Passes  : " << passes << " Pass(es)\n";
    std::cout << "Timeout      : " << std::fixed << std::setprecision(0) << timeout_sec << " sec per test\n";
    std::cout << "Profile      : " << (write_through ? "Without Cache (Write-Through; device cache reduced)" : "With Cache (OS cache bypassed; device cache available)") << "\n\n";

    struct TestConfig {
        int type;
        int block_size;
        int q_depth;
        std::string name;
        bool has_iops;
    };

    std::vector<TestConfig> tests = {
        { TEST_SEQ_WRITE, 1024 * 1024, 8, "SEQ1M Q8T1 Write", false },
        { TEST_SEQ_READ,  1024 * 1024, 8, "SEQ1M Q8T1 Read",  false },
        { TEST_SEQ_WRITE, 1024 * 1024, 1, "SEQ1M Q1T1 Write", false },
        { TEST_SEQ_READ,  1024 * 1024, 1, "SEQ1M Q1T1 Read",  false },
        { TEST_RND_WRITE, 4096,       32, "RND4K Q32T1 Write", true },
        { TEST_RND_READ,  4096,       32, "RND4K Q32T1 Read",  true },
        { TEST_RND_WRITE, 4096,        1, "RND4K Q1T1 Write",  true },
        { TEST_RND_READ,  4096,        1, "RND4K Q1T1 Read",   true }
    };

    struct OutputMetric {
        std::string name;
        StatResult stats;
    };
    std::vector<OutputMetric> final_results;

    int stop_flag = 0;

    for (const auto& t : tests) {
        std::vector<double> speed_samples;
        std::vector<double> iops_samples;

        for (int p = 1; p <= passes; ++p) {
            std::string label = t.name + (passes > 1 ? (" (Pass " + std::to_string(p) + "/" + std::to_string(passes) + ")") : "");
            double speed = 0.0, iops = 0.0;
            
            int ret = run_benchmark_test(
                test_file.c_str(),
                t.type,
                file_size_bytes,
                t.block_size,
                t.q_depth,
                write_through,
                progress_cb,
                &stop_flag,
                &speed,
                &iops
            );

            if (ret == 0) {
                speed_samples.push_back(speed);
                iops_samples.push_back(iops);
            } else {
                std::cerr << "Benchmark failed for " << t.name << " (Win32 error " << ret << ")\n";
            }
        }
        std::cout << "\n";
        StatResult res = calc_stats(speed_samples, iops_samples);
        final_results.push_back({ t.name, res });
    }

    DeleteFileW(test_file.c_str());

    std::cout << "\n\033[1;36m============================================================\033[0m\n";
    std::cout << "\033[1;32m                   BENCHMARK RESULTS SUMMARY                \033[0m\n";
    std::cout << "\033[1;36m============================================================\033[0m\n";
    std::cout << "\033[1;37m" << std::setw(20) << std::left << "Test Name" 
              << std::setw(16) << std::right << "Mean Speed"
              << std::setw(14) << std::right << "StdDev"
              << std::setw(16) << std::right << "IOPS (Mean)"
              << "\033[0m\n";
    std::cout << "------------------------------------------------------------\n";

    for (const auto& r : final_results) {
        std::cout << std::setw(20) << std::left << r.name
                  << std::setw(10) << std::right << std::fixed << std::setprecision(2) << r.stats.mean << " MB/s"
                  << std::setw(8) << std::right << " +/-" << std::fixed << std::setprecision(2) << r.stats.std_dev
                  << std::setw(12) << std::right << std::fixed << std::setprecision(0) << r.stats.mean_iops << " IOPS\n";
    }
    std::cout << "------------------------------------------------------------\n\n";

    if (!csv_path.empty()) {
        std::ofstream csv(csv_path, std::ios::binary);
        if (!csv) { std::cerr << "Cannot write CSV: " << csv_path << "\n"; return 2; }
        csv << "test,mean_mbs,stddev_mbs,mean_iops\n";
        csv << std::fixed << std::setprecision(3);
        for (const auto& r : final_results)
            csv << '"' << r.name << "\"," << r.stats.mean << ',' << r.stats.std_dev << ',' << r.stats.mean_iops << "\n";
    }

    return 0;
}
