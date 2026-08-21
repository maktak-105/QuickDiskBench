# 開発環境

[English environment.md](environment.md)

## 実行環境

- Windows 10 / 11（64bit）
- Microsoft Edge WebView2 Runtime（実行時）
- Python 3.11+（`python main.py`をソースから実行する場合、およびビルドスクリプト用）

## セットアップ

### MinGWツールチェイン

WinLibs（MCF threads / UCRT runtime）を使用します。

```powershell
winget install --id BrechtSanders.WinLibs.MCF.UCRT --exact --source winget
```

標準的なインストール先:

```text
%LOCALAPPDATA%\Microsoft\WinGet\Packages\BrechtSanders.WinLibs.MCF.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe\mingw64\bin
```

`build_native.py`はこの場所を自動検索し、検出したコンパイラと同じフォルダの`windres.exe`も
使うため、プロジェクトのビルドだけならPATH登録は不要です。`g++`/`windres`を直接実行したい
場合のみ、パッケージの`mingw64\bin`を**ユーザー環境変数**のPATHに追加してください
（追加後はターミナル/IDEの再起動が必要）。

### WebView2 SDK

NuGetパッケージ`Microsoft.Web.WebView2`を展開し、ヘッダーを配置します。既定の探索先は
`C:\tools\webview2\build\native\include`。別の場所に置く場合は環境変数`WEBVIEW2_INCLUDE`を
設定してください。

## ソースから起動する場合（Python/FastAPI版）

```powershell
python -m pip install -r requirements.txt
python main.py
```

ネイティブ版と同じUI（`templates/index.html`）をFastAPI経由でブラウザに表示します。
ネイティブビルドとの関係は[`about_jp.md`](about_jp.md)を参照してください——
`core/native/engine_x64.dll`が存在すれば`ctypes`経由でそれをロードし、無ければ
純Python実装にフォールバックします。

## ビルド方法

```powershell
g++ --version
windres --version
python build_native.py
```

### ビルド成果物

| ファイル | 説明 |
| --- | --- |
| `dist/binary/QuickDiskBench.exe` | GUI版 |
| `dist/binary/QuickDiskBench_cli.exe` | CLI版 |
| `dist/binary/WebView2Loader.dll` | WebView2ローダー |
| `dist/binary/index.html` | バンドル済みGUI |
| `dist/binary/benchmark-all-drives.ps1` | 全ドライブ測定スクリプト |

## トラブルシューティング

| 症状 | 原因と対処 |
| --- | --- |
| 大容量・低速ドライブでWin32エラー1460（タイムアウト） | `--timeout`（CLI）や`-TimeoutSec`（全ドライブスクリプト）を増やす、GUIで長めの制限時間を選択する |
| WebView2ウィンドウが開かない | Microsoft Edge WebView2 Runtime (Evergreen)をインストール |
| `g++`/`windres`を直接実行できない | WinLibsの`mingw64\bin`をユーザーPATHに追加しターミナル/IDEを再起動（`build_native.py`自体には不要） |

## 依存関係

サードパーティC++ライブラリ依存なし。Python/FastAPI版の依存関係は`requirements.txt`を参照してください。
