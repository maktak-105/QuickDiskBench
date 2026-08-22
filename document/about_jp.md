# QuickDiskBench バージョン情報

[English about.md](about.md)

## バージョン

Ver. v2.1.1

## コンセプト

Windows向けのSSD/HDD/NVMeベンチマークツールです。瞬間的なピーク性能ではなく、
実務で意味のある「持続的な実効速度」と「動作の安定性」を、WindowsのOSキャッシュを
バイパスしたDirect I/Oで測定することに重点を置いています。

## 開発環境

- C++17（MinGW-w64 / g++、WinLibs MCF UCRT）
- WebView2（Microsoft Edge WebView2 Runtime）
- Win32 API（`FILE_FLAG_NO_BUFFERING` / `FILE_FLAG_WRITE_THROUGH`によるオーバーラップ/非同期I/O）

サードパーティC++ライブラリ依存なし。フロントエンド（HTML/CSS/JS）もフレームワーク非依存です。

## 現在の位置づけ：Python版とC++版の関係について

他の一部のQuick系アプリと異なり、`python/browser/main.py`は**独立した試作実装ではありません**。
FastAPIサーバーが`templates/index.html`と同じUIをブラウザへ提供し、実際のディスクI/O測定は
`core/native/engine_x64.dll`（ネイティブ版と同じC++エンジン）を`ctypes`経由でロードして
実行します（`core/benchmark.py`参照）。このDLLが存在しない場合のみ、純Python実装
（`core/win32_io.py`の`Win32DirectIO`）にフォールバックするため、ネイティブビルドが
無くても`python python/browser/main.py`は動作します。製品として出荷されるのは`QuickDiskBench.exe`
（C++17 + WebView2、静的リンク）であり、`python/browser/main.py`は同じUIをソースから起動する
開発用の手段であって、別の独立した製品ではありません。

## 制作者

GitHub: [maktak-105](https://github.com/maktak-105)

## 免責事項

QuickDiskBenchは独立したディスクベンチマークアプリケーションであり、いかなる
サードパーティのベンチマークソフトウェア・ハードウェアベンダーとも提携・承認関係にありません。
