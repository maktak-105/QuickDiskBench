#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <windowsx.h>
#include <commctrl.h>
#include <dwmapi.h>
#include <iostream>
#include <vector>
#include <string>
#include <sstream>
#include <iomanip>
#include <cmath>
#include <numeric>
#include <algorithm>
#include <thread>
#include <atomic>

#pragma comment(lib, "comctl32.lib")
#pragma comment(lib, "dwmapi.lib")
#pragma comment(lib, "gdi32.lib")
#pragma comment(lib, "user32.lib")

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

// UI Colors (Dark Modern Theme)
#define COLOR_BG RGB(15, 23, 42)         // #0f172a (Dark Slate)
#define COLOR_CARD_BG RGB(30, 41, 59)    // #1e293b
#define COLOR_CARD_ACTIVE RGB(15, 45, 65)// Highlight
#define COLOR_TEXT_MAIN RGB(248, 250, 252)// #f8fafc
#define COLOR_TEXT_MUTED RGB(148, 163, 184)// #94a3b8
#define COLOR_CYAN RGB(0, 240, 255)       // #00f0ff (Read)
#define COLOR_PURPLE RGB(176, 38, 255)    // #b026ff (Write)
#define COLOR_ACCENT_BORDER RGB(51, 65, 85)

struct DriveItem {
    std::wstring letter;
    std::wstring label;
    std::wstring fstype;
    double free_gb;
    double total_gb;
};

struct MetricCard {
    std::wstring name;
    std::wstring sub;
    double read_mbs = 0.0;
    double read_std = 0.0;
    double read_iops = 0.0;
    double write_mbs = 0.0;
    double write_std = 0.0;
    double write_iops = 0.0;
    bool has_iops = false;
};

// Global GUI State
HWND g_hWnd = NULL;
HWND g_hComboDrive = NULL;
HWND g_hComboSize = NULL;
HWND g_hComboPasses = NULL;
HWND g_hComboProfile = NULL;
HWND g_hBtnStart = NULL;
HWND g_hBtnStop = NULL;
HWND g_hProgressBar = NULL;

HFONT g_hFontMain = NULL;
HFONT g_hFontBold = NULL;
HFONT g_hFontNumber = NULL;
HFONT g_hFontSmall = NULL;

HBRUSH g_hBrushBg = NULL;
HBRUSH g_hBrushCard = NULL;
HBRUSH g_hBrushActive = NULL;

std::vector<DriveItem> g_drives;
MetricCard g_cards[4] = {
    { L"SEQ1M Q8T1", L"Sequential (Q8 / 1MB)", 0, 0, 0, 0, 0, 0, false },
    { L"SEQ1M Q1T1", L"Sequential (Q1 / 1MB)", 0, 0, 0, 0, 0, 0, false },
    { L"RND4K Q32T1", L"Random 4KB (Q32 Overlapped)", 0, 0, 0, 0, 0, 0, true },
    { L"RND4K Q1T1", L"Random 4KB (Q1 Single)", 0, 0, 0, 0, 0, 0, true }
};

std::atomic<bool> g_isRunning(false);
std::atomic<int> g_stopFlag(0);
std::thread g_workerThread;
int g_activeRowIndex = -1;
std::wstring g_statusText = L"待機中 - ドライブを選択して「テスト開始」を押してください";
double g_currentProgress = 0.0;

#define WM_UPDATE_PROGRESS (WM_USER + 1)
#define WM_TEST_FINISHED   (WM_USER + 2)

// Enumerate available drives
std::vector<DriveItem> EnumerateDrives() {
    std::vector<DriveItem> list;
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
            double free_gb = 0.0, total_gb = 0.0;
            if (GetDiskFreeSpaceExW(drive.c_str(), &free_bytes, &total_bytes, NULL)) {
                free_gb = free_bytes.QuadPart / (1024.0 * 1024.0 * 1024.0);
                total_gb = total_bytes.QuadPart / (1024.0 * 1024.0 * 1024.0);
            }

            // Exclude cloud drive if FAT32 / Google Drive
            std::wstring label = vol_name;
            if (label.find(L"Google") == std::wstring::npos) {
                list.push_back({ drive, label.empty() ? L"(No Label)" : label, fs_name, free_gb, total_gb });
            }
        }
        p += wcslen(p) + 1;
    }
    return list;
}

