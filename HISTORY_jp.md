# QuickDiskBench 変更履歴

このファイルには、公開版の主な変更履歴を記載します。

## バージョン命名規則

- 1桁目の更新（例：`1.0.0`→`2.0.0`）：機能追加
- 2桁目の更新（例：`1.0.0`→`1.1.0`）：バグ修正
- 3桁目の更新（例：`1.1.0`→`1.1.1`）：その他の変更（ドキュメント修正など）

## 未リリース

### ドキュメント

- `dist/documents/README.txt`/`README-en.txt`/`LICENSE-ja.txt`を、Quickシリーズ共通の命名規則（英語版がベース名、`_jp`接尾辞、ハイフン不使用）に合わせて`readme_jp.txt`/`readme.txt`/`LICENSE_jp.txt`にリネーム。従来は英語版であるはずの`README.txt`の中身が日本語になっており、英日の役割が逆転していた。
- 欠落していた`document/`フォルダ（`spec.md`/`spec_jp.md`、`environment.md`/`environment_jp.md`、`about.md`/`about_jp.md`）を新規作成。GitHub公開時の注意点PDFがある既存の`documents/`（複数形）フォルダとは無関係で、そちらは変更していない。
- 存在しなかった`dist/documents/history.txt`/`history_jp.txt`を新規作成。
- `dist/documents/readme.txt`/`readme_jp.txt`にバージョン行（`配布パッケージ v2.1.1`）を追加。
- README.md/README_jpと`document/about.md`に、`python main.py`がネイティブ版とどう関係するか（独立したPython実装ではなく、`ctypes`経由で同じ`engine_x64.dll`をロードするFastAPIブラウザ版であること）を明記。
- `core/native/QuickDiskBench.rc`に`VERSIONINFO`ブロックを追加し、ビルドしたexeのファイルプロパティにバージョンが表示されるようにした（従来はアイコン定義のみだった）。
- `.github/workflows/release.yml`のパッケージ対象ファイルリストを、リネーム後の`dist/documents/`ファイル名に更新。

## 2.1.1（2026-08-17）

### 配布・ビルド

- 配布用ファイルを`dist/binary`へ、説明書とライセンスを`dist/documents`へ整理。
- リリースZIPをサブフォルダなしのフラット構成で作成するよう変更。
- ZIPには`README.txt`、`README-en.txt`、`LICENSE.txt`、`LICENSE-ja.txt`を含め、`README.md`は含めない構成に変更。
- リポジトリのルートREADMEを英語版`README.md`と日本語版`README_jp.md`に分離し、英語版冒頭から日本語版へリンク。
- GitHub ActionsのWindowsビルドで、MinGW優先、UTF-8ログ、Windows固有のコンパイル互換性を修正。
- CLI実行ファイルのビルド失敗を検出し、エラー内容を表示するよう改善。
- `build_native.py`が、`PATH`にない場合でも検出したコンパイラと同じフォルダの`windres.exe`を使うよう改善。
- `bundle_html.py`が相対パスの画像をdata URIへ埋め込み、WebView2の`NavigateToString`でも表示できるよう改善。

### GUI

- ヘッダー右端の言語切替、CSV出力、ヘルプボタンを、日本語・英語ともに縦並びに変更。
- ヘルプダイアログ末尾に作者画像を追加。
- 既定ウィンドウ高さを900から780へ下げ、転送速度グラフ下の余白を解消。

### ベンチマーク修正

- RND4K非同期I/Oの失敗、待機失敗、タイムアウトを成功扱いにしないよう修正。
- ランダムI/Oの安全タイムアウトを3秒から60秒へ延長し、低速ドライブや高負荷時の誤った0.00表示を抑制。
- 各テストの既定タイムアウトを60秒に統一し、CLIの`--timeout`および全ドライブ測定スクリプトの`-TimeoutSec`で最大3600秒まで延長できるよう改善。
- Win32 I/OエラーコードをCLIに表示するよう改善。
- GUIで測定失敗を0.00の正常終了として表示せず、失敗状態を表示するよう改善。
- GUIに制限時間（60～600秒）の選択を追加し、選択値をネイティブエンジンへ渡すよう改善。
- 進捗率を経過時間ではなく完了I/O数基準に変更し、4K I/O待機中の表示とグラフの0 MB/s更新に対応。
- GUIのドライブ情報パネル先頭に、物理ドライブのメーカーと機種を表示するよう改善。
- GUIのドライブ情報パネル下部に、全テストの実計測時間を表示するよう改善。
- 512MiB、1GiB、2GiB・測定回数1回のRND4K WRITEをローカル実測で確認。

## 1.0.0（2026-08-16）

- QuickDiskBench初回公開版。
- Windows向けGUI版とCLI版を提供。
- OSキャッシュをバイパスするDirect I/Oベンチマークを実装。
- シーケンシャルI/O、RND4K Q32T1、RND4K Q1T1の速度・IOPS測定に対応。
- 測定回数、書き込みスルー、CSV出力、全ドライブ測定スクリプトを提供。
- GitHub Releases向けのバイナリ配布ZIPを追加。
