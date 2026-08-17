#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winioctl.h>
#include <commctrl.h>
#include <dwmapi.h>
#include <unknwn.h>
#include <WebView2.h>
#include <shellapi.h>

#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <sstream>
#include <iomanip>
#include <cmath>
#include <numeric>
#include <algorithm>
#include <thread>
#include <atomic>
#include <functional>
#include <cstdarg>
#include <chrono>

#define WM_POST_PROGRESS (WM_APP + 1)
#define IDI_ICON1 101

// Dynamic loader for WebView2Loader.dll
typedef HRESULT (STDAPICALLTYPE *CreateEnvFn)(
    PCWSTR browserExecutableFolder,
    PCWSTR userDataFolder,
    ICoreWebView2EnvironmentOptions* environmentOptions,
    ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler* environment_created_handler
);

// Typed COM Callbacks for WebView2 Handlers
class EnvCompletedHandler : public ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler {
    std::function<HRESULT(HRESULT, ICoreWebView2Environment*)> m_fn;
    std::atomic<ULONG> m_ref{ 1 };
public:
    EnvCompletedHandler(std::function<HRESULT(HRESULT, ICoreWebView2Environment*)> fn) : m_fn(fn) {}
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void** ppv) override {
        if (riid == IID_IUnknown || riid == IID_ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler) {
            *ppv = static_cast<ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler*>(this);
            AddRef();
            return S_OK;
        }
        *ppv = nullptr;
        return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return ++m_ref; }
    ULONG STDMETHODCALLTYPE Release() override {
        ULONG r = --m_ref;
        if (r == 0) delete this;
        return r;
    }
    HRESULT STDMETHODCALLTYPE Invoke(HRESULT result, ICoreWebView2Environment* env) override {
        return m_fn(result, env);
    }
};

class ControllerCompletedHandler : public ICoreWebView2CreateCoreWebView2ControllerCompletedHandler {
    std::function<HRESULT(HRESULT, ICoreWebView2Controller*)> m_fn;
    std::atomic<ULONG> m_ref{ 1 };
public:
    ControllerCompletedHandler(std::function<HRESULT(HRESULT, ICoreWebView2Controller*)> fn) : m_fn(fn) {}
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void** ppv) override {
        if (riid == IID_IUnknown || riid == IID_ICoreWebView2CreateCoreWebView2ControllerCompletedHandler) {
            *ppv = static_cast<ICoreWebView2CreateCoreWebView2ControllerCompletedHandler*>(this);
            AddRef();
            return S_OK;
        }
        *ppv = nullptr;
        return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return ++m_ref; }
    ULONG STDMETHODCALLTYPE Release() override {
        ULONG r = --m_ref;
        if (r == 0) delete this;
        return r;
    }
    HRESULT STDMETHODCALLTYPE Invoke(HRESULT result, ICoreWebView2Controller* controller) override {
        return m_fn(result, controller);
    }
};

class WebMessageReceivedHandler : public ICoreWebView2WebMessageReceivedEventHandler {
    std::function<HRESULT(ICoreWebView2*, ICoreWebView2WebMessageReceivedEventArgs*)> m_fn;
    std::atomic<ULONG> m_ref{ 1 };
public:
    WebMessageReceivedHandler(std::function<HRESULT(ICoreWebView2*, ICoreWebView2WebMessageReceivedEventArgs*)> fn) : m_fn(fn) {}
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void** ppv) override {
        if (riid == IID_IUnknown || riid == IID_ICoreWebView2WebMessageReceivedEventHandler) {
            *ppv = static_cast<ICoreWebView2WebMessageReceivedEventHandler*>(this);
            AddRef();
            return S_OK;
        }
        *ppv = nullptr;
        return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return ++m_ref; }
    ULONG STDMETHODCALLTYPE Release() override {
        ULONG r = --m_ref;
        if (r == 0) delete this;
        return r;
    }
    HRESULT STDMETHODCALLTYPE Invoke(ICoreWebView2* sender, ICoreWebView2WebMessageReceivedEventArgs* args) override {
        return m_fn(sender, args);
    }
};

// Benchmark engine prototype
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

// Global WebView2 pointers
HWND g_hWnd = NULL;
ICoreWebView2Controller* g_controller = NULL;
ICoreWebView2* g_webview = NULL;

std::atomic<bool> g_isRunning(false);
std::atomic<int> g_stopFlag(0);
std::thread g_workerThread;
std::wstring g_logPath;
std::chrono::steady_clock::time_point g_benchmarkStart;
bool g_benchmarkTimerStarted = false;

static void LOG(const char* fmt, ...);

// Drive structure
struct DriveInfo {
    std::wstring mountpoint;
    std::wstring label;
    std::wstring fstype;
    std::wstring manufacturer;
    std::wstring model;
    double total_gb;
    double free_gb;
    double used_gb;
    double percent;
};

