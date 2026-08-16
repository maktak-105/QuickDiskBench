#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <wininet.h>
#include <string>
#include <thread>
#include <chrono>

#pragma comment(lib, "wininet.lib")
#pragma comment(lib, "shell32.lib")

// Check if http://127.0.0.1:8000 is accessible
bool IsServerAlive() {
    HINTERNET hInternet = InternetOpenW(L"QuickDiskBenchLauncher", INTERNET_OPEN_TYPE_DIRECT, NULL, NULL, 0);
    if (!hInternet) return false;

    DWORD timeout = 500; // 500ms timeout
    InternetSetOptionW(hInternet, INTERNET_OPTION_CONNECT_TIMEOUT, &timeout, sizeof(timeout));
    InternetSetOptionW(hInternet, INTERNET_OPTION_RECEIVE_TIMEOUT, &timeout, sizeof(timeout));

    HINTERNET hConnect = InternetOpenUrlW(
        hInternet,
        L"http://127.0.0.1:8000/api/drives",
        NULL, 0,
        INTERNET_FLAG_RELOAD | INTERNET_FLAG_NO_CACHE_WRITE,
        0
    );

    bool alive = (hConnect != NULL);
    if (hConnect) InternetCloseHandle(hConnect);
    InternetCloseHandle(hInternet);
    return alive;
}

// Start Python FastAPI server silently in background
void StartBackendSilently(const std::wstring& appDir) {
    STARTUPINFOW si = { sizeof(si) };
    PROCESS_INFORMATION pi = { 0 };
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE; // completely hide console window

    std::wstring cmd = L"python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000";

    CreateProcessW(
        NULL,
        &cmd[0],
        NULL, NULL, FALSE,
        CREATE_NO_WINDOW,
        NULL,
        appDir.c_str(),
        &si, &pi
    );

    if (pi.hProcess) CloseHandle(pi.hProcess);
    if (pi.hThread) CloseHandle(pi.hThread);
}

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE, LPSTR, int nCmdShow) {
    wchar_t exePath[MAX_PATH];
    GetModuleFileNameW(NULL, exePath, MAX_PATH);
    std::wstring appDir = exePath;
    size_t lastSlash = appDir.find_last_of(L"\\/");
    if (lastSlash != std::wstring::npos) {
        appDir = appDir.substr(0, lastSlash);
    }

    // 1. Ensure backend is running
    if (!IsServerAlive()) {
        StartBackendSilently(appDir);
        // Wait up to 3 seconds for server to come up
        for (int i = 0; i < 30; ++i) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
            if (IsServerAlive()) break;
        }
    }

    // 2. Launch Dedicated Desktop Window via Edge App Mode (PWA container)
    // Works on all Windows 10 & 11 PCs without address bar or tabs
    std::wstring edgeArgs = L"--app=http://127.0.0.1:8000 --window-size=1100,740 --app-id=QuickDiskBenchApp";
    
    HINSTANCE hRes = ShellExecuteW(
        NULL,
        L"open",
        L"msedge.exe",
        edgeArgs.c_str(),
        NULL,
        SW_SHOWNORMAL
    );

    // Fallback: If msedge.exe somehow fails, open default browser
    if ((INT_PTR)hRes <= 32) {
        ShellExecuteW(NULL, L"open", L"http://127.0.0.1:8000", NULL, NULL, SW_SHOWNORMAL);
    }

    return 0;
}
