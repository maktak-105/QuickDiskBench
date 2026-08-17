# QuickDiskBench
[日本語版 README_jp.md](README_jp.md)

QuickDiskBench is a Windows SSD / HDD / NVMe benchmark tool. It measures sequential and random transfer performance and IOPS using Direct I/O with the Windows OS cache bypassed.

## Using the binary release

If you do not need the source code or Python environment, download the distribution ZIP from GitHub Releases.

- [Latest releases](https://github.com/maktak-105/QuickDiskBench/releases)
- [QuickDiskBench v2.1.1](https://github.com/maktak-105/QuickDiskBench/releases/tag/v2.1.1)
- [Direct download of QuickDiskBench-binary.zip](https://github.com/maktak-105/QuickDiskBench/releases/download/v2.1.1/QuickDiskBench-binary.zip)

The ZIP contains all distribution files in one flat folder.

- `QuickDiskBench.exe` - GUI version
- `QuickDiskBench_cli.exe` - command-line version
- `WebView2Loader.dll` - WebView2 loader
- `index.html` - GUI content
- `benchmark-all-drives.ps1` - script for benchmarking all fixed volumes
- `README.txt` / `README-en.txt` - distribution documentation
- `LICENSE.txt` / `LICENSE-ja.txt` - MIT License files

Run `QuickDiskBench.exe` for the GUI. If WebView2 Runtime is unavailable, install Microsoft Edge WebView2 Runtime (Evergreen). It is normally included with Windows 11, but may require installation on older Windows 10 systems, LTSC, Server, or managed devices.

## CLI usage

```powershell
cd I:\path\to\QuickDiskBench-binary
.\QuickDiskBench_cli.exe --help
.\QuickDiskBench_cli.exe --drive D:\ --size 512 --passes 3
.\QuickDiskBench_cli.exe --drive D:\ --raw --csv result.csv
.\QuickDiskBench_cli.exe --drive D:\ --size 4096 --timeout 120
```

Main options:

- `--drive PATH` - target location, for example `C:\`
- `--size MiB` - temporary test-file size; minimum 64 MiB, default 256 MiB
- `--passes N` - number of repetitions for each test (1-9)
- `--timeout SEC` - per-test timeout; default 60 seconds, range 1-3600
- `--raw` - add Write-Through to reduce the effect of device-side write caching
- `--csv PATH` - save the result summary as CSV

The default timeout is 60 seconds per test. For 4 GiB or larger tests, or when a slow or busy drive reports Win32 error 1460 (timeout), retry with a larger value such as `--timeout 120` or `--timeout 180`.

The GUI provides the same timeout choices in its `Timeout` control: 60, 120, 180, 300, or 600 seconds. When no I/O completes, it displays `Waiting for I/O`; progress is based on completed I/O operations rather than elapsed time, and the chart shows the waiting period as 0 MB/s. After the run, the drive information panel shows the total elapsed measurement time.

## Benchmark all drives

Open PowerShell in the distribution folder and run:

```powershell
cd I:\path\to\QuickDiskBench-binary
.\benchmark-all-drives.ps1
```

Specify size, pass count, and timeout as needed:

```powershell
.\benchmark-all-drives.ps1 -SizeMiB 256 -Passes 2
.\benchmark-all-drives.ps1 -SizeMiB 4096 -TimeoutSec 120
```

If execution policy blocks the script:

```powershell
powershell -ExecutionPolicy Bypass -File .\benchmark-all-drives.ps1
```

The script enumerates fixed volumes and writes a combined summary to `results\summary-YYYYMMDD-HHMMSS.csv`. Close important applications and ensure sufficient free space before running write tests.

## Cache modes

- With cache: `FILE_FLAG_NO_BUFFERING` bypasses the Windows OS cache while allowing device hardware cache.
- Without cache: `FILE_FLAG_NO_BUFFERING` is combined with `FILE_FLAG_WRITE_THROUGH` to reduce the effect of device hardware cache.

Results vary with drive temperature, free space, power settings, connection method, background activity, and firmware.

## Running from source

```powershell
python -m pip install -r requirements.txt
python main.py
```

The binary release is recommended for normal use. Building the native version requires LLVM-MinGW for Windows and the WebView2 SDK.

## License

This project is provided under the MIT License. See [`dist/documents/LICENSE.txt`](dist/documents/LICENSE.txt) for the English original and [`dist/documents/LICENSE-ja.txt`](dist/documents/LICENSE-ja.txt) for the Japanese reference translation.

## Disclaimer

This software is provided as-is. The author assumes no responsibility for write tests, measurement results, data loss, system failures, or hardware damage. Always back up important data before use.

## Design Philosophy: Focusing on Practical Stability

While standard benchmarks excel at measuring peak burst performance, real-world workloads—such as loading large local LLM models or intensive data processing—heavily rely on sustained speed and consistency.

QuickDiskBench was developed to quickly diagnose drive performance under practical conditions, born from real troubleshooting with local AI environments.

- **Average & Standard Deviation:** Evaluates practical throughput and stability by calculating the average speed and variance across multiple rapid runs.
- **Direct I/O (Cache-Bypass Mode):** Bypasses OS/controller cache buffering to help observe the drive's baseline performance under continuous load.
- **Time-Efficient Diagnostics:** Quickly provides actionable diagnostic data without prolonged wait times.