void GlobalProgressCallback(const char* test_name, double speed_mbs, double iops, double pct) {
    if (g_hWnd) {
        PostMessage(g_hWnd, WM_UPDATE_PROGRESS, (WPARAM)(int)(pct * 10), (LPARAM)(int)(speed_mbs * 10));
    }
}

// Background Benchmark Runner Thread
void BenchmarkWorker(std::wstring target_dir, int size_mb, int passes, int write_through) {
    g_stopFlag = 0;
    uint64_t file_size_bytes = static_cast<uint64_t>(size_mb) * 1024 * 1024;

    std::wstring test_file = target_dir + L"QuickDiskBench_gui_test.dat";
    HANDLE hCheck = CreateFileW(test_file.c_str(), GENERIC_READ | GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hCheck == INVALID_HANDLE_VALUE) {
        wchar_t temp_path[MAX_PATH];
        GetTempPathW(MAX_PATH, temp_path);
        test_file = std::wstring(temp_path) + L"QuickDiskBench_gui_test.dat";
    } else {
        CloseHandle(hCheck);
        DeleteFileW(test_file.c_str());
    }

    struct Step {
        int card_idx;
        bool is_read;
        int test_type;
        int block_size;
        int q_depth;
        std::wstring name;
    };

    std::vector<Step> steps = {
        { 0, false, TEST_SEQ_WRITE, 1024 * 1024, 8, L"SEQ1M Q8T1 Write" },
        { 0, true,  TEST_SEQ_READ,  1024 * 1024, 8, L"SEQ1M Q8T1 Read" },
        { 1, false, TEST_SEQ_WRITE, 1024 * 1024, 1, L"SEQ1M Q1T1 Write" },
        { 1, true,  TEST_SEQ_READ,  1024 * 1024, 1, L"SEQ1M Q1T1 Read" },
        { 2, false, TEST_RND_WRITE, 4096,       32, L"RND4K Q32T1 Write" },
        { 2, true,  TEST_RND_READ,  4096,       32, L"RND4K Q32T1 Read" },
        { 3, false, TEST_RND_WRITE, 4096,        1, L"RND4K Q1T1 Write" },
        { 3, true,  TEST_RND_READ,  4096,        1, L"RND4K Q1T1 Read" }
    };

    for (const auto& step : steps) {
        if (g_stopFlag != 0) break;
        g_activeRowIndex = step.card_idx;

        std::vector<double> speed_samples;
        std::vector<double> iops_samples;

        for (int p = 1; p <= passes; ++p) {
            if (g_stopFlag != 0) break;
            std::wstringstream ss;
            ss << L"測定中: " << step.name;
            if (passes > 1) ss << L" (Pass " << p << L"/" << passes << L")";
            g_statusText = ss.str();
            PostMessage(g_hWnd, WM_UPDATE_PROGRESS, 0, 0);

            double speed = 0.0, iops = 0.0;
            int ret = run_benchmark_test(
                test_file.c_str(),
                step.test_type,
                file_size_bytes,
                step.block_size,
                step.q_depth,
                write_through,
                GlobalProgressCallback,
                (const int*)&g_stopFlag,
                &speed,
                &iops
            );

            if (ret == 0 && speed > 0) {
                speed_samples.push_back(speed);
                iops_samples.push_back(iops);
            }
        }

        if (!speed_samples.empty()) {
            double sum = std::accumulate(speed_samples.begin(), speed_samples.end(), 0.0);
            double mean = sum / speed_samples.size();
            double std_dev = 0.0;
            if (speed_samples.size() > 1) {
                double sq = 0.0;
                for (double s : speed_samples) sq += (s - mean) * (s - mean);
                std_dev = std::sqrt(sq / (speed_samples.size() - 1));
            }
            double mean_iops = std::accumulate(iops_samples.begin(), iops_samples.end(), 0.0) / iops_samples.size();

            if (step.is_read) {
                g_cards[step.card_idx].read_mbs = mean;
                g_cards[step.card_idx].read_std = std_dev;
                g_cards[step.card_idx].read_iops = mean_iops;
            } else {
                g_cards[step.card_idx].write_mbs = mean;
                g_cards[step.card_idx].write_std = std_dev;
                g_cards[step.card_idx].write_iops = mean_iops;
            }
        }
        PostMessage(g_hWnd, WM_UPDATE_PROGRESS, 1000, 0);
    }

    DeleteFileW(test_file.c_str());
    g_activeRowIndex = -1;
    g_statusText = (g_stopFlag != 0) ? L"測定が中断されました。" : L"測定完了！すべてのテストが終了しました。";
    g_isRunning = false;
    PostMessage(g_hWnd, WM_TEST_FINISHED, 0, 0);
}

