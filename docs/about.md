# QuickDiskBench — About

## Version

Ver. v3.0.0

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

## Prototypes

`proto/browser/main.py` is a development and verification prototype (FastAPI browser version).
It serves the `src/ui/index.html` UI in a browser and loads `dist/engine_x64.dll` (C++ engine)
via `ctypes` for disk I/O measurements, falling back to a pure-Python implementation when the DLL is not present.
The shipped product is `dist/QuickDiskBench.exe` (C++17 + WebView2, statically linked).

## Author

GitHub: [maktak-105](https://github.com/maktak-105)

## Disclaimer

QuickDiskBench is an independent disk benchmark application and is not
affiliated with or endorsed by any third-party benchmark software or
hardware vendor.
