# 開発環境

## 実行環境

- Windows 10 / 11（64bit）
- Windows 10 / 11 (64-bit)
- Microsoft Edge WebView2 Runtime（実行時）
- Python 3.11+（`python python/browser/main.py`をソースから実行する場合、およびビルドスクリプト用）
- Python 3.11+（ビルドスクリプト実行用）
- Python 3.11+（ビルドスクリプト実行およびプロトタイプ実行用）

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
`scripts/build.py`はこの場所を自動検索し、検出したコンパイラと同じフォルダの`windres.exe`も
使うため、プロジェクトのビルドだけならPATH登録は不要です。`g++`/`windres`を直接実行したい
場合のみ、パッケージの`mingw64\bin`を**ユーザー環境変数**のPATHに追加してください
`scripts/build.py` はこの場所を自動検索し、検出したコンパイラと同じフォルダの `windres.exe` も
使うため、プロジェクトのビルドだけならPATH登録は不要です。`g++` / `windres` を直接実行したい
場合のみ、パッケージの `mingw64\bin` を**ユーザー環境変数**の PATH に追加してください
（追加後はターミナル/IDEの再起動が必要）。
`scripts/build.py` はこの場所を自動検索し、検出したコンパイラと同じフォルダの `windres.exe` も使うため、プロジェクトのビルドだけならPATH登録は不要です。`g++` / `windres` を直接実行したい場合のみ、パッケージの `mingw64\bin` を**ユーザー環境変数**の PATH に追加してください（追加後はターミナル/IDEの再起動が必要）。

### WebView2 SDK

NuGetパッケージ`Microsoft.Web.WebView2`を展開し、ヘッダーを配置します。既定の探索先は
`C:\tools\webview2\build\native\include`。別の場所に置く場合は環境変数`WEBVIEW2_INCLUDE`を
設定してください。
NuGetパッケージ `Microsoft.Web.WebView2` を展開し、ヘッダーを配置します。
既定の探索先は `C:\tools\webview2\build\native\include`。
別の場所に置く場合は環境変数 `WEBVIEW2_INCLUDE` を設定してください。

## ソースから起動する場合（Python/FastAPI版）

```powershell
python -m pip install -r requirements.txt
python -m pip install -r scripts/requirements.txt
python python/browser/main.py
```

ネイティブ版と同じUI（`templates/index.html`）をFastAPI経由でブラウザに表示します。
ネイティブ版と同じUI（`src/ui/index.html`）をFastAPI経由でブラウザに表示します。
ネイティブビルドとの関係は[`about_jp.md`](about_jp.md)を参照してください——
`core/native/engine_x64.dll`が存在すれば`ctypes`経由でそれをロードし、無ければ
`dist/engine_x64.dll`が存在すれば`ctypes`経由でそれをロードし、無ければ
純Python実装にフォールバックします。

## ビルド方法

```powershell
g++ --version
windres --version
python build_native.py
scripts\build.bat
# または python scripts/build.py
```

### ビルド手順の内訳（scripts/build.py）

1. コンパイラ検出（`g++` → 見つからなければ `clang++`）
2. `scripts/bundle_html.py` で `src/ui/` を1枚の `index.html` にバンドルし `build/intermediate/` に配置（画像は data URI として埋め込み、HTML/CSS/JS を自己完結化）
3. `windres` でリソース（アイコン・バージョン情報・埋め込みHTML）を `build/intermediate/QuickDiskBench_res.o` へコンパイル
4. `src/engine/engine.cpp` から `dist/engine_x64.dll` を生成
5. `src/app/main_gui.cpp` + `src/engine/engine.cpp` + リソースを静的リンクして `dist/QuickDiskBench.exe` を生成
6. `src/cli/main_cli.cpp` + `src/engine/engine.cpp` から `dist/QuickDiskBench_cli.exe` を生成
7. `WebView2Loader.dll` および `scripts/benchmark-all-drives.ps1` を `dist/` へコピー

### ビルド成果物

| ファイル | 説明 |
| --- | --- |
| `dist/binary/QuickDiskBench.exe` | GUI版 |
| `dist/binary/QuickDiskBench_cli.exe` | CLI版 |
| `dist/binary/WebView2Loader.dll` | WebView2ローダー |
| `dist/binary/index.html` | バンドル済みGUI |
| `dist/binary/benchmark-all-drives.ps1` | 全ドライブ測定スクリプト |
| `dist/QuickDiskBench.exe` | GUI版（自己完結HTML内蔵） |
| `dist/QuickDiskBench_cli.exe` | CLI版 |
| `dist/engine_x64.dll` | C++ ネイティブDLL |
| `dist/WebView2Loader.dll` | WebView2ローダー |
| `dist/benchmark-all-drives.ps1` | 全ドライブ測定スクリプト |

## プロトタイプ（試作版）の実行

開発・検証用のプロトタイプ（FastAPIブラウザ版）を実行する場合：

```powershell
python -m pip install -r scripts/requirements.txt
python proto/browser/main.py
```

ネイティブ版と同じUI（`src/ui/index.html`）をFastAPI経由でブラウザに表示します。
ネイティブビルドとの関係は[`about_jp.md`](about_jp.md)を参照してください。
`dist/engine_x64.dll` が存在すれば `ctypes` 経由でそれをロードし、無ければ純Python実装にフォールバックします。

## トラブルシューティング

| 症状 | 原因と対処 |
| --- | --- |
| 大容量・低速ドライブでWin32エラー1460（タイムアウト） | `--timeout`（CLI）や`-TimeoutSec`（全ドライブスクリプト）を増やす、GUIで長めの制限時間を選択する |
| WebView2ウィンドウが開かない | Microsoft Edge WebView2 Runtime (Evergreen)をインストール |
| `g++`/`windres`を直接実行できない | WinLibsの`mingw64\bin`をユーザーPATHに追加しターミナル/IDEを再起動（`build_native.py`自体には不要） |
| `g++`/`windres`を直接実行できない | WinLibsの`mingw64\bin`をユーザーPATHに追加しターミナル/IDEを再起動（`scripts/build.py`自体には不要） |
| WebView2ウィンドウが開かない | Microsoft Edge WebView2 Runtime (Evergreen) をインストール |
| `g++`/`windres` を直接実行できない | WinLibsの `mingw64\bin` をユーザーPATHに追加しターミナル/IDEを再起動（`scripts/build.py` 自体には不要） |
| `g++` / `windres` を直接実行できない | WinLibsの `mingw64\bin` をユーザーPATHに追加しターミナル/IDEを再起動（`scripts/build.py` 自体には不要） |

## 依存関係

サードパーティC++ライブラリ依存なし。Python/FastAPI版の依存関係は`requirements.txt`を参照してください。
サードパーティC++ライブラリ依存なし。Python/FastAPI版の依存関係は`scripts/requirements.txt`を参照してください。
サードパーティC++ライブラリ依存なし。フロントエンド（HTML/CSS/JS）もフレームワーク非依存。
プロトタイプ実行に必要なPythonパッケージは `scripts/requirements.txt` を参照してください。
