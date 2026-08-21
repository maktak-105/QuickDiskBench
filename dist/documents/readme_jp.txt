QuickDiskBench - 配布用 README
配布パッケージ  v2.1.1

QuickDiskBench は、Windows向けの高速ディスクベンチマークツールです。
Windows OSキャッシュをバイパスしたDirect I/O測定に対応し、ストレージ側のハードウェアキャッシュを使用するモードと、その影響を抑えるモードを選択できます。

GitHubリポジトリ
-----------------
https://github.com/maktak-105/QuickDiskBench

配布用Release
-------------
最新版の配布ZIPはGitHub Releasesから取得できます。
https://github.com/maktak-105/QuickDiskBench/releases
Releaseページで `QuickDiskBench-binary.zip` をダウンロードし、任意のフォルダへ展開してください。
ZIP内のすべての配布ファイルは、サブフォルダを作らず同じフォルダに置かれています。

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
1. 配布ZIPを展開します。
2. `QuickDiskBench.exe` を実行します。
3. 測定対象ドライブ、測定サイズ、回数、モード、制限時間を選択します。
4. 言語切替、CSV出力、ヘルプはヘッダー右端の縦並びボタンから操作できます。ヘルプ末尾に作者画像があります。
5. 測定中は対象ドライブへの負荷が高くなるため、重要な処理を終了してから実行してください。

コマンドライン版は `QuickDiskBench_cli.exe` です。

CLIの使い方
------------
PowerShellで展開先フォルダへ移動してから、`QuickDiskBench_cli.exe --help` で全オプションを表示できます。主な例:

- `cd I:\path\to\QuickDiskBench-binary`
- `.\QuickDiskBench_cli.exe --drive D:\ --size 512 --passes 3`
- `.\QuickDiskBench_cli.exe --drive D:\ --raw --csv result.csv`
- `.\QuickDiskBench_cli.exe --drive D:\ --size 4096 --timeout 120`
- `.\benchmark-all-drives.ps1 -SizeMiB 256 -Passes 2`

タイムアウト
------------
各テストのタイムアウトは既定60秒です。CLI版では `--timeout SEC` で1～3600秒の範囲に変更できます。
4GB以上の測定や、低速・高負荷状態のドライブでWin32エラー1460（タイムアウト）が出る場合は、
`--timeout 120` や `--timeout 180` のように値を増やして再実行してください。GUI版も既定60秒で動作します。
全ドライブ測定スクリプトでは `-TimeoutSec 120` のように指定できます。
GUI版では上部の「制限時間」から60 / 120 / 180 / 300 / 600秒を選択できます。I/O完了がない場合は「I/O待機中」と表示され、進捗率は完了したI/O数を基準に更新されます。測定完了後は、ドライブ情報パネルの下部に全テストの実計測時間が表示されます。

`benchmark-all-drives.ps1` は認識されている固定ボリューム（SSD/HDD）を列挙し、各ドライブをCLIで測定します。
全ドライブの測定結果を1つの集計CSVファイルとして `results` フォルダに保存します。
PowerShellではカレントフォルダのスクリプトを実行するため、次のように `.` と `\\` を付けて実行してください。

`.\benchmark-all-drives.ps1`

実行ポリシーで拒否される場合は、次のコマンドを使用してください。

`powershell -ExecutionPolicy Bypass -File .\benchmark-all-drives.ps1`

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
- `readme_jp.txt` - この配布ファイルの説明書
- `readme.txt` - 英語版の配布ファイル説明書
- `LICENSE.txt` - MIT License英語原文
- `LICENSE_jp.txt` - MIT License日本語参考訳

SHA-256
-------
119FD0368B0BE58160DD314CC52DDA437E84D6BA2FF3EFA3B63A6C8B9FE4A828  QuickDiskBench.exe
4528BEFAE3FB83E81417DDAD62C9360EBE019C402B5E6B37FC03B0341E183D81  QuickDiskBench_cli.exe
A9A09232C25805323D4CFB3FC8F545A190A9C8A99C93262EA99D0B88DF99EC90  WebView2Loader.dll

ライセンス
----------
このソフトウェアのソースコードはMIT Licenseで提供されます。MIT Licenseの全文は、
同梱の `LICENSE.txt`（英語原文）または `LICENSE_jp.txt`（日本語参考訳）を確認してください。

免責事項
--------
本ソフトウェアは現状有姿で提供されます。本ソフトウェアの使用、測定結果、書き込みテスト、データ消失、システム障害、ハードウェア故障、その他の損害について、作者は責任を負いません。重要なデータは必ずバックアップしてから使用してください。

QuickDiskBench is an independent disk benchmark application and is not affiliated with or endorsed by any third-party benchmark software or hardware vendor.

