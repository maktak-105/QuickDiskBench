import os
import sys
import json
import time
from datetime import datetime

from core.drive_manager import get_drive_list
from core.benchmark import BenchmarkRunner

def main():
    print("=" * 60)
    print(" SSDSpeed - 全ドライブ一括ベンチマークテスト")
    print(f" 開始日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    drives = get_drive_list()
    print(f"検出されたドライブ数: {len(drives)}")
    for d in drives:
        print(f" - {d['mountpoint']} [{d['label']}] ({d['fstype']}) Free: {d['free_gb']} GB / Total: {d['total_gb']} GB")

    results_summary = []
    test_size_mb = 256  # 全ドライブを安定して効率よく測定するためのサイズ (256MB)

    for drive in drives:
        mp = drive['mountpoint']
        label = drive['label'] or "(ラベルなし)"
        fstype = drive['fstype']

        # Google Drive 等の仮想ドライブ判定
        if "Google" in label or "Cloud" in label:
            print(f"\n[スキップ] {mp} {label} - クラウド仮想ドライブのため除外")
            continue

        print(f"\n" + "=" * 50)
        print(f" 測定開始: {mp} [{label}] ({fstype})")
        print("=" * 50)

        # 空き容量チェック (最低 1GB 以上)
        if drive['free_gb'] < 0.5:
            print(f"[スキップ] 空き容量不足 ({drive['free_gb']} GB)")
            results_summary.append({
                "mountpoint": mp,
                "label": label,
                "fstype": fstype,
                "total_gb": drive['total_gb'],
                "free_gb": drive['free_gb'],
                "status": "skipped (low disk space)",
                "results": {}
            })
            continue

        runner = BenchmarkRunner(target_dir=mp, file_size_mb=test_size_mb)
        
        last_phase = ""
        def on_progress(status):
            nonlocal last_phase
            current_test = status.get("current_test", "")
            if current_test and current_test != last_phase:
                print(f" -> {current_test} ...")
                last_phase = current_test

        start_time = time.time()
        runner.run_all(progress_callback=on_progress)
        elapsed = time.time() - start_time

        status_info = runner.current_status
        if status_info["status"] == "completed":
            print(f" [完了] 測定時間: {elapsed:.1f} 秒")
            res = status_info["results"]
            print(f"   Seq Write: {res['seq_write_mbs']} MB/s | Seq Read: {res['seq_read_mbs']} MB/s")
            print(f"   Rnd4K Q1 Write: {res['rnd4k_write_mbs']} MB/s ({res['rnd4k_write_iops']} IOPS) | Read: {res['rnd4k_read_mbs']} MB/s ({res['rnd4k_read_iops']} IOPS)")
            print(f"   Rnd4K Q32 Write: {res['rnd4k_q32_write_mbs']} MB/s ({res['rnd4k_q32_write_iops']} IOPS) | Read: {res['rnd4k_q32_read_mbs']} MB/s ({res['rnd4k_q32_read_iops']} IOPS)")
            
            results_summary.append({
                "mountpoint": mp,
                "label": label,
                "fstype": fstype,
                "total_gb": drive['total_gb'],
                "free_gb": drive['free_gb'],
                "status": "success",
                "results": res
            })
        else:
            err = status_info.get("error_msg", "Unknown error")
            print(f" [エラー] 測定失敗: {err}")
            results_summary.append({
                "mountpoint": mp,
                "label": label,
                "fstype": fstype,
                "total_gb": drive['total_gb'],
                "free_gb": drive['free_gb'],
                "status": f"error: {err}",
                "results": {}
            })

    # 結果を JSON ファイルに保存
    json_path = os.path.join(os.path.dirname(__file__), "benchmark_results_all.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "test_size_mb": test_size_mb,
            "drives": results_summary
        }, f, ensure_ascii=False, indent=2)
    print(f"\n[保存] JSON 結果ファイル: {json_path}")

    # 結果を Markdown レポートファイルに保存
    md_path = os.path.join(os.path.dirname(__file__), "benchmark_results_all.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 全ドライブ ベンチマーク測定結果レポート\n\n")
        f.write(f"- **測定日時**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- **テストサイズ**: {test_size_mb} MiB\n")
        f.write("- **測定エンジン**: Win32 Direct I/O (Unbuffered, Non-Cached)\n\n")
        f.write("## 測定結果サマリー\n\n")
        f.write("| ドライブ | ボリューム名 | 容量 (空き/総容量) | Seq Read | Seq Write | Rnd4K Q1 Read | Rnd4K Q1 Write | Rnd4K Q32 Read | Rnd4K Q32 Write |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")

        for item in results_summary:
            mp = item['mountpoint']
            label = item['label']
            cap = f"{item['free_gb']}G / {item['total_gb']}G"
            
            if item['status'] == 'success':
                r = item['results']
                f.write(f"| **{mp}** | {label} | {cap} | **{r['seq_read_mbs']} MB/s** | **{r['seq_write_mbs']} MB/s** | {r['rnd4k_read_mbs']} MB/s<br>({r['rnd4k_read_iops']:.0f} IOPS) | {r['rnd4k_write_mbs']} MB/s<br>({r['rnd4k_write_iops']:.0f} IOPS) | {r['rnd4k_q32_read_mbs']} MB/s<br>({r['rnd4k_q32_read_iops']:.0f} IOPS) | {r['rnd4k_q32_write_mbs']} MB/s<br>({r['rnd4k_q32_write_iops']:.0f} IOPS) |\n")
            else:
                f.write(f"| **{mp}** | {label} | {cap} | - | - | - | - | - | - |\n")

        f.write("\n## 各ドライブ詳細\n\n")
        for item in results_summary:
            f.write(f"### ドライブ {item['mountpoint']} [{item['label']}]\n")
            f.write(f"- ファイルシステム: `{item['fstype']}`\n")
            f.write(f"- 総容量: `{item['total_gb']} GB` (空き容量: `{item['free_gb']} GB`)\n")
            f.write(f"- ステータス: `{item['status']}`\n")
            if item['status'] == 'success':
                r = item['results']
                f.write(f"- **シーケンシャル 1MB**:\n")
                f.write(f"  - 読み込み: `{r['seq_read_mbs']} MB/s`\n")
                f.write(f"  - 書き込み: `{r['seq_write_mbs']} MB/s`\n")
                f.write(f"- **ランダム 4KB (Q1T1)**:\n")
                f.write(f"  - 読み込み: `{r['rnd4k_read_mbs']} MB/s` ({r['rnd4k_read_iops']} IOPS)\n")
                f.write(f"  - 書き込み: `{r['rnd4k_write_mbs']} MB/s` ({r['rnd4k_write_iops']} IOPS)\n")
                f.write(f"- **ランダム 4KB (Q32T1)**:\n")
                f.write(f"  - 読み込み: `{r['rnd4k_q32_read_mbs']} MB/s` ({r['rnd4k_q32_read_iops']} IOPS)\n")
                f.write(f"  - 書き込み: `{r['rnd4k_q32_write_mbs']} MB/s` ({r['rnd4k_q32_write_iops']} IOPS)\n")
            f.write("\n")

    print(f"[保存] Markdown レポート: {md_path}")
    print("\n全ドライブのベンチマーク測定が完了しました！")

if __name__ == "__main__":
    main()
