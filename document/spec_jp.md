# QuickDiskBench 仕様書

[English spec.md](spec.md)

## 1. アプリ概要

- **名称**: QuickDiskBench
- **目的**: Windows向けSSD/HDD/NVMeベンチマークツール。WindowsのOSキャッシュをバイパスしたDirect I/Oで、シーケンシャル/ランダムアクセスの速度・IOPSを測定する
- **対象OS**: Windows 10 / 11 (64-bit)
- **実装**: C++17 (MinGW-w64) + WebView2 + HTML/CSS/バニラJS
- **配布形態**: GitHub Releases の ZIP（フラット構成）
- **バージョン**: v2.1.1

`python/main.py`は独立したPython試作品ではなく、`core/native/engine_x64.dll`（製品版と同じC++エンジン）を`ctypes`経由でロードするFastAPIブラウザ版。DLL未ビルド時のみ純Python実装にフォールバックする。詳細は[`about_jp.md`](about_jp.md)参照。

## 2. アーキテクチャ

```text
[HTML/CSS/JS (WebView2)]  ←WebMessage(JSON)→  [webview_main.cpp]  ←直接呼出→  [engine.cpp]
```

- `engine.cpp` / `engine_x64.dll`: オーバーラップ/非同期I/OによるDirect I/O計測本体。GUI非依存で、CLI版・`python/main.py`（ctypes経由）からも同じエンジンを呼ぶ
- `webview_main.cpp`: Win32ウィンドウ生成、WebView2初期化、JSONメッセージの受け渡し
- フロントエンド: フレームワーク非依存。`bundle_html.py`で1枚のHTMLへバンドル

## 3. 画面構成

| 領域 | 内容 |
| --- | --- |
| ヘッダー | ドライブ/サイズ/回数/モード/制限時間の選択、言語切替・CSV出力・ヘルプ（右端に縦並び） |
| メイン | 転送速度グラフ、ドライブ情報パネル（メーカー・機種・実計測時間） |
| ステータス | 測定進捗（完了I/O数基準）、I/O待機中表示 |

## 4. 機能一覧

| # | 機能 | 説明 |
| --- | --- | --- |
| 1 | ドライブ選択 | 測定対象ドライブ・パスを選択 |
| 2 | 測定設定 | サイズ（既定256MiB、最小64MiB）、回数（1-9）、キャッシュあり/なし、制限時間（60/120/180/300/600秒） |
| 3 | Direct I/O計測 | `FILE_FLAG_NO_BUFFERING`でOSキャッシュを回避。「キャッシュなし」モードは`FILE_FLAG_WRITE_THROUGH`も追加しデバイス側キャッシュの影響も抑制 |
| 4 | 平均値・標準偏差 | 複数回の測定から平均と標準偏差を算出し安定性を可視化 |
| 5 | 進捗表示 | 経過時間ではなく完了I/O数基準で進捗を更新。I/O待機中はグラフに0MB/sを反映 |
| 6 | CSV出力 | 測定結果サマリーをCSV保存（GUI/CLIとも対応） |
| 7 | 全ドライブ測定 | `benchmark-all-drives.ps1`が固定ボリュームを列挙し順に測定、集計CSVを`results`フォルダへ出力 |
| 8 | 言語切替 | 日本語⇔Englishをヘッダーのボタンで切替 |
| 9 | CLI版 | `QuickDiskBench_cli.exe --drive/--size/--passes/--timeout/--raw/--csv` |

## 5. 処理フロー

1. ユーザーがドライブ・設定を選択して測定開始
2. `webview_main.cpp`がエンジンへ測定を依頼、進捗コールバックでJSへ送信
3. 各テスト完了ごとに結果を集計し、平均・標準偏差を算出
4. 全テスト完了後、実計測時間とともにドライブ情報パネルへ表示

## 6. 出力フォーマット仕様

- **CSV**: ドライブ・テスト種別・速度・IOPSを含む結果サマリー
- **全ドライブ測定CSV**: `results\summary-YYYYMMDD-HHMMSS.csv`に集計

## 7. パフォーマンス・タイムアウト

- 各テストの既定タイムアウトは60秒。CLIの`--timeout`、全ドライブスクリプトの`-TimeoutSec`で1〜3600秒に変更可能
- 4GB以上の測定や低速・高負荷ドライブでWin32エラー1460（タイムアウト）が出る場合はタイムアウト値を増やして再実行する

## 8. 今後の実装予定

- （現時点で明記された計画なし）