std::wstring TrimStorageText(const char* text, size_t max_len) {
    if (!text || max_len == 0) return L"";
    size_t len = 0;
    while (len < max_len && text[len] != '\0') ++len;
    while (len > 0 && (text[len - 1] == ' ' || text[len - 1] == '\t')) --len;
    if (len == 0) return L"";

    int chars = MultiByteToWideChar(CP_ACP, 0, text, static_cast<int>(len), NULL, 0);
    if (chars <= 0) return L"";
    std::wstring result(chars, L'\0');
    MultiByteToWideChar(CP_ACP, 0, text, static_cast<int>(len), &result[0], chars);
    return result;
}

std::wstring StorageDescriptorText(const STORAGE_DEVICE_DESCRIPTOR* descriptor, DWORD buffer_size, DWORD offset) {
    if (!descriptor || offset == 0 || offset >= buffer_size) return L"";
    const char* text = reinterpret_cast<const char*>(descriptor) + offset;
    return TrimStorageText(text, buffer_size - offset);
}

bool GetPhysicalDriveIdentity(const std::wstring& mountpoint, std::wstring& manufacturer, std::wstring& model) {
    if (mountpoint.size() < 2 || mountpoint[1] != L':') return false;

    std::wstring volume_path = L"\\\\.\\" + mountpoint.substr(0, 2);
    HANDLE volume = CreateFileW(
        volume_path.c_str(), 0,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL, OPEN_EXISTING, 0, NULL
    );
    if (volume == INVALID_HANDLE_VALUE) return false;

    STORAGE_DEVICE_NUMBER device_number = {};
    DWORD returned = 0;
    BOOL ok = DeviceIoControl(
        volume, IOCTL_STORAGE_GET_DEVICE_NUMBER,
        NULL, 0, &device_number, sizeof(device_number), &returned, NULL
    );
    CloseHandle(volume);
    if (!ok) return false;

    std::wstring physical_path = L"\\\\.\\PhysicalDrive" + std::to_wstring(device_number.DeviceNumber);
    HANDLE physical = CreateFileW(
        physical_path.c_str(), 0,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL, OPEN_EXISTING, 0, NULL
    );
    if (physical == INVALID_HANDLE_VALUE) return false;

    STORAGE_PROPERTY_QUERY query = {};
    query.PropertyId = StorageDeviceProperty;
    query.QueryType = PropertyStandardQuery;
    BYTE buffer[4096] = {};
    ok = DeviceIoControl(
        physical, IOCTL_STORAGE_QUERY_PROPERTY,
        &query, sizeof(query), buffer, sizeof(buffer), &returned, NULL
    );
    CloseHandle(physical);
    if (!ok || returned < sizeof(STORAGE_DEVICE_DESCRIPTOR)) return false;

    const auto* descriptor = reinterpret_cast<const STORAGE_DEVICE_DESCRIPTOR*>(buffer);
    manufacturer = StorageDescriptorText(descriptor, returned, descriptor->VendorIdOffset);
    model = StorageDescriptorText(descriptor, returned, descriptor->ProductIdOffset);
    return !manufacturer.empty() || !model.empty();
}

std::wstring JsonEscape(const std::wstring& value) {
    std::wstring escaped;
    escaped.reserve(value.size());
    for (wchar_t ch : value) {
        switch (ch) {
            case L'\\': escaped += L"\\\\"; break;
            case L'"': escaped += L"\\\""; break;
            case L'\n': escaped += L"\\n"; break;
            case L'\r': escaped += L"\\r"; break;
            case L'\t': escaped += L"\\t"; break;
            default: escaped += ch; break;
        }
    }
    return escaped;
}

std::vector<DriveInfo> GetDrivesList() {
    std::vector<DriveInfo> list;
    wchar_t drive_strings[512] = {0};
    GetLogicalDriveStringsW(512, drive_strings);

    wchar_t* p = drive_strings;
    while (*p) {
        std::wstring drive = p;
        UINT type = GetDriveTypeW(drive.c_str());
        if (type == DRIVE_FIXED || type == DRIVE_REMOVABLE) {
            wchar_t vol_name[256] = {0};
            wchar_t fs_name[256] = {0};
            GetVolumeInformationW(drive.c_str(), vol_name, 256, NULL, NULL, NULL, fs_name, 256);

            ULARGE_INTEGER free_bytes, total_bytes;
            double free_gb = 0.0, total_gb = 0.0, used_gb = 0.0, pct = 0.0;
            if (GetDiskFreeSpaceExW(drive.c_str(), &free_bytes, &total_bytes, NULL)) {
                free_gb = free_bytes.QuadPart / (1024.0 * 1024.0 * 1024.0);
                total_gb = total_bytes.QuadPart / (1024.0 * 1024.0 * 1024.0);
                used_gb = total_gb - free_gb;
                if (total_gb > 0) pct = (used_gb / total_gb) * 100.0;
            }

            std::wstring label = vol_name;
            if (label.find(L"Google") == std::wstring::npos) {
                std::wstring manufacturer;
                std::wstring model;
                GetPhysicalDriveIdentity(drive, manufacturer, model);
                list.push_back({
                    drive,
                    label.empty() ? L"(No Label)" : label,
                    fs_name,
                    manufacturer,
                    model,
                    std::round(total_gb * 100.0) / 100.0,
                    std::round(free_gb * 100.0) / 100.0,
                    std::round(used_gb * 100.0) / 100.0,
                    std::round(pct * 10.0) / 10.0
                });
            }
        }
        p += wcslen(p) + 1;
    }
    return list;
}

