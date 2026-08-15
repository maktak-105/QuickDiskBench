import os
import sys
import psutil
import ctypes

def get_drive_list():
    """
    接続されているディスクドライブの一覧を取得する。
    """
    drives = []
    partitions = psutil.disk_partitions(all=False)
    for p in partitions:
        try:
            usage = psutil.disk_usage(p.mountpoint)
            # ドライブラベルの取得 (Windows)
            label = ""
            if sys.platform == 'win32':
                volume_name_buf = ctypes.create_unicode_buffer(1024)
                fs_name_buf = ctypes.create_unicode_buffer(1024)
                res = ctypes.windll.kernel32.GetVolumeInformationW(
                    ctypes.c_wchar_p(p.mountpoint),
                    volume_name_buf,
                    1024,
                    None, None, None,
                    fs_name_buf,
                    1024
                )
                if res:
                    label = volume_name_buf.value

            drives.append({
                "mountpoint": p.mountpoint,
                "device": p.device,
                "fstype": p.fstype,
                "label": label,
                "total_gb": round(usage.total / (1024 ** 3), 2),
                "used_gb": round(usage.used / (1024 ** 3), 2),
                "free_gb": round(usage.free / (1024 ** 3), 2),
                "percent": usage.percent
            })
        except Exception:
            continue
    return drives