void StartBenchmark() {
    if (g_isRunning) return;

    int drive_idx = ComboBox_GetCurSel(g_hComboDrive);
    if (drive_idx < 0 || drive_idx >= (int)g_drives.size()) return;

    std::wstring target_dir = g_drives[drive_idx].letter;
    
    int size_idx = ComboBox_GetCurSel(g_hComboSize);
    int sizes[] = { 256, 512, 1024, 2048 };
    int size_mb = sizes[std::max(0, std::min(3, size_idx))];

    int pass_idx = ComboBox_GetCurSel(g_hComboPasses);
    int passes_arr[] = { 1, 3, 5, 9 };
    int passes = passes_arr[std::max(0, std::min(3, pass_idx))];

    int profile_idx = ComboBox_GetCurSel(g_hComboProfile);
    int write_through = (profile_idx == 1) ? 1 : 0;

    // Reset results
    for (int i = 0; i < 4; ++i) {
        g_cards[i].read_mbs = 0; g_cards[i].read_std = 0; g_cards[i].read_iops = 0;
        g_cards[i].write_mbs = 0; g_cards[i].write_std = 0; g_cards[i].write_iops = 0;
    }

    g_isRunning = true;
    EnableWindow(g_hBtnStart, FALSE);
    EnableWindow(g_hBtnStop, TRUE);
    EnableWindow(g_hComboDrive, FALSE);
    EnableWindow(g_hComboSize, FALSE);
    EnableWindow(g_hComboPasses, FALSE);
    EnableWindow(g_hComboProfile, FALSE);

    if (g_workerThread.joinable()) g_workerThread.join();
    g_workerThread = std::thread(BenchmarkWorker, target_dir, size_mb, passes, write_through);
}

void StopBenchmark() {
    if (!g_isRunning) return;
    g_stopFlag = 1;
    g_statusText = L"停止中...";
    InvalidateRect(g_hWnd, NULL, TRUE);
}