std::wstring SerializeDrivesJson(const std::vector<DriveInfo>& drives) {
    std::wstringstream ss;
    ss << L"{\"type\":\"drives\",\"data\":[";
    for (size_t i = 0; i < drives.size(); ++i) {
        const auto& d = drives[i];
        if (i > 0) ss << L",";
        std::wstring mp = d.mountpoint;
        if (!mp.empty() && mp.back() == L'\\') mp += L'\\';
        ss << L"{\"mountpoint\":\"" << JsonEscape(mp) << L"\","
           << L"\"device\":\"" << JsonEscape(mp) << L"\","
           << L"\"label\":\"" << JsonEscape(d.label) << L"\","
           << L"\"fstype\":\"" << JsonEscape(d.fstype) << L"\","
           << L"\"manufacturer\":\"" << JsonEscape(d.manufacturer) << L"\","
           << L"\"model\":\"" << JsonEscape(d.model) << L"\","
           << L"\"total_gb\":" << d.total_gb << L","
           << L"\"free_gb\":" << d.free_gb << L","
           << L"\"used_gb\":" << d.used_gb << L","
           << L"\"percent\":" << d.percent << L"}";
    }
    ss << L"]}";
    return ss.str();
}

struct ProgressState {
    std::wstring current_test;
    double current_speed_mbs = 0.0;
    double current_iops = 0.0;
    double progress_percent = 0.0;
    std::wstring status = L"running";
    int passes = 1;
    int current_pass = 1;
    bool io_waiting = false;
    double elapsed_seconds = 0.0;

    double seq_q8_read_mbs = 0.0, seq_q8_read_std = 0.0;
    double seq_q8_write_mbs = 0.0, seq_q8_write_std = 0.0;
    double seq_read_mbs = 0.0, seq_read_std = 0.0;
    double seq_write_mbs = 0.0, seq_write_std = 0.0;
    double rnd4k_q32_read_mbs = 0.0, rnd4k_q32_read_std = 0.0, rnd4k_q32_read_iops = 0.0;
    double rnd4k_q32_write_mbs = 0.0, rnd4k_q32_write_std = 0.0, rnd4k_q32_write_iops = 0.0;
    double rnd4k_read_mbs = 0.0, rnd4k_read_std = 0.0, rnd4k_read_iops = 0.0;
    double rnd4k_write_mbs = 0.0, rnd4k_write_std = 0.0, rnd4k_write_iops = 0.0;
};

ProgressState g_prog;

// Post thread-safe progress to UI thread message queue
void PostProgressToWebView() {
    if (g_benchmarkTimerStarted) {
        g_prog.elapsed_seconds = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - g_benchmarkStart).count();
    }
    std::wstringstream ss;
    ss << std::fixed << std::setprecision(2);
    ss << L"{\"type\":\"progress\",\"data\":{"
       << L"\"status\":\"" << g_prog.status << L"\","
       << L"\"current_test\":\"" << g_prog.current_test << L"\","
       << L"\"current_speed_mbs\":" << g_prog.current_speed_mbs << L","
       << L"\"current_iops\":" << g_prog.current_iops << L","
       << L"\"io_waiting\":" << (g_prog.io_waiting ? L"true" : L"false") << L","
       << L"\"progress_percent\":" << g_prog.progress_percent << L","
       << L"\"passes\":" << g_prog.passes << L","
       << L"\"current_pass\":" << g_prog.current_pass << L","
       << L"\"elapsed_seconds\":" << g_prog.elapsed_seconds << L","
       << L"\"results\":{"
       << L"\"seq_q8_read_mbs\":" << g_prog.seq_q8_read_mbs << L","
       << L"\"seq_q8_read_std\":" << g_prog.seq_q8_read_std << L","
       << L"\"seq_q8_write_mbs\":" << g_prog.seq_q8_write_mbs << L","
       << L"\"seq_q8_write_std\":" << g_prog.seq_q8_write_std << L","
       << L"\"seq_read_mbs\":" << g_prog.seq_read_mbs << L","
       << L"\"seq_read_std\":" << g_prog.seq_read_std << L","
       << L"\"seq_write_mbs\":" << g_prog.seq_write_mbs << L","
       << L"\"seq_write_std\":" << g_prog.seq_write_std << L","
       << L"\"rnd4k_q32_read_mbs\":" << g_prog.rnd4k_q32_read_mbs << L","
       << L"\"rnd4k_q32_read_std\":" << g_prog.rnd4k_q32_read_std << L","
       << L"\"rnd4k_q32_read_iops\":" << g_prog.rnd4k_q32_read_iops << L","
       << L"\"rnd4k_q32_write_mbs\":" << g_prog.rnd4k_q32_write_mbs << L","
       << L"\"rnd4k_q32_write_std\":" << g_prog.rnd4k_q32_write_std << L","
       << L"\"rnd4k_q32_write_iops\":" << g_prog.rnd4k_q32_write_iops << L","
       << L"\"rnd4k_read_mbs\":" << g_prog.rnd4k_read_mbs << L","
       << L"\"rnd4k_read_std\":" << g_prog.rnd4k_read_std << L","
       << L"\"rnd4k_read_iops\":" << g_prog.rnd4k_read_iops << L","
       << L"\"rnd4k_write_mbs\":" << g_prog.rnd4k_write_mbs << L","
       << L"\"rnd4k_write_std\":" << g_prog.rnd4k_write_std << L","
       << L"\"rnd4k_write_iops\":" << g_prog.rnd4k_write_iops
       << L"}}}";

    std::wstring* pJson = new std::wstring(ss.str());
    PostMessageW(g_hWnd, WM_POST_PROGRESS, 0, (LPARAM)pJson);
}

