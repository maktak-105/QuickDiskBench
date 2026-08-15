# SSDSpeed - High Precision Disk Benchmark Engine & Web Dashboard

Windows OS ファイルシステムキャッシュの影響を受けない **Unbuffered Direct I/O Engine** を搭載した、高精度な SSD / NVMe / HDD ディスクベンチマークツールです。

## 特徴
- **Direct I/O 測定エンジン**:
  - Windows API (`kernel32.dll` -> `CreateFileW`, `FILE_FLAG_NO_BUFFERING`, `FILE_FLAG_WRITE_THROUGH`) を直接呼び出すことで OS キャッシュを完全バイパス。
  - セクターアライメント済みメモリバッファ (`VirtualAlloc`) による正確なストレージアクセス速度・IOPSを測定。
- **リッチな Web Dashboard**:
  - CrystalDiskMark 風の測定項目 (Seq 1M, Random 4K Q1T1, Random 4K Q32T1)
  - Chart.js による転送速度 (MB/s) のリアルタイム折れ線グラフ
  - ディスク容量・使用率ゲージ
  - Glassmorphic Dark モードのモダン UI
- **柔軟な制御**:
  - ドライブ選択 (C:, D: など)
  - テストサイズ選択 (256MB ～ 2GB)
  - リアルタイムでの測定停止機能

## 動作要件
- Windows OS (Windows 10 / 11)
- Python 3.8 以上

## インストール & 起動手順

1. 依存ライブラリのインストール
   ```bash
   pip install -r requirements.txt
   ```

2. サーバーの起動
   ```bash
   python main.py
   ```

3. ブラウザでアクセス
   [http://127.0.0.1:8000](http://127.0.0.1:8000) を開き、ドライブを選択して「テスト開始」をクリックします。