LRESULT CALLBACK WndProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch (msg) {
    case WM_CREATE: {
        // Init fonts
        g_hFontMain = CreateFontW(-13, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
        g_hFontBold = CreateFontW(-14, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
        g_hFontNumber = CreateFontW(-22, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Consolas");
        g_hFontSmall = CreateFontW(-11, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");

        g_hBrushBg = CreateSolidBrush(COLOR_BG);
        g_hBrushCard = CreateSolidBrush(COLOR_CARD_BG);
        g_hBrushActive = CreateSolidBrush(COLOR_CARD_ACTIVE);

        // Toolbar Combos & Buttons
        g_hComboProfile = CreateWindowW(L"COMBOBOX", NULL, WS_CHILD | WS_VISIBLE | CBS_DROPDOWNLIST | WS_VSCROLL, 16, 16, 210, 150, hWnd, (HMENU)101, NULL, NULL);
        ComboBox_AddString(g_hComboProfile, L"キャッシュあり");
        ComboBox_AddString(g_hComboProfile, L"キャッシュなし");
        ComboBox_SetCurSel(g_hComboProfile, 0);

        g_hComboDrive = CreateWindowW(L"COMBOBOX", NULL, WS_CHILD | WS_VISIBLE | CBS_DROPDOWNLIST | WS_VSCROLL, 236, 16, 220, 200, hWnd, (HMENU)102, NULL, NULL);
        g_drives = EnumerateDrives();
        for (const auto& d : g_drives) {
            std::wstringstream ss;
            ss << d.letter << L" [" << d.label << L"] (" << std::fixed << std::setprecision(1) << d.free_gb << L"G Free)";
            ComboBox_AddString(g_hComboDrive, ss.str().c_str());
        }
        ComboBox_SetCurSel(g_hComboDrive, 0);

        g_hComboSize = CreateWindowW(L"COMBOBOX", NULL, WS_CHILD | WS_VISIBLE | CBS_DROPDOWNLIST, 466, 16, 95, 150, hWnd, (HMENU)103, NULL, NULL);
        ComboBox_AddString(g_hComboSize, L"256 MiB");
        ComboBox_AddString(g_hComboSize, L"512 MiB");
        ComboBox_AddString(g_hComboSize, L"1 GiB");
        ComboBox_AddString(g_hComboSize, L"2 GiB");
        ComboBox_SetCurSel(g_hComboSize, 1);

        g_hComboPasses = CreateWindowW(L"COMBOBOX", NULL, WS_CHILD | WS_VISIBLE | CBS_DROPDOWNLIST, 571, 16, 100, 150, hWnd, (HMENU)104, NULL, NULL);
        ComboBox_AddString(g_hComboPasses, L"1 回 (高速)");
        ComboBox_AddString(g_hComboPasses, L"3 回");
        ComboBox_AddString(g_hComboPasses, L"5 回 (標準)");
        ComboBox_AddString(g_hComboPasses, L"9 回 (高精度)");
        ComboBox_SetCurSel(g_hComboPasses, 0);

        g_hBtnStart = CreateWindowW(L"BUTTON", L"▶ テスト開始", WS_CHILD | WS_VISIBLE | BS_DEFPUSHBUTTON, 681, 14, 110, 28, hWnd, (HMENU)201, NULL, NULL);
        g_hBtnStop = CreateWindowW(L"BUTTON", L"■ 停止", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 801, 14, 80, 28, hWnd, (HMENU)202, NULL, NULL);
        EnableWindow(g_hBtnStop, FALSE);

        SendMessage(g_hComboProfile, WM_SETFONT, (WPARAM)g_hFontMain, TRUE);
        SendMessage(g_hComboDrive, WM_SETFONT, (WPARAM)g_hFontMain, TRUE);
        SendMessage(g_hComboSize, WM_SETFONT, (WPARAM)g_hFontMain, TRUE);
        SendMessage(g_hComboPasses, WM_SETFONT, (WPARAM)g_hFontMain, TRUE);
        SendMessage(g_hBtnStart, WM_SETFONT, (WPARAM)g_hFontBold, TRUE);
        SendMessage(g_hBtnStop, WM_SETFONT, (WPARAM)g_hFontBold, TRUE);

        // Dark titlebar
        BOOL dark = TRUE;
        DwmSetWindowAttribute(hWnd, DWMWA_USE_IMMERSIVE_DARK_MODE, &dark, sizeof(dark));
        break;
    }

    case WM_COMMAND: {
        int id = LOWORD(wParam);
        if (id == 201) StartBenchmark();
        else if (id == 202) StopBenchmark();
        break;
    }

    case WM_UPDATE_PROGRESS:
        InvalidateRect(hWnd, NULL, FALSE);
        break;

    case WM_TEST_FINISHED:
        EnableWindow(g_hBtnStart, TRUE);
        EnableWindow(g_hBtnStop, FALSE);
        EnableWindow(g_hComboDrive, TRUE);
        EnableWindow(g_hComboSize, TRUE);
        EnableWindow(g_hComboPasses, TRUE);
        EnableWindow(g_hComboProfile, TRUE);
        InvalidateRect(hWnd, NULL, TRUE);
        break;

    case WM_PAINT: {
        PAINTSTRUCT ps;
        HDC hdc = BeginPaint(hWnd, &ps);

        RECT clientRect;
        GetClientRect(hWnd, &clientRect);

        // Double buffer
        HDC memDC = CreateCompatibleDC(hdc);
        HBITMAP memBmp = CreateCompatibleBitmap(hdc, clientRect.right, clientRect.bottom);
        SelectObject(memDC, memBmp);

        FillRect(memDC, &clientRect, g_hBrushBg);
        SetBkMode(memDC, TRANSPARENT);

        // Render 4 Benchmark Rows
        int topY = 60;
        int rowH = 76;
        int gapY = 8;

        for (int i = 0; i < 4; ++i) {
            RECT rowRect = { 16, topY + i * (rowH + gapY), clientRect.right - 16, topY + i * (rowH + gapY) + rowH };
            HBRUSH rowBrush = (i == g_activeRowIndex) ? g_hBrushActive : g_hBrushCard;
            FillRect(memDC, &rowRect, rowBrush);

            // Row Border
            HPEN hPen = CreatePen(PS_SOLID, 1, (i == g_activeRowIndex) ? COLOR_CYAN : COLOR_ACCENT_BORDER);
            SelectObject(memDC, hPen);
            SelectObject(memDC, GetStockObject(NULL_BRUSH));
            RoundRect(memDC, rowRect.left, rowRect.top, rowRect.right, rowRect.bottom, 8, 8);
            DeleteObject(hPen);

            // 1. Test Info (Left)
            SelectObject(memDC, g_hFontBold);
            SetTextColor(memDC, COLOR_TEXT_MAIN);
            TextOutW(memDC, rowRect.left + 16, rowRect.top + 16, g_cards[i].name.c_str(), g_cards[i].name.length());

            SelectObject(memDC, g_hFontSmall);
            SetTextColor(memDC, COLOR_TEXT_MUTED);
            TextOutW(memDC, rowRect.left + 16, rowRect.top + 40, g_cards[i].sub.c_str(), g_cards[i].sub.length());

            // 2. Read Card (Middle)
            int cardW = 300;
            int readX = rowRect.left + 230;
            RECT readRect = { readX, rowRect.top + 8, readX + cardW, rowRect.bottom - 8 };
            
            SelectObject(memDC, g_hFontSmall);
            SetTextColor(memDC, COLOR_CYAN);
            TextOutW(memDC, readRect.left + 10, readRect.top + 6, L"READ (MB/s)", 11);

            SelectObject(memDC, g_hFontNumber);
            SetTextColor(memDC, (g_cards[i].read_mbs > 0) ? RGB(255, 255, 255) : COLOR_TEXT_MUTED);
            std::wstringstream ssRead;
            ssRead << std::fixed << std::setprecision(2) << g_cards[i].read_mbs;
            TextOutW(memDC, readRect.left + 10, readRect.top + 24, ssRead.str().c_str(), ssRead.str().length());

            // Sub Stats / IOPS
            SelectObject(memDC, g_hFontSmall);
            SetTextColor(memDC, COLOR_CYAN);
            std::wstringstream ssReadSub;
            if (g_cards[i].read_std > 0) ssReadSub << L"±" << std::fixed << std::setprecision(2) << g_cards[i].read_std << L" ";
            if (g_cards[i].has_iops && g_cards[i].read_iops > 0) ssReadSub << L"[" << (int)g_cards[i].read_iops << L" IOPS]";
            TextOutW(memDC, readRect.left + 160, readRect.top + 32, ssReadSub.str().c_str(), ssReadSub.str().length());

            // 3. Write Card (Right)
            int writeX = readX + cardW + 16;
            RECT writeRect = { writeX, rowRect.top + 8, writeX + cardW, rowRect.bottom - 8 };
            
            SelectObject(memDC, g_hFontSmall);
            SetTextColor(memDC, COLOR_PURPLE);
            TextOutW(memDC, writeRect.left + 10, writeRect.top + 6, L"WRITE (MB/s)", 12);

            SelectObject(memDC, g_hFontNumber);
            SetTextColor(memDC, (g_cards[i].write_mbs > 0) ? RGB(255, 255, 255) : COLOR_TEXT_MUTED);
            std::wstringstream ssWrite;
            ssWrite << std::fixed << std::setprecision(2) << g_cards[i].write_mbs;
            TextOutW(memDC, writeRect.left + 10, writeRect.top + 24, ssWrite.str().c_str(), ssWrite.str().length());

            // Sub Stats / IOPS
            SelectObject(memDC, g_hFontSmall);
            SetTextColor(memDC, COLOR_PURPLE);
            std::wstringstream ssWriteSub;
            if (g_cards[i].write_std > 0) ssWriteSub << L"±" << std::fixed << std::setprecision(2) << g_cards[i].write_std << L" ";
            if (g_cards[i].has_iops && g_cards[i].write_iops > 0) ssWriteSub << L"[" << (int)g_cards[i].write_iops << L" IOPS]";
            TextOutW(memDC, writeRect.left + 160, writeRect.top + 32, ssWriteSub.str().c_str(), ssWriteSub.str().length());
        }

        // Status bar area (Bottom)
        RECT statusRect = { 16, clientRect.bottom - 44, clientRect.right - 16, clientRect.bottom - 12 };
        FillRect(memDC, &statusRect, g_hBrushCard);
        
        SelectObject(memDC, g_hFontMain);
        SetTextColor(memDC, g_isRunning ? COLOR_CYAN : COLOR_TEXT_MAIN);
        TextOutW(memDC, statusRect.left + 16, statusRect.top + 6, g_statusText.c_str(), g_statusText.length());

        // Copy buffer to screen
        BitBlt(hdc, 0, 0, clientRect.right, clientRect.bottom, memDC, 0, 0, SRCCOPY);
        DeleteObject(memBmp);
        DeleteDC(memDC);
        EndPaint(hWnd, &ps);
        break;
    }

    case WM_DESTROY:
        if (g_workerThread.joinable()) {
            g_stopFlag = 1;
            g_workerThread.join();
        }
        DeleteObject(g_hFontMain);
        DeleteObject(g_hFontBold);
        DeleteObject(g_hFontNumber);
        DeleteObject(g_hFontSmall);
        DeleteObject(g_hBrushBg);
        DeleteObject(g_hBrushCard);
        DeleteObject(g_hBrushActive);
        PostQuitMessage(0);
        break;

    default:
        return DefWindowProcW(hWnd, msg, wParam, lParam);
    }
    return 0;
}

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE, LPSTR, int nCmdShow) {
    INITCOMMONCONTROLSEX icex;
    icex.dwSize = sizeof(INITCOMMONCONTROLSEX);
    icex.dwICC = ICC_WIN95_CLASSES | ICC_STANDARD_CLASSES;
    InitCommonControlsEx(&icex);

    WNDCLASSEXW wc = {0};
    wc.cbSize = sizeof(WNDCLASSEXW);
    wc.style = CS_HREDRAW | CS_VREDRAW;
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInstance;
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
    wc.lpszClassName = L"QuickDiskBenchNativeGUIClass";
    wc.hIcon = LoadIcon(NULL, IDI_APPLICATION);

    if (!RegisterClassExW(&wc)) return 1;

    g_hWnd = CreateWindowExW(
        0,
        wc.lpszClassName,
        L"QuickDiskBench 2.0 - Native Storage Benchmark (Cache Modes & Statistics)",
        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
        CW_USEDEFAULT, CW_USEDEFAULT,
        910, 480,
        NULL, NULL, hInstance, NULL
    );

    if (!g_hWnd) return 1;

    ShowWindow(g_hWnd, nCmdShow);
    UpdateWindow(g_hWnd);

    MSG msg;
    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }

    return (int)msg.wParam;
}