void GlobalProgressCallback(const char* test_name, double speed_mbs, double iops, double pct) {
    g_prog.current_speed_mbs = speed_mbs;
    g_prog.current_iops = iops;
    g_prog.progress_percent = pct;
    g_prog.io_waiting = (g_prog.status == L"running" && speed_mbs <= 0.0 && pct < 100.0);
    PostProgressToWebView();
}

void NativeBenchmarkWorker(std::wstring target_dir, int size_mb, int passes, int write_through, double timeout_sec) {
    g_stopFlag = 0;
    g_benchmarkStart = std::chrono::steady_clock::now();
    g_benchmarkTimerStarted = true;
    g_prog = ProgressState();
    g_prog.status = L"running";
    g_prog.passes = passes;

    if (set_benchmark_timeout_sec(timeout_sec) != ERROR_SUCCESS) {
        g_prog.status = L"error";
        g_prog.current_test = L"無効なタイムアウト設定";
        g_prog.io_waiting = false;
        PostProgressToWebView();
        g_isRunning = false;
        return;
    }

    uint64_t file_size_bytes = static_cast<uint64_t>(size_mb) * 1024 * 1024;
    std::wstring test_file = target_dir + L"QuickDiskBench_wv_test.dat";
    HANDLE hCheck = CreateFileW(test_file.c_str(), GENERIC_READ | GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hCheck == INVALID_HANDLE_VALUE) {
        wchar_t temp_path[MAX_PATH];
        GetTempPathW(MAX_PATH, temp_path);
        test_file = std::wstring(temp_path) + L"QuickDiskBench_wv_test.dat";
    } else {
        CloseHandle(hCheck);
        DeleteFileW(test_file.c_str());
    }

    struct Step {
        int test_id;
        int test_type;
        int block_size;
        int q_depth;
        std::wstring name;
    };

    std::vector<Step> steps = {
        { 1, TEST_SEQ_WRITE, 1024 * 1024, 8, L"SEQ1M Q8T1 書き込み" },
        { 2, TEST_SEQ_READ,  1024 * 1024, 8, L"SEQ1M Q8T1 読み込み" },
        { 3, TEST_SEQ_WRITE, 1024 * 1024, 1, L"SEQ1M Q1T1 書き込み" },
        { 4, TEST_SEQ_READ,  1024 * 1024, 1, L"SEQ1M Q1T1 読み込み" },
        { 5, TEST_RND_WRITE, 4096,       32, L"RND4K Q32T1 書き込み" },
        { 6, TEST_RND_READ,  4096,       32, L"RND4K Q32T1 読み込み" },
        { 7, TEST_RND_WRITE, 4096,        1, L"RND4K Q1T1 書き込み" },
        { 8, TEST_RND_READ,  4096,        1, L"RND4K Q1T1 読み込み" }
    };

    int first_error = 0;

    for (const auto& step : steps) {
        if (g_stopFlag != 0 || first_error != 0) break;
        std::vector<double> spd_samples;
        std::vector<double> iops_samples;

        for (int p = 1; p <= passes; ++p) {
            if (g_stopFlag != 0 || first_error != 0) break;
            g_prog.current_pass = p;
            g_prog.current_test = step.name + (passes > 1 ? (L" (Pass " + std::to_wstring(p) + L"/" + std::to_wstring(passes) + L")") : L"");
            g_prog.io_waiting = false;
            PostProgressToWebView();

            double spd = 0.0, iops = 0.0;
            int ret = run_benchmark_test(
                test_file.c_str(),
                step.test_type,
                file_size_bytes,
                step.block_size,
                step.q_depth,
                write_through,
                GlobalProgressCallback,
                (const int*)&g_stopFlag,
                &spd,
                &iops
            );

            if (ret == 0 && spd > 0) {
                spd_samples.push_back(spd);
                iops_samples.push_back(iops);
            } else if (ret != 0) {
                first_error = ret;
                g_prog.status = L"error";
                g_prog.current_test = step.name + L" 失敗 (Win32 error " + std::to_wstring(ret) + L")";
                PostProgressToWebView();
                break;
            }
        }

        if (!spd_samples.empty()) {
            double sum = std::accumulate(spd_samples.begin(), spd_samples.end(), 0.0);
            double mean = sum / spd_samples.size();
            double std_dev = 0.0;
            if (spd_samples.size() > 1) {
                double sq = 0.0;
                for (double s : spd_samples) sq += (s - mean) * (s - mean);
                std_dev = std::sqrt(sq / (spd_samples.size() - 1));
            }
            double mean_iops = std::accumulate(iops_samples.begin(), iops_samples.end(), 0.0) / iops_samples.size();

            switch (step.test_id) {
                case 1: g_prog.seq_q8_write_mbs = mean; g_prog.seq_q8_write_std = std_dev; break;
                case 2: g_prog.seq_q8_read_mbs  = mean; g_prog.seq_q8_read_std  = std_dev; break;
                case 3: g_prog.seq_write_mbs    = mean; g_prog.seq_write_std    = std_dev; break;
                case 4: g_prog.seq_read_mbs     = mean; g_prog.seq_read_std     = std_dev; break;
                case 5: g_prog.rnd4k_q32_write_mbs = mean; g_prog.rnd4k_q32_write_std = std_dev; g_prog.rnd4k_q32_write_iops = mean_iops; break;
                case 6: g_prog.rnd4k_q32_read_mbs  = mean; g_prog.rnd4k_q32_read_std  = std_dev; g_prog.rnd4k_q32_read_iops  = mean_iops; break;
                case 7: g_prog.rnd4k_write_mbs     = mean; g_prog.rnd4k_write_std     = std_dev; g_prog.rnd4k_write_iops     = mean_iops; break;
                case 8: g_prog.rnd4k_read_mbs      = mean; g_prog.rnd4k_read_std      = std_dev; g_prog.rnd4k_read_iops      = mean_iops; break;
            }
        }
        PostProgressToWebView();
    }

    DeleteFileW(test_file.c_str());
    if (first_error != 0) {
        g_prog.status = L"error";
        g_prog.current_test = L"測定失敗 (Win32 error " + std::to_wstring(first_error) + L")";
    } else {
        g_prog.status = (g_stopFlag != 0) ? L"stopped" : L"completed";
        g_prog.progress_percent = 100.0;
        g_prog.current_test = (g_stopFlag != 0) ? L"測定が停止されました。" : L"測定完了！すべてのテストが終了しました。";
    }
    g_prog.io_waiting = false;
    PostProgressToWebView();
    g_isRunning = false;
}

