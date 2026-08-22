# QuickDiskBench — About

[日本語版 about_jp.md](about_jp.md)

## Version

Ver. v2.1.1

## Concept

A Windows SSD/HDD/NVMe benchmark tool focused on practical, sustained
throughput and consistency rather than peak burst numbers, using Direct
I/O with the Windows OS cache bypassed.

## Development environment

- C++17 (MinGW-w64 / g++, WinLibs MCF UCRT)
- WebView2 (Microsoft Edge WebView2 Runtime)
- Win32 API (overlapped/async I/O via `FILE_FLAG_NO_BUFFERING` /
  `FILE_FLAG_WRITE_THROUGH`)

No third-party C++ library dependencies. The frontend (HTML/CSS/JS) is
framework-free.

## Status: how the Python and C++ versions relate

Unlike some other Quick-series apps, `python/browser/main.py` is **not** an
independent prototype implementation. It is a FastAPI server that serves
the same `templates/index.html` UI in a browser and, for the actual disk
I/O measurement, loads `core/native/engine_x64.dll` (the same C++ engine
built for the native app) via `ctypes` — see `core/benchmark.py`. If that
DLL is not present, it falls back to a pure-Python implementation
(`python/browser/core/win32_io.py`'s `Win32DirectIO`) so `python python/browser/main.py` still runs
without a native build. The shipped product is `QuickDiskBench.exe`
(C++17 + WebView2, statically linked); `python/browser/main.py` is a
development/from-source way to run the same UI, not a separate product.

## Author

GitHub: [maktak-105](https://github.com/maktak-105)

## Disclaimer

QuickDiskBench is an independent disk benchmark application and is not
affiliated with or endorsed by any third-party benchmark software or
hardware vendor.
