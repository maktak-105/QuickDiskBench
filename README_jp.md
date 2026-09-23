# QuickDiskBench

<p align="center">
  <img src="assets/quickdiskbench-gui-ja.png" alt="QuickDiskBench 日本語GUI" width="720">
</p>

Windows向けのSSD / HDD / NVMeベンチマークツールです。WindowsのOSキャッシュを常にバイパスしたDirect I/Oで、シーケンシャルおよびランダムアクセスの速度とIOPSを測定します。

## 配布版を使う

ソースコードやPython環境がない場合は、GitHub Releasesから配布用ZIPをダウンロードしてください。

- [最新版の配布ページ](https://github.com/maktak-105/QuickDiskBench/releases)
- [QuickDiskBench v3.0.0](https://github.com/maktak-105/QuickDiskBench/releases/tag/v3.0.0)
- [QuickDiskBench-binary.zipを直接ダウンロード](https://github.com/maktak-105/QuickDiskBench/releases/download/v3.0.0/QuickDiskBench-binary.zip)

ZIPを展開すると、すべての配布ファイルが同じフォルダに入ります。

- `QuickDiskBench.exe` - GUI版（自己完結HTML内蔵）
- `QuickDiskBench_cli.exe` - コマンドライン版
- `WebView2Loader.dll` - WebView2接続用ローダー
- `benchmark-all-drives.ps1` - 固定ドライブ一括測定スクリプト
- `readme.txt` / `readme_jp.txt` - 使用説明書
- `history.txt` / `history_jp.txt` - 更新履歴
- `LICENSE.txt` / `LICENSE_jp.txt` - MIT License

### 完全性の確認（SHA-256）

配布用ZIPおよび各バイナリの公式SHA-256チェックサムは、CI（GitHub Actions）のビルド時に自動算出され、GitHub Releasesの各リリースに `SHA256SUMS.txt` として添付されています。ダウンロード後の整合性確認には `SHA256SUMS.txt` を参照してください。

```powershell
Get-FileHash .\QuickDiskBench-binary.zip -Algorithm SHA256
```

GUI版は `QuickDiskBench.exe` を実行します。言語切替、CSV出力、ヘルプボタンはヘッダー右端に縦に並び、日本語・英語のどちらでも同じ配置です。作者ワッペンはヘルプダイアログ上部の「バージョン情報」ボタンから開く別ダイアログに表示されます。WebView2 Runtimeがない場合は、Microsoft Edge WebView2 Runtime (Evergreen)をインストールしてください。Windows 11には通常含まれていますが、Windows 10の古い環境、LTSC、Server、管理端末では追加導入が必要な場合があります。

## CLIの使い方

```powershell
cd I:\path\to\QuickDiskBench-binary
.\QuickDiskBench_cli.exe --help
.\QuickDiskBench_cli.exe --drive D:\ --size 512 --passes 3
.\QuickDiskBench_cli.exe --drive D:\ --raw --csv result.csv
.\QuickDiskBench_cli.exe --drive D:\ --size 4096 --timeout 120
```

主なオプション：

- `--drive PATH` - 測定先（例：`C:\`）
- `--size MiB` - 一時測定ファイルのサイズ。最小64 MiB、既定256 MiB
- `--passes N` - 各テストの反復回数（1～9）
- `--timeout SEC` - 各テストのタイムアウト秒数。既定60秒、1～3600秒
- `--raw` - Write-Throughを追加し、デバイス側書き込みキャッシュの影響を抑制
- `--csv PATH` - 結果サマリーをCSV保存

各テストのタイムアウトは既定60秒です。4GB以上の測定や、低速・高負荷状態のドライブでWin32エラー1460（タイムアウト）が出る場合は、`--timeout 120`や`--timeout 180`のように値を増やして再実行してください。GUI版も既定60秒で動作します。

GUI版では上部の「制限時間」から60 / 120 / 180 / 300 / 600秒を選択できます。測定中にI/O完了がない場合は「I/O待機中」と表示され、進捗率は経過時間ではなく完了したI/O数に基づいて更新されます。グラフにも待機中の0 MB/sが反映されるため、ストレージが応答待ちになった状態を確認できます。測定完了後は、ドライブ情報パネルの下部に全テストの実計測時間が表示されます。

## 全ドライブを測定する

PowerShellで配布フォルダへ移動し、カレントフォルダを示す` .\`を付けて実行します。

```powershell
cd I:\path\to\QuickDiskBench-binary
.\benchmark-all-drives.ps1
```

サイズと回数を指定する例：

```powershell
.\benchmark-all-drives.ps1 -SizeMiB 256 -Passes 2
# 4GB測定などで時間を延長する場合
.\benchmark-all-drives.ps1 -SizeMiB 4096 -TimeoutSec 120
```

実行ポリシーで拒否される場合：

```powershell
powershell -ExecutionPolicy Bypass -File .\benchmark-all-drives.ps1
```

スクリプトは固定ボリュームを列挙し、各ドライブをCLIで測定します。全ドライブの結果は`results\summary-YYYYMMDD-HHMMSS.csv`という1つのCSVにまとめられます。書き込みテストを行うため、重要な処理を終了し、対象ドライブの空き容量を確保してから実行してください。

## 測定モード

- キャッシュあり：`FILE_FLAG_NO_BUFFERING`でWindows OSキャッシュを使わず、ストレージ側のハードウェアキャッシュは使用可能
- キャッシュなし：OSキャッシュを使わないまま`FILE_FLAG_WRITE_THROUGH`を追加し、ハードウェアキャッシュの影響も抑制

測定値は、ドライブの温度、空き容量、電源設定、接続方式、バックグラウンド処理、ファームウェアなどで変動します。

## ビルド方法

通常の利用にはGitHub Releasesの配布ZIPを推奨します。自分でビルドする場合は以下を用意してください。

### ネイティブ版ビルドに必要なもの

ネイティブ版はMinGW-w64のC++ツールチェーンを使用します。WinLibs（MCF threads、UCRT runtime）のWinGetパッケージ`BrechtSanders.WinLibs.MCF.UCRT`で動作確認しています。

```powershell
winget install --id BrechtSanders.WinLibs.MCF.UCRT --exact --source winget
```

`scripts/build.py` は標準的なWinGetパッケージの場所を自動検索し、検出したコンパイラと同じフォルダの `windres.exe` も使うため、プロジェクトのビルドだけならPATH登録は必須ではありません。`g++` や `windres` を直接実行したい場合は、パッケージ内の `mingw64\bin` を**ユーザー環境変数のPATH**に追加してください。標準的なWinGetインストール先は通常次の場所です。

```text
%LOCALAPPDATA%\Microsoft\WinGet\Packages\BrechtSanders.WinLibs.MCF.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe\mingw64\bin
```

ビルドの実行：

```powershell
scripts\build.bat
# または python scripts/build.py
```

WebView2 SDKのヘッダーは、既定では `C:\tools\webview2\build\native\include` にあるものとして扱います。別の場所にインストールした場合は環境変数 `WEBVIEW2_INCLUDE` を設定してください。

## プロトタイプ（試作版）について

`proto/browser/main.py` は開発・検証用のFastAPIブラウザ版プロトタイプです。

```powershell
python -m pip install -r scripts/requirements.txt
python proto/browser/main.py
```

FastAPIサーバーが同じUI（`src/ui/index.html`）をブラウザへ提供し、実際の測定はC++エンジン `dist/engine_x64.dll` を `ctypes` 経由でロードして実行します。このDLLが未ビルドの場合のみ純Python実装にフォールバックします。詳細は[`docs/about_jp.md`](docs/about_jp.md)を参照してください。

## ライセンス

MIT Licenseです。英語原文は[`LICENSE`](LICENSE)（配布物では[`docs/distribution/LICENSE.txt`](docs/distribution/LICENSE.txt)）、日本語参考訳は[`docs/distribution/LICENSE_jp.txt`](docs/distribution/LICENSE_jp.txt)を確認してください。

## 注意事項

本ソフトウェアは現状有姿で提供されます。書き込みテスト、測定結果、データ消失、システム障害、ハードウェア故障などについて作者は責任を負いません。重要なデータは必ずバックアップしてから使用してください。

## 設計思想：実用的な安定性と再現性の重視

一般的なベンチマークはピーク時の最大性能を測るのに適していますが、ローカルLLMの大規模モデルのロードや連続データ処理など、実際の現場では**「持続的な実効速度」と「動作の安定性（速度ムラの少なさ）」**が重要になります。

QuickDiskBench は、ローカルAI環境のセットアップ時に遭遇したドライブ起因の課題をきっかけに、実務に即したドライブの状態を手軽に診断できるツールを目指して開発されました。

- **平均値と標準偏差（ばらつき）の算出:** 複数回の高速テストから平均値と標準偏差を計算し、速度の安定性・ムラを客観的に把握できます。
- **Direct I/O（キャッシュ無効化モード）:** キャッシュの影響を抑えることで、連続した負荷がかかった際のドライブ本来の挙動を確認できます。
- **短時間での測定:** 待ち時間を大幅に抑え、必要な診断結果を素早く確認できます。
