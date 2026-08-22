# QuickDiskBench Specification

[日本語版 spec_jp.md](spec_jp.md)

## 1. Overview

- **Name**: QuickDiskBench
- **Purpose**: A Windows SSD/HDD/NVMe benchmark tool measuring sequential/random transfer speed and IOPS using Direct I/O with the Windows OS cache bypassed.
- **Target OS**: Windows 10 / 11 (64-bit)
- **Implementation**: C++17 (MinGW-w64) + WebView2 + HTML/CSS/vanilla JS
- **Distribution**: GitHub Releases ZIP (flat layout)
- **Version**: v2.1.1

`python/browser/main.py` is not an independent Python prototype; it's a FastAPI
browser version that loads `core/native/engine_x64.dll` (the same C++
engine as the shipped app) via `ctypes`, falling back to a pure-Python
implementation only when that DLL isn't built. See [`about.md`](about.md)
for details.

## 2. Architecture

```text
[HTML/CSS/JS (WebView2)]  <-WebMessage(JSON)->  [webview_main.cpp]  <-direct call->  [engine.cpp]
```

- `engine.cpp` / `engine_x64.dll`: the Direct I/O measurement core using overlapped/async I/O. GUI-independent, shared by the CLI build and `python/browser/main.py` (via `ctypes`).
- `webview_main.cpp`: creates the Win32 window, initializes WebView2, relays JSON messages.
- Frontend: framework-free, bundled into one HTML by `bundle_html.py`.

## 3. Screen layout

| Area | Content |
| --- | --- |
| Header | Drive/size/pass-count/mode/timeout selection; language, CSV export, and Help buttons stacked on the right |
| Main | Transfer-speed chart, drive info panel (manufacturer/model, total elapsed time) |
| Status | Progress based on completed I/O count, "waiting for I/O" indicator |

## 4. Feature list

| # | Feature | Description |
| --- | --- | --- |
| 1 | Drive selection | Choose the target drive/path |
| 2 | Test settings | Size (default 256MiB, min 64MiB), passes (1-9), with/without cache, timeout (60/120/180/300/600s) |
| 3 | Direct I/O measurement | `FILE_FLAG_NO_BUFFERING` bypasses the OS cache; "without cache" mode adds `FILE_FLAG_WRITE_THROUGH` to also reduce device-side cache effects |
| 4 | Average & std. deviation | Computed across multiple passes to show throughput stability |
| 5 | Progress reporting | Based on completed I/O operations, not elapsed time; shows 0 MB/s while waiting for I/O |
| 6 | CSV export | Saves a result summary (GUI and CLI) |
| 7 | Benchmark all drives | `benchmark-all-drives.ps1` enumerates fixed volumes and writes a combined summary CSV under `results` |
| 8 | Language toggle | Japanese/English via a header button |
| 9 | CLI | `QuickDiskBench_cli.exe --drive/--size/--passes/--timeout/--raw/--csv` |

## 5. Processing flow

1. The user selects a drive and settings, then starts the test.
2. `webview_main.cpp` asks the engine to run the test, forwarding progress callbacks to JS.
3. Results from each test are aggregated (average, standard deviation).
4. After all tests complete, total elapsed time is shown in the drive info panel.

## 6. Output format notes

- **CSV**: result summary with drive, test type, speed, and IOPS.
- **All-drives CSV**: aggregated into `results\summary-YYYYMMDD-HHMMSS.csv`.

## 7. Performance / timeout

- Default per-test timeout is 60 seconds. The CLI's `--timeout` and the all-drives script's `-TimeoutSec` extend it to 1-3600 seconds.
- Retry with a larger timeout if a slow/busy drive reports Win32 error 1460 (timeout) on 4 GiB+ tests.

## 8. Planned work

- No specific plans documented at this time.