LRESULT CALLBACK WndProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch (msg) {
    case WM_SIZE:
        if (g_controller) {
            RECT bounds;
            GetClientRect(hWnd, &bounds);
            HRESULT hr = g_controller->put_Bounds(bounds);
            if (FAILED(hr)) LOG("[ERR] put_Bounds failed: 0x%08X", (unsigned)hr);
        }
        break;

    case WM_POST_PROGRESS:
        {
            std::wstring* pJson = (std::wstring*)lParam;
            if (pJson) {
                if (g_webview) {
                    HRESULT hr = g_webview->PostWebMessageAsJson(pJson->c_str());
                    if (FAILED(hr)) LOG("[ERR] PostWebMessageAsJson failed: 0x%08X", (unsigned)hr);
                }
                delete pJson;
            }
        }
        break;

    case WM_DESTROY:
        if (g_workerThread.joinable()) {
            g_stopFlag = 1;
            // Never join from the UI thread: the worker may be waiting for
            // the UI message queue while reporting progress.
            g_workerThread.detach();
        }
        if (g_controller) {
            g_controller->Close();
            g_controller->Release();
            g_controller = NULL;
        }
        if (g_webview) {
            g_webview->Release();
            g_webview = NULL;
        }
        PostQuitMessage(0);
        break;

    default:
        return DefWindowProcW(hWnd, msg, wParam, lParam);
    }
    return 0;
}

