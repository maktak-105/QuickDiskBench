import os
import sys
import json
import time
from datetime import datetime

from core.drive_manager import get_drive_list
from core.benchmark import BenchmarkRunner

def main():
    passes = 1
    if len(sys.argv) > 1:
        try:
            passes = max(1, min(9, int(sys.argv[1])))
        except ValueError:
            pass

    print("=" * 60)
    print(" QuickDiskBench - 全ドライブ一括ベンチマークテスト")
    print(f" 開始日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" 測定回数: {passes} 回 (平均 ± 標準偏差を算出)")
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
        if "google drive" in label.lower() or fstype.upper() == "FAT32":
            print(f"[スキップ] クラウド同期/仮想ドライブのためスキップ ({label})")
            results_summary.append({
                "mountpoint": mp,
                "label": label,
                "fstype": fstype,
                "total_gb": drive['total_gb'],
                "free_gb": drive['free_gb'],
                "status": "skipped (cloud drive)",
                "results": {}
            })
            continue

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

        runner = BenchmarkRunner(target_dir=mp, file_size_mb=test_size_mb, profile="cdm", passes=passes)
        
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
            print(f"   SEQ1M Q8T1: Read {res.get('seq_q8_read_mbs', 0)} MB/s | Write {res.get('seq_q8_write_mbs', 0)} MB/s")
            print(f"   SEQ1M Q1T1: Read {res.get('seq_read_mbs', 0)} MB/s | Write {res.get('seq_write_mbs', 0)} MB/s")
            print(f"   RND4K Q32T1: Read {res.get('rnd4k_q32_read_mbs', 0)} MB/s ({res.get('rnd4k_q32_read_iops', 0):.0f} IOPS) | Write {res.get('rnd4k_q32_write_mbs', 0)} MB/s ({res.get('rnd4k_q32_write_iops', 0):.0f} IOPS)")
            print(f"   RND4K Q1T1: Read {res.get('rnd4k_read_mbs', 0)} MB/s ({res.get('rnd4k_read_iops', 0):.0f} IOPS) | Write {res.get('rnd4k_write_mbs', 0)} MB/s ({res.get('rnd4k_write_iops', 0):.0f} IOPS)")
            
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
            "profile": "cdm",
            "passes": passes,
            "drives": results_summary
        }, f, ensure_ascii=False, indent=2)
    print(f"\n[保存] JSON 結果ファイル: {json_path}")

    # 結果を Markdown レポートファイルに保存
    md_path = os.path.join(os.path.dirname(__file__), "benchmark_results_all.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 全ドライブ ベンチマーク測定結果レポート (キャッシュ測定 & 統計機能)\n\n")
        f.write(f"- **測定日時**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- **テストサイズ**: {test_size_mb} MiB\n")
        f.write(f"- **測定回数**: {passes} Pass(es) (平均値 ± 標準偏差)\n")
        f.write("- **測定モード**: OSキャッシュなし・ハードウェアキャッシュあり／ハードウェアキャッシュの影響を抑制 (Overlapped Direct I/O)\n\n")
        f.write("## 測定結果サマリー\n\n")
        f.write("| ドライブ | ボリューム名 | 容量 (空き/総容量) | SEQ1M Q8 Read | SEQ1M Q8 Write | SEQ1M Q1 Read | SEQ1M Q1 Write | RND4K Q32 Read | RND4K Q32 Write | RND4K Q1 Read | RND4K Q1 Write |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|---|\n")

        for item in results_summary:
            mp = item['mountpoint']
            label = item['label']
            cap = f"{item['free_gb']}G / {item['total_gb']}G"
            
            if item['status'] == 'success':
                r = item['results']
                def fmt(mbs_key, std_key=""):
                    v = r.get(mbs_key, 0.0)
                    s = r.get(std_key, 0.0) if std_key else 0.0
                    if passes > 1 and s > 0:
                        return f"{v:.2f} ±{s:.2f} MB/s"
                    return f"{v:.2f} MB/s"

                f.write(f"| **{mp}** | {label} | {cap} | **{fmt('seq_q8_read_mbs', 'seq_q8_read_std')}** | **{fmt('seq_q8_write_mbs', 'seq_q8_write_std')}** | {fmt('seq_read_mbs', 'seq_read_std')} | {fmt('seq_write_mbs', 'seq_write_std')} | {fmt('rnd4k_q32_read_mbs', 'rnd4k_q32_read_std')}<br>({r.get('rnd4k_q32_read_iops', 0):.0f} IOPS) | {fmt('rnd4k_q32_write_mbs', 'rnd4k_q32_write_std')}<br>({r.get('rnd4k_q32_write_iops', 0):.0f} IOPS) | {fmt('rnd4k_read_mbs', 'rnd4k_read_std')}<br>({r.get('rnd4k_read_iops', 0):.0f} IOPS) | {fmt('rnd4k_write_mbs', 'rnd4k_write_std')}<br>({r.get('rnd4k_write_iops', 0):.0f} IOPS) |\n")
            else:
                f.write(f"| **{mp}** | {label} | {cap} | - | - | - | - | - | - | - | - |\n")

        # 測定項目別 横棒グラフの出力
        f.write("\n## 測定項目別 比較グラフ (横棒グラフ)\n\n")
        metrics = [
            ("seq_q8_read_mbs", "1. SEQ1M Q8T1 リード (Seq Q8 Read)", "MB/s", ""),
            ("seq_q8_write_mbs", "2. SEQ1M Q8T1 ライト (Seq Q8 Write)", "MB/s", ""),
            ("seq_read_mbs", "3. SEQ1M Q1T1 リード (Seq Q1 Read)", "MB/s", ""),
            ("seq_write_mbs", "4. SEQ1M Q1T1 ライト (Seq Q1 Write)", "MB/s", ""),
            ("rnd4k_q32_read_mbs", "5. RND4K Q32T1 リード (Rnd4K Q32 Read)", "MB/s", "rnd4k_q32_read_iops"),
            ("rnd4k_q32_write_mbs", "6. RND4K Q32T1 ライト (Rnd4K Q32 Write)", "MB/s", "rnd4k_q32_write_iops"),
            ("rnd4k_read_mbs", "7. RND4K Q1T1 リード (Rnd4K Q1 Read)", "MB/s", "rnd4k_read_iops"),
            ("rnd4k_write_mbs", "8. RND4K Q1T1 ライト (Rnd4K Q1 Write)", "MB/s", "rnd4k_write_iops"),
        ]

        bar_max_width = 30
        for m_key, title, unit, iops_key in metrics:
            f.write(f"### {title}\n```text\n")
            success_drives = [d for d in results_summary if d.get("status") == "success"]
            sorted_drives = sorted(success_drives, key=lambda d: d.get("mountpoint", ""))
            max_val = max([d.get("results", {}).get(m_key, 0) for d in sorted_drives], default=1.0)
            if max_val <= 0: max_val = 1.0

            for d in sorted_drives:
                res = d.get("results", {})
                val = res.get(m_key, 0.0)
                bar_len = int(round((val / max_val) * bar_max_width))
                bar_str = "█" * bar_len if bar_len > 0 else ("▏" if val > 0 else "")
                iops_str = f" [{res.get(iops_key, 0):.0f} IOPS]" if iops_key and iops_key in res else ""
                f.write(f"{d['mountpoint']:<4} [{d['label']:<14}] : {val:>8.2f} {unit} | {bar_str} ({bar_len}){iops_str}\n")
            f.write("```\n\n")

        f.write("## 各ドライブ詳細\n\n")
        for item in results_summary:
            f.write(f"### ドライブ {item['mountpoint']} [{item['label']}]\n")
            f.write(f"- ファイルシステム: `{item['fstype']}`\n")
            f.write(f"- 総容量: `{item['total_gb']} GB` (空き容量: `{item['free_gb']} GB`)\n")
            f.write(f"- ステータス: `{item['status']}`\n")
            if item['status'] == 'success':
                r = item['results']
                f.write(f"- **SEQ1M Q8T1**:\n")
                f.write(f"  - 読み込み: `{r.get('seq_q8_read_mbs', 0)} MB/s`\n")
                f.write(f"  - 書き込み: `{r.get('seq_q8_write_mbs', 0)} MB/s`\n")
                f.write(f"- **SEQ1M Q1T1**:\n")
                f.write(f"  - 読み込み: `{r.get('seq_read_mbs', 0)} MB/s`\n")
                f.write(f"  - 書き込み: `{r.get('seq_write_mbs', 0)} MB/s`\n")
                f.write(f"- **RND4K Q32T1**:\n")
                f.write(f"  - 読み込み: `{r.get('rnd4k_q32_read_mbs', 0)} MB/s` ({r.get('rnd4k_q32_read_iops', 0)} IOPS)\n")
                f.write(f"  - 書き込み: `{r.get('rnd4k_q32_write_mbs', 0)} MB/s` ({r.get('rnd4k_q32_write_iops', 0)} IOPS)\n")
                f.write(f"- **RND4K Q1T1**:\n")
                f.write(f"  - 読み込み: `{r.get('rnd4k_read_mbs', 0)} MB/s` ({r.get('rnd4k_read_iops', 0)} IOPS)\n")
                f.write(f"  - 書き込み: `{r.get('rnd4k_write_mbs', 0)} MB/s` ({r.get('rnd4k_write_iops', 0)} IOPS)\n")
            f.write("\n")

    print(f"[保存] Markdown レポート: {md_path}")
    print("\n全ドライブのベンチマーク測定が完了しました！")

if __name__ == "__main__":
    main()
