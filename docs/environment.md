# Development Environment

## Runtime requirements
## Runtime Environment

- Windows 10 / 11 (64-bit)
- Microsoft Edge WebView2 Runtime (runtime)
- Python 3.11+ (for running `python python/browser/main.py` from source, and for build scripts)
- Microsoft Edge WebView2 Runtime (at runtime)
- Python 3.11+ (for running build scripts)
- Python 3.11+ (for running build scripts and prototype)

## Setup

### MinGW toolchain
### MinGW Toolchain

Uses WinLibs (MCF threads / UCRT runtime):
WinLibs (MCF threads / UCRT runtime) is used.

```powershell
winget install --id BrechtSanders.WinLibs.MCF.UCRT --exact --source winget
```

Standard install location:
Standard installation location:

```text
%LOCALAPPDATA%\Microsoft\WinGet\Packages\BrechtSanders.WinLibs.MCF.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe\mingw64\bin
```

`build_native.py` searches this location automatically and also uses
`scripts/build.py` searches this location automatically and also uses
`windres.exe` next to the detected compiler, so PATH registration isn't
`scripts/build.py` automatically searches this location and also uses
`windres.exe` next to the detected compiler, so PATH registration is not
required just to build the project. Add the package's `mingw64\bin` to
the **user** PATH only if you want to invoke `g++`/`windres` directly
(restart your terminal/IDE afterward).
`scripts/build.py` automatically searches this location and also uses `windres.exe` next to the detected compiler, so PATH registration is not required just to build the project. Add the package's `mingw64\bin` to the **user** PATH only if you want to invoke `g++` / `windres` directly (restart your terminal/IDE afterward).

### WebView2 SDK

Extract the `Microsoft.Web.WebView2` NuGet package and place the headers.
Default search path: `C:\tools\webview2\build\native\include`. Set
`WEBVIEW2_INCLUDE` if installed elsewhere.
Default search path: `C:\tools\webview2\build\native\include`. Set `WEBVIEW2_INCLUDE` if installed elsewhere.

## Running from source (Python/FastAPI version)
## Build Method

```powershell
python -m pip install -r requirements.txt
python -m pip install -r scripts/requirements.txt
python python/browser/main.py
scripts\build.bat
# or python scripts/build.py
```

This serves the same UI (`templates/index.html`) via FastAPI in a
This serves the same UI (`src/ui/index.html`) via FastAPI in a
browser. See [`about.md`](about.md) for how it relates to the native
build — it loads `core/native/engine_x64.dll` via `ctypes` when
build — it loads `dist/engine_x64.dll` via `ctypes` when
available, falling back to a pure-Python implementation otherwise.
### Build Steps Breakdown (scripts/build.py)

## Build method
1. Compiler detection (`g++` -> falls back to `clang++` if not found)
2. `scripts/bundle_html.py` bundles `src/ui/` into a single `index.html` placed under `build/intermediate/` (images inlined as data URIs, HTML/CSS/JS self-contained)
3. `windres` compiles resources (icon, version info, embedded HTML) into `build/intermediate/QuickDiskBench_res.o`
4. Builds `dist/engine_x64.dll` from `src/engine/engine.cpp`
5. Statically links `src/app/main_gui.cpp` + `src/engine/engine.cpp` + resources into `dist/QuickDiskBench.exe`
6. Compiles CLI tool `dist/QuickDiskBench_cli.exe` from `src/cli/main_cli.cpp` + `src/engine/engine.cpp`
7. Copies `WebView2Loader.dll` and `scripts/benchmark-all-drives.ps1` to `dist/`

```powershell
g++ --version
windres --version
python build_native.py
scripts\build.bat
# or python scripts/build.py
```
### Build Output

### Build output

| File | Description |
| --- | --- |
| `dist/binary/QuickDiskBench.exe` | GUI version |
| `dist/binary/QuickDiskBench_cli.exe` | CLI version |
| `dist/binary/WebView2Loader.dll` | WebView2 loader |
| `dist/binary/index.html` | Bundled GUI |
| `dist/binary/benchmark-all-drives.ps1` | All-drives benchmark script |
| `dist/QuickDiskBench.exe` | GUI version (self-contained embedded HTML) |
| `dist/QuickDiskBench_cli.exe` | CLI version |
| `dist/engine_x64.dll` | C++ native DLL |
| `dist/WebView2Loader.dll` | WebView2 loader |
| `dist/benchmark-all-drives.ps1` | All-drives benchmark script |

## Running the Prototype

To run the development/verification prototype (FastAPI browser version):

```powershell
python -m pip install -r scripts/requirements.txt
python proto/browser/main.py
```

This serves the same UI (`src/ui/index.html`) via FastAPI in a browser. See [`about.md`](about.md) for how it relates to the native build — it loads `dist/engine_x64.dll` via `ctypes` when available, falling back to a pure-Python implementation otherwise.

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| Win32 error 1460 (timeout) on large/slow drives | Increase `--timeout` (CLI) or `-TimeoutSec` (all-drives script), or select a longer timeout in the GUI |
| Win32 error 1460 (timeout) on large or slow drives | Increase `--timeout` (CLI) or `-TimeoutSec` (all-drives script), or select a longer timeout in GUI |
| WebView2 window fails to open | Install Microsoft Edge WebView2 Runtime (Evergreen) |
| `g++`/`windres` not found when invoked directly | Add WinLibs `mingw64\bin` to user PATH and restart the terminal/IDE — not needed for `build_native.py` itself |
| `g++`/`windres` not found when invoked directly | Add WinLibs `mingw64\bin` to user PATH and restart the terminal/IDE — not needed for `scripts/build.py` itself |
| Cannot invoke `g++` / `windres` directly | Add WinLibs `mingw64\bin` to user PATH and restart terminal/IDE (not needed for `scripts/build.py`) |

## Dependencies

No third-party C++ library dependencies. See `requirements.txt` for the
Python/FastAPI version's dependencies.
No third-party C++ library dependencies. See `scripts/requirements.txt` for the
Python/FastAPI dependencies.
No third-party C++ library dependencies. Frontend (HTML/CSS/JS) is framework-free.
No third-party C++ library dependencies. The frontend (HTML/CSS/JS) is framework-free.
Python packages for the prototype are listed in `scripts/requirements.txt`.
