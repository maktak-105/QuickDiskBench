# Development Environment

[日本語版 environment_jp.md](environment_jp.md)

## Runtime requirements

- Windows 10 / 11 (64-bit)
- Microsoft Edge WebView2 Runtime (runtime)
- Python 3.11+ (for running `python python/browser/main.py` from source, and for build scripts)

## Setup

### MinGW toolchain

Uses WinLibs (MCF threads / UCRT runtime):

```powershell
winget install --id BrechtSanders.WinLibs.MCF.UCRT --exact --source winget
```

Standard install location:

```text
%LOCALAPPDATA%\Microsoft\WinGet\Packages\BrechtSanders.WinLibs.MCF.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe\mingw64\bin
```

`build_native.py` searches this location automatically and also uses
`windres.exe` next to the detected compiler, so PATH registration isn't
required just to build the project. Add the package's `mingw64\bin` to
the **user** PATH only if you want to invoke `g++`/`windres` directly
(restart your terminal/IDE afterward).

### WebView2 SDK

Extract the `Microsoft.Web.WebView2` NuGet package and place the headers.
Default search path: `C:\tools\webview2\build\native\include`. Set
`WEBVIEW2_INCLUDE` if installed elsewhere.

## Running from source (Python/FastAPI version)

```powershell
python -m pip install -r requirements.txt
python python/browser/main.py
```

This serves the same UI (`templates/index.html`) via FastAPI in a
browser. See [`about.md`](about.md) for how it relates to the native
build — it loads `core/native/engine_x64.dll` via `ctypes` when
available, falling back to a pure-Python implementation otherwise.

## Build method

```powershell
g++ --version
windres --version
python build_native.py
```

### Build output

| File | Description |
| --- | --- |
| `dist/binary/QuickDiskBench.exe` | GUI version |
| `dist/binary/QuickDiskBench_cli.exe` | CLI version |
| `dist/binary/WebView2Loader.dll` | WebView2 loader |
| `dist/binary/index.html` | Bundled GUI |
| `dist/binary/benchmark-all-drives.ps1` | All-drives benchmark script |

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| Win32 error 1460 (timeout) on large/slow drives | Increase `--timeout` (CLI) or `-TimeoutSec` (all-drives script), or select a longer timeout in the GUI |
| WebView2 window fails to open | Install Microsoft Edge WebView2 Runtime (Evergreen) |
| `g++`/`windres` not found when invoked directly | Add WinLibs `mingw64\bin` to user PATH and restart the terminal/IDE — not needed for `build_native.py` itself |

## Dependencies

No third-party C++ library dependencies. See `requirements.txt` for the
Python/FastAPI version's dependencies.