// Helper to read entire UTF-8 file into std::wstring
std::wstring ReadUtf8FileToWString(const std::wstring& path) {
    std::ifstream file(path.c_str(), std::ios::binary);
    if (!file.is_open()) return L"";
    std::string str((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
    if (str.empty()) return L"";
    int count = MultiByteToWideChar(CP_UTF8, 0, str.c_str(), (int)str.length(), NULL, 0);
    std::wstring wstr(count, 0);
    MultiByteToWideChar(CP_UTF8, 0, str.c_str(), (int)str.length(), &wstr[0], count);
    return wstr;
}

// ===== Diagnostic file logger =====
static FILE* g_log = nullptr;
static void LOG(const char* fmt, ...) {
    if (!g_log) {
        if (g_logPath.empty()) {
            wchar_t exePath[MAX_PATH] = {0};
            GetModuleFileNameW(NULL, exePath, MAX_PATH);
            g_logPath = exePath;
            size_t slash = g_logPath.find_last_of(L"\\/");
            if (slash != std::wstring::npos) g_logPath.resize(slash + 1);
            g_logPath += L"QuickDiskBench_debug.log";
        }
        char path[MAX_PATH * 3] = {0};
        WideCharToMultiByte(CP_UTF8, 0, g_logPath.c_str(), -1, path, sizeof(path), NULL, NULL);
        g_log = fopen(path, "w");
    }
    if (!g_log) return;
    va_list ap; va_start(ap, fmt); vfprintf(g_log, fmt, ap); va_end(ap);
    fprintf(g_log, "\n"); fflush(g_log);
}
// ==================================

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE, LPSTR lpCmdLine, int nCmdShow) {
    LOG("[1] WinMain entered");
    std::string cmdStr = lpCmdLine ? lpCmdLine : "";
    if (cmdStr.find("--test-run") != std::string::npos) {
        // Run full benchmark verification
        NativeBenchmarkWorker(L"C:\\", 64, 1, 0, 60.0);
        std::wofstream out("test_run.log");
        out << L"STATUS: " << g_prog.status << L"\n";
        out << L"SEQ1M_Q8_WRITE: " << g_prog.seq_q8_write_mbs << L"\n";
        out << L"SEQ1M_Q8_READ: " << g_prog.seq_q8_read_mbs << L"\n";
        out << L"SEQ1M_Q1_WRITE: " << g_prog.seq_write_mbs << L"\n";
        out << L"SEQ1M_Q1_READ: " << g_prog.seq_read_mbs << L"\n";
        out << L"RND4K_Q32_WRITE: " << g_prog.rnd4k_q32_write_mbs << L" IOPS: " << g_prog.rnd4k_q32_write_iops << L"\n";
        out << L"RND4K_Q32_READ: " << g_prog.rnd4k_q32_read_mbs << L" IOPS: " << g_prog.rnd4k_q32_read_iops << L"\n";
        out << L"RND4K_Q1_WRITE: " << g_prog.rnd4k_write_mbs << L" IOPS: " << g_prog.rnd4k_write_iops << L"\n";
        out << L"RND4K_Q1_READ: " << g_prog.rnd4k_read_mbs << L" IOPS: " << g_prog.rnd4k_read_iops << L"\n";
        out.close();
        return 0;
    }

    CoInitializeEx(NULL, COINIT_APARTMENTTHREADED);
    OleInitialize(NULL);
    SetProcessDPIAware();
    LOG("[2] COM initialized");

    WNDCLASSEXW wc = {0};
    wc.cbSize = sizeof(WNDCLASSEXW);
    wc.style = CS_HREDRAW | CS_VREDRAW;
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInstance;
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)GetStockObject(BLACK_BRUSH);
    wc.lpszClassName = L"QuickDiskBenchNativeWebView2Class";
    wc.hIcon = LoadIconW(hInstance, MAKEINTRESOURCEW(IDI_ICON1));
    wc.hIconSm = LoadIconW(hInstance, MAKEINTRESOURCEW(IDI_ICON1));

    if (!RegisterClassExW(&wc)) { LOG("[ERR] RegisterClassExW failed: %lu", GetLastError()); return 1; }
    LOG("[3] Window class registered");

    g_hWnd = CreateWindowExW(
        0, wc.lpszClassName,
        L"QuickDiskBench v2.1.1 - Native Storage Benchmark (Cache Modes & Statistics)",
        WS_OVERLAPPEDWINDOW,
        // Leave enough vertical space for the results card and the chart at startup.
        CW_USEDEFAULT, CW_USEDEFAULT, 900, 900,
        NULL, NULL, hInstance, NULL
    );
    if (!g_hWnd) { LOG("[ERR] CreateWindowExW failed: %lu", GetLastError()); return 1; }
    LOG("[4] Window created HWND=%p", (void*)g_hWnd);

    BOOL dark = TRUE;
    DwmSetWindowAttribute(g_hWnd, DWMWA_USE_IMMERSIVE_DARK_MODE, &dark, sizeof(dark));
    ShowWindow(g_hWnd, nCmdShow);
    UpdateWindow(g_hWnd);
    LOG("[5] Window shown");

    // Get EXE directory
    wchar_t exePath[MAX_PATH];
    GetModuleFileNameW(NULL, exePath, MAX_PATH);
    std::wstring appDir = exePath;
    size_t lastSlash = appDir.find_last_of(L"\\/");
    if (lastSlash != std::wstring::npos) appDir = appDir.substr(0, lastSlash);

    // Determine HTML file path
    std::wstring htmlFile = appDir + L"\\index.html";
    if (GetFileAttributesW(htmlFile.c_str()) == INVALID_FILE_ATTRIBUTES) {
        htmlFile = appDir + L"\\templates\\index.html";
    }
    LOG("[6] HTML file: %S (exists=%d)", htmlFile.c_str(),
        GetFileAttributesW(htmlFile.c_str()) != INVALID_FILE_ATTRIBUTES ? 1 : 0);

    std::wstring htmlContent = ReadUtf8FileToWString(htmlFile);
    LOG("[7] htmlContent size: %zu chars", htmlContent.size());

    // User Data Folder — use fixed path, do NOT block main thread to clean it
    wchar_t tempPath[MAX_PATH];
    GetTempPathW(MAX_PATH, tempPath);
    std::wstring userDataFolder = std::wstring(tempPath) + L"QuickDiskBench_WVData2";
    CreateDirectoryW(userDataFolder.c_str(), NULL);
    LOG("[8] User data folder: %S", userDataFolder.c_str());

    // Load WebView2Loader.dll
    std::wstring loaderDll = appDir + L"\\WebView2Loader.dll";
    HMODULE hLoader = LoadLibraryW(loaderDll.c_str());
    if (!hLoader) {
        hLoader = LoadLibraryW(L"C:\\tools\\webview2\\build\\native\\x64\\WebView2Loader.dll");
    }
    if (!hLoader) {
        LOG("[ERR] WebView2Loader.dll not found");
        MessageBoxW(g_hWnd, L"WebView2Loader.dll not found.\nPlace it next to QuickDiskBench.exe.", L"QuickDiskBench Error", MB_ICONERROR);
        return 1;
    }
    LOG("[9] WebView2Loader.dll loaded");

    CreateEnvFn createEnv = (CreateEnvFn)GetProcAddress(hLoader, "CreateCoreWebView2EnvironmentWithOptions");
    if (!createEnv) {
        LOG("[ERR] CreateCoreWebView2EnvironmentWithOptions not found in DLL");
        MessageBoxW(g_hWnd, L"WebView2: CreateCoreWebView2EnvironmentWithOptions not found", L"QuickDiskBench Error", MB_ICONERROR);
        return 1;
    }
    LOG("[10] createEnv proc found, calling...");

    createEnv(
        nullptr, userDataFolder.c_str(), nullptr,
        new EnvCompletedHandler(
            [htmlContent](HRESULT result, ICoreWebView2Environment* env) -> HRESULT {
                LOG("[11] EnvCompletedHandler called, HRESULT=0x%08X, env=%p", (unsigned)result, (void*)env);
                if (FAILED(result) || !env) {
                    wchar_t msg[256];
                    swprintf_s(msg, L"WebView2 Runtimeを初期化できませんでした。\n\n"
                                   L"WebView2 Runtimeがインストールされていないか、破損している可能性があります。\n"
                                   L"Microsoft Edge WebView2 Runtime (Evergreen) をインストールしてから再実行してください。\n\n"
                                   L"エラーコード: 0x%08X\n"
                                   L"改善しない場合は %%TEMP%%\\QuickDiskBench_WVData2 を削除して再実行してください。",
                               (unsigned)result);
                    MessageBoxW(g_hWnd, msg, L"QuickDiskBench Error", MB_ICONERROR);
                    return result;
                }

                env->CreateCoreWebView2Controller(g_hWnd,
                    new ControllerCompletedHandler(
                        [htmlContent](HRESULT result, ICoreWebView2Controller* controller) -> HRESULT {
                            LOG("[12] ControllerCompletedHandler called, HRESULT=0x%08X, ctrl=%p", (unsigned)result, (void*)controller);
                            if (FAILED(result) || !controller) {
                                wchar_t msg[256];
                                swprintf_s(msg, L"WebView2 controller creation failed: 0x%08X", (unsigned)result);
                                MessageBoxW(g_hWnd, msg, L"QuickDiskBench Error", MB_ICONERROR);
                                return result;
                            }

                            g_controller = controller;
                            g_controller->AddRef();
                            g_controller->get_CoreWebView2(&g_webview);
                            LOG("[13] CoreWebView2 obtained, g_webview=%p", (void*)g_webview);

                            RECT bounds;
                            GetClientRect(g_hWnd, &bounds);
                            HRESULT hrBounds = g_controller->put_Bounds(bounds);
                            HRESULT hrVisible = g_controller->put_IsVisible(TRUE);
                            LOG("[13b] put_Bounds=0x%08X put_IsVisible=0x%08X", (unsigned)hrBounds, (unsigned)hrVisible);

                            ICoreWebView2Settings* settings = NULL;
                            g_webview->get_Settings(&settings);
                            if (settings) {
                                settings->put_AreDefaultContextMenusEnabled(FALSE);
                                settings->put_IsStatusBarEnabled(FALSE);
                                settings->Release();
                            }

                            // WebMessage handler
                            EventRegistrationToken token;
                            HRESULT msgHr = g_webview->add_WebMessageReceived(
                                new WebMessageReceivedHandler(
                                    [](ICoreWebView2* webview, ICoreWebView2WebMessageReceivedEventArgs* args) -> HRESULT {
                                        LPWSTR jsonRaw = NULL;
                                        args->get_WebMessageAsJson(&jsonRaw);
                                        std::wstring msg = jsonRaw ? jsonRaw : L"";
                                        if (jsonRaw) CoTaskMemFree(jsonRaw);

                                        if (msg.empty()) {
                                            LPWSTR strRaw = NULL;
                                            args->TryGetWebMessageAsString(&strRaw);
                                            if (strRaw) { msg = strRaw; CoTaskMemFree(strRaw); }
                                        }

                                        if (msg.find(L"get_drives") != std::wstring::npos) {
                                            auto drives = GetDrivesList();
                                            std::wstring json = SerializeDrivesJson(drives);
                                            HRESULT hr = webview->PostWebMessageAsJson(json.c_str());
                                            LOG("[MSG] get_drives response hr=0x%08X count=%zu", (unsigned)hr, drives.size());
                                        } else if (msg.find(L"\"start\"") != std::wstring::npos || msg.find(L"start") != std::wstring::npos) {
                                            if (g_isRunning) return S_OK;

                                            std::wstring drive = L"C:\\";
                                            size_t dPos = msg.find(L"drive");
                                            if (dPos != std::wstring::npos) {
                                                size_t colon = msg.find(L':', dPos);
                                                if (colon != std::wstring::npos) {
                                                    size_t start = msg.find_first_not_of(L" \t\\\":", colon);
                                                    if (start != std::wstring::npos) {
                                                        size_t end = msg.find_first_of(L"\\\",}", start);
                                                        if (end != std::wstring::npos) {
                                                            drive = msg.substr(start, end - start);
                                                            if (drive.back() != L'\\') drive += L'\\';
                                                        }
                                                    }
                                                }
                                            }

                                            int size_mb = 1024;
                                            size_t sPos = msg.find(L"file_size_mb");
                                            if (sPos != std::wstring::npos) {
                                                size_t colon = msg.find(L':', sPos);
                                                if (colon != std::wstring::npos) {
                                                    size_mb = _wtoi(msg.substr(colon + 1).c_str());
                                                    if (size_mb <= 0) size_mb = 1024;
                                                }
                                            }

                                            int passes = 5;
                                            size_t pPos = msg.find(L"passes");
                                            if (pPos != std::wstring::npos) {
                                                size_t colon = msg.find(L':', pPos);
                                                if (colon != std::wstring::npos) {
                                                    passes = _wtoi(msg.substr(colon + 1).c_str());
                                                    if (passes <= 0) passes = 5;
                                                }
                                            }

                                            double timeout_sec = 60.0;
                                            size_t tPos = msg.find(L"timeout_sec");
                                            if (tPos != std::wstring::npos) {
                                                size_t colon = msg.find(L':', tPos);
                                                if (colon != std::wstring::npos) {
                                                    timeout_sec = _wtof(msg.substr(colon + 1).c_str());
                                                    if (timeout_sec < 1.0 || timeout_sec > 3600.0) timeout_sec = 60.0;
                                                }
                                            }

                                            int write_through = (msg.find(L"raw") != std::wstring::npos) ? 1 : 0;

                                            g_isRunning = true;
                                            if (g_workerThread.joinable()) g_workerThread.join();
                                            g_workerThread = std::thread(NativeBenchmarkWorker, drive, size_mb, passes, write_through, timeout_sec);
                                        } else if (msg.find(L"stop") != std::wstring::npos) {
                                            g_stopFlag = 1;
                                        }
                                        return S_OK;
                                    }
                                ), &token
                            );
                            LOG("[MSG] add_WebMessageReceived hr=0x%08X", (unsigned)msgHr);

                            // Load UI
                            LOG("[14] Calling NavigateToString, htmlContent.size=%zu", htmlContent.size());
                            if (htmlContent.empty()) {
                                MessageBoxW(g_hWnd, L"Failed to read index.html\nPlace index.html next to QuickDiskBench.exe.", L"QuickDiskBench Error", MB_ICONERROR);
                            } else {
                                HRESULT navResult = g_webview->NavigateToString(htmlContent.c_str());
                                LOG("[15] NavigateToString returned 0x%08X", (unsigned)navResult);
                                if (FAILED(navResult)) {
                                    wchar_t errMsg[256];
                                    swprintf_s(errMsg, L"NavigateToString failed: 0x%08X\nHTML size: %zu chars", (unsigned)navResult, htmlContent.size());
                                    MessageBoxW(g_hWnd, errMsg, L"QuickDiskBench Error", MB_ICONERROR);
                                }
                            }
                            return S_OK;
                        }
                    )
                );
                return S_OK;
            }
        )
    );

    LOG("[16] Entering message loop");
    MSG msg;
    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }

    OleUninitialize();
    CoUninitialize();
    LOG("[17] Exiting WinMain");
    if (g_log) fclose(g_log);
    return (int)msg.wParam;
}
