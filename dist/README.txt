QuickDiskBench - 配布用 README

QuickDiskBench は、Windows向けの高速ディスクベンチマークツールです。
Windows OSキャッシュをバイパスしたDirect I/O測定に対応し、ストレージ側のハードウェアキャッシュを使用するモードと、その影響を抑えるモードを選択できます。

GitHubリポジトリ
-----------------
https://github.com/maktak-105/QuickDiskBench

動作環境
--------
- Windows 10 / 11 (64-bit)
- Microsoft Edge WebView2 Runtime
- 書き込みテストを実行する場合、対象ドライブに十分な空き容量が必要
- 管理者権限が必要になる環境やドライブがあります

WebView2 Runtimeについて
------------------------
Windows 11では通常、WebView2 RuntimeはOSに同梱されているため、追加インストールは不要です。
Windows 10でも多くの端末には導入済みですが、古い環境、LTSC、Windows Server、企業管理端末などでは入っていない場合があります。
起動時にRuntimeが見つからない場合は、Microsoft公式のMicrosoft Edge WebView2 Runtime (Evergreen)をインストールしてください。
`WebView2Loader.dll` はアプリとRuntimeを接続するローダーであり、Runtime本体ではありません。

起動方法
--------
1. 配布ファイルを同じフォルダに展開します。
2. `QuickDiskBench.exe` を実行します。
3. 測定対象ドライブ、測定サイズ、回数、モードを選択します。
4. 測定中は対象ドライブへの負荷が高くなるため、重要な処理を終了してから実行してください。

コマンドライン版は `QuickDiskBench_cli.exe` です。

CLIの使い方
------------
`QuickDiskBench_cli.exe --help` で全オプションを表示できます。主な例:

- `QuickDiskBench_cli.exe --drive D:\ --size 512 --passes 3`
- `QuickDiskBench_cli.exe --drive D:\ --raw --csv result.csv`
- `benchmark-all-drives.ps1 -SizeMiB 256 -Passes 2`

`benchmark-all-drives.ps1` は認識されている固定ボリューム（SSD/HDD）を列挙し、各ドライブをCLIで測定します。
全ドライブの測定結果を1つの集計CSVファイルとして `results` フォルダに保存します。
PowerShellではカレントフォルダのスクリプトを実行するため、次のように `.` と `\\` を付けて実行してください。

`.\benchmark-all-drives.ps1`

実行ポリシーで拒否される場合は、次のコマンドを使用してください。

`powershell -ExecutionPolicy Bypass -File .\benchmark-all-drives.ps1`
PowerShellの実行ポリシーでブロックされる場合は、`powershell -ExecutionPolicy Bypass -File .\benchmark-all-drives.ps1` を使用してください。

測定モード
----------
- キャッシュあり: `FILE_FLAG_NO_BUFFERING` によりWindows OSキャッシュは使用せず、ストレージ側のハードウェアキャッシュは使用可能です。
- キャッシュなし: OSキャッシュを使用しないまま、`FILE_FLAG_WRITE_THROUGH` を追加し、ハードウェアキャッシュの影響も抑えます。

測定結果は、ドライブの状態、空き容量、温度、電源設定、バックグラウンド処理、ファームウェア、接続方式などにより変動します。

配布ファイル
------------
- `QuickDiskBench.exe` - WebView2 GUI版
- `QuickDiskBench_cli.exe` - コマンドライン版
- `WebView2Loader.dll` - WebView2ローダー
- `index.html` - GUIに使用するUI
- `benchmark-all-drives.ps1` - 全固定ドライブを検出してCLI測定するスクリプト
- `README.txt` - この配布ファイルの説明書
- `README-en.txt` - 英語版の配布ファイル説明書
- `LICENSE-en.txt` - MIT License英語原文
- `LICENSE-ja.txt` - MIT License日本語参考訳

SHA-256
-------
6F08B803E450697C9736FECF611C77C2038E6DB8812FC922E05F7B6434077E03  QuickDiskBench.exe
78C6B38D02D66153C0FD2EC7497EBD0A55DAB9999F0F3281430DB8194024F0C9  QuickDiskBench_cli.exe
465A7DDFB3A0DA4C3965DAF2AD6AC7548513F42329B58AEBC337311C10EA0A6F  WebView2Loader.dll

ライセンス
----------
このソフトウェアのソースコードはMIT Licenseで提供されます。MIT Licenseの全文は、
リポジトリ直下のLICENSE-en.txt（英語原文）またはLICENSE-ja.txt（日本語参考訳）を確認してください。

免責事項
--------
本ソフトウェアは現状有姿で提供されます。本ソフトウェアの使用、測定結果、書き込みテスト、データ消失、システム障害、ハードウェア故障、その他の損害について、作者は責任を負いません。重要なデータは必ずバックアップしてから使用してください。

QuickDiskBench is an independent disk benchmark application and is not affiliated with or endorsed by any third-party benchmark software or hardware vendor.

