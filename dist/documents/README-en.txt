QuickDiskBench - Distribution README

QuickDiskBench is a Windows disk benchmark tool for SSDs and HDDs.
It supports Direct I/O measurements that bypass the Windows OS cache, with modes that either allow or reduce the effect of storage-device hardware caching.

GitHub repository
-----------------
https://github.com/maktak-105/QuickDiskBench

Binary release
--------------
Download the latest package from GitHub Releases:
https://github.com/maktak-105/QuickDiskBench/releases
On the release page, download `QuickDiskBench-binary.zip` and extract it. All distribution files are placed in the same folder without subfolders.

Requirements
------------
- Windows 10 / 11 (64-bit)
- Microsoft Edge WebView2 Runtime
- Sufficient free space on the target drive for write tests
- Administrator privileges may be required for some drives or environments

About WebView2 Runtime
----------------------
Windows 11 normally includes WebView2 Runtime as part of the operating system.
Many Windows 10 systems also have it installed, but it may be missing on older systems, LTSC, Windows Server, or managed corporate devices.
If the Runtime is missing, install Microsoft Edge WebView2 Runtime (Evergreen) from Microsoft.
`WebView2Loader.dll` is only the loader connecting the application to the Runtime; it is not the Runtime itself.

Usage
-----
1. Extract the distribution ZIP.
2. Run `QuickDiskBench.exe` for the graphical interface.
3. Select the target drive, test size, pass count, and cache mode.
4. Close important applications before testing because disk load can be high.

The command-line version is `QuickDiskBench_cli.exe`.
Open PowerShell in the extracted folder and run `QuickDiskBench_cli.exe --help` to see all options.

Examples:
- `cd I:\path\to\QuickDiskBench-binary`
- `.\QuickDiskBench_cli.exe --drive D:\ --size 512 --passes 3`
- `.\QuickDiskBench_cli.exe --drive D:\ --raw --csv result.csv`
- `.\QuickDiskBench_cli.exe --drive D:\ --size 4096 --timeout 120`
- `.\benchmark-all-drives.ps1 -SizeMiB 256 -Passes 2`

Timeout
-------
The default timeout is 60 seconds per test. The CLI accepts `--timeout SEC` from 1 to 3600 seconds.
For 4 GiB or larger tests, or when a slow or busy drive reports Win32 error 1460 (timeout),
retry with a larger value such as `--timeout 120` or `--timeout 180`. The GUI also uses a 60-second default.
For the all-drives script, use `-TimeoutSec 120` to increase the timeout.
In the GUI, select 60 / 120 / 180 / 300 / 600 seconds from the Timeout control. When no I/O completes, the status shows "Waiting for I/O" and progress is based on completed I/O operations. After the run, the drive information panel shows the total elapsed measurement time.

`benchmark-all-drives.ps1` enumerates fixed volumes and benchmarks them one by one.
All drive results are combined into one aggregate CSV file under the `results` folder.
In PowerShell, run a script from the current folder with `.\`:

`.\benchmark-all-drives.ps1`

If execution policy blocks the script, use:

`powershell -ExecutionPolicy Bypass -File .\benchmark-all-drives.ps1`

Cache modes
-----------
- With cache: Windows OS caching is bypassed with `FILE_FLAG_NO_BUFFERING`; device hardware caching remains available.
- Without cache: Windows OS caching remains bypassed, and `FILE_FLAG_WRITE_THROUGH` is also used to reduce the effect of device hardware caching.

Distribution files
------------------
- `QuickDiskBench.exe` - WebView2 GUI application
- `QuickDiskBench_cli.exe` - command-line application
- `WebView2Loader.dll` - WebView2 loader
- `index.html` - GUI content
- `benchmark-all-drives.ps1` - script for benchmarking all fixed volumes
- `README.txt` - Japanese distribution README
- `README-en.txt` - English distribution README
- `LICENSE.txt` - MIT License, English original
- `LICENSE-ja.txt` - MIT License, Japanese reference translation

License
-------
This software is provided under the MIT License.
See `LICENSE.txt` for the original license text and `LICENSE-ja.txt` for a Japanese reference translation.

Disclaimer
----------
This software is provided as-is. The author assumes no responsibility for measurement results, write tests, data loss, system failures, hardware damage, or any other losses. Always back up important data before use.

QuickDiskBench is an independent disk benchmark application and is not affiliated with or endorsed by any third-party benchmark software or hardware vendor.

