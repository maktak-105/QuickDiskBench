# QuickDiskBench バージョン情報

## バージョン

Ver. v3.0.0

## コンセプト

Windows向けのSSD/HDD/NVMeベンチマークツールです。瞬間的なピーク性能ではなく、
実務で意味のある「持続的な実効速度」と「動作の安定性」を、WindowsのOSキャッシュを
バイパスしたDirect I/Oで測定することに重点を置いています。

## 開発環境

- C++17（MinGW-w64 / g++、WinLibs MCF UCRT）
- WebView2（Microsoft Edge WebView2 Runtime）
- Win32 API（`FILE_FLAG_NO_BUFFERING` / `FILE_FLAG_WRITE_THROUGH`によるオーバーラップ/非同期I/O）

サードパーティC++ライブラリ依存なし。フロントエンド（HTML/CSS/JS）もフレームワーク非依存です。

## プロトタイプ（試作版）について

`proto/browser/main.py` は開発・検証用のプロトタイプ（FastAPIブラウザ版）です。
`src/ui/index.html` と同じUIをブラウザへ提供し、`dist/engine_x64.dll`（C++エンジン）を `ctypes` 経由でロードして実測定を行います（DLL未ビルド時は純Python実装にフォールバック）。
製品として出荷・配布されるのは `dist/QuickDiskBench.exe`（C++17 + WebView2、静的リンク）です。

## 制作者

GitHub: [maktak-105](https://github.com/maktak-105)

## 免責事項

QuickDiskBenchは独立したディスクベンチマークアプリケーションであり、いかなる
サードパーティのベンチマークソフトウェア・ハードウェアベンダーとも提携・承認関係にありません。
