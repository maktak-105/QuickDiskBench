# QuickDiskBench Changelog
[日本語版 HISTORY_jp.md](HISTORY_jp.md)

This file records the major changes in each public version.

## Versioning rules

- First digit (for example, `1.0.0` to `2.0.0`): new features
- Second digit (for example, `1.0.0` to `1.1.0`): bug fixes
- Third digit (for example, `1.1.0` to `1.1.1`): other changes, such as documentation updates

## 2.1.1 (in preparation)

### Distribution and build

- Organized distribution files under `dist/binary` and documentation and licenses under `dist/documents`.
- Changed release ZIP creation to use a flat layout without subfolders.
- The ZIP contains `README.txt`, `README-en.txt`, `LICENSE.txt`, and `LICENSE-ja.txt`; `README.md` is not included.
- Split the repository root documentation into the English `README.md` and Japanese `README_jp.md`, with a link to the Japanese version at the top of the English file.
- Updated the Windows GitHub Actions build for MinGW preference, UTF-8 logs, and Windows-specific compilation compatibility.
- Improved CLI build failure detection and error reporting.
- `build_native.py` now finds `windres.exe` next to the detected compiler when it is not on `PATH`.
- `bundle_html.py` embeds relative images as data URIs so WebView2 `NavigateToString` can display them.

### GUI

- Stacked the language, CSV export, and Help buttons on the right side of the header in both Japanese and English.
- Added the author image at the bottom of the Help dialog.
- Reduced the default window height from 900 to 780 so the transfer-speed chart no longer sits above unused empty space.

### Benchmark fixes

- Fixed asynchronous RND4K I/O failures, wait failures, and timeouts being treated as successful measurements.
- Increased the random-I/O safety timeout from 3 to 60 seconds to reduce false 0.00 results on slow or busy drives.
- Unified the default timeout at 60 seconds for every test. The CLI `--timeout` option and the all-drives script `-TimeoutSec` option can extend it up to 3600 seconds.
- Added Win32 I/O error codes to CLI failure messages.
- Changed the GUI to report measurement failures instead of showing them as successful 0.00 results.
- Added GUI timeout choices of 60, 120, 180, 300, and 600 seconds.
- Changed progress reporting to use completed I/O operations instead of elapsed time.
- Added an I/O-waiting status and 0 MB/s chart updates while no I/O completes.
- Added physical-drive manufacturer and model lookup to the GUI drive information panel.
- Added total elapsed measurement time to the GUI drive information panel.
- Verified RND4K WRITE locally at 512 MiB, 1 GiB, and 2 GiB with one pass.

## 1.0.0 (2026-08-16)

- Initial QuickDiskBench public release.
- Provided Windows GUI and CLI versions.
- Implemented Direct I/O benchmarking that bypasses the OS cache.
- Added sequential I/O, RND4K Q32T1, and RND4K Q1T1 speed and IOPS measurements.
- Added pass-count selection, write-through mode, CSV export, and an all-drives measurement script.
- Added binary distribution ZIP packaging for GitHub Releases.
