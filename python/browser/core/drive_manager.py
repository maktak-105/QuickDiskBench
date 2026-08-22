import os
import sys
import psutil
import ctypes
from ctypes import wintypes


def _get_physical_drive_identity(mountpoint):
    """Return (manufacturer, model) for the physical disk behind a volume."""
    if sys.platform != 'win32' or not mountpoint or len(mountpoint) < 2 or mountpoint[1] != ':':
        return '', ''

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.DeviceIoControl.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p
    ]
    kernel32.DeviceIoControl.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    volume_path = r'\\.' + '\\' + mountpoint[:2]
    invalid_handle = wintypes.HANDLE(-1).value

    volume = kernel32.CreateFileW(
        ctypes.c_wchar_p(volume_path), 0,
        0x00000001 | 0x00000002,  # FILE_SHARE_READ | FILE_SHARE_WRITE
        None, 3, 0, None           # OPEN_EXISTING
    )
    if volume == invalid_handle:
        return '', ''

    class StorageDeviceNumber(ctypes.Structure):
        _fields_ = [
            ('DeviceType', wintypes.DWORD),
            ('DeviceNumber', wintypes.DWORD),
            ('PartitionNumber', wintypes.DWORD),
        ]

    number = StorageDeviceNumber()
    returned = wintypes.DWORD()
    ioctl_get_number = 0x002D1080
    ok = kernel32.DeviceIoControl(
        volume, ioctl_get_number, None, 0,
        ctypes.byref(number), ctypes.sizeof(number),
        ctypes.byref(returned), None
    )
    kernel32.CloseHandle(volume)
    if not ok:
        return '', ''

    physical_path = r'\\.\PhysicalDrive' + str(number.DeviceNumber)
    physical = kernel32.CreateFileW(
        ctypes.c_wchar_p(physical_path), 0,
        0x00000001 | 0x00000002,
        None, 3, 0, None
    )
    if physical == invalid_handle:
        return '', ''

    class StoragePropertyQuery(ctypes.Structure):
        _fields_ = [
            ('PropertyId', wintypes.DWORD),
            ('QueryType', wintypes.DWORD),
            ('AdditionalParameters', ctypes.c_ubyte * 1),
        ]

    query = StoragePropertyQuery(0, 0, (ctypes.c_ubyte * 1)(0))
    buffer = ctypes.create_string_buffer(4096)
    ioctl_query_property = 0x002D1400
    ok = kernel32.DeviceIoControl(
        physical, ioctl_query_property,
        ctypes.byref(query), ctypes.sizeof(query),
        buffer, ctypes.sizeof(buffer),
        ctypes.byref(returned), None
    )
    kernel32.CloseHandle(physical)
    if not ok or returned.value < 28:
        return '', ''

    raw = buffer.raw[:returned.value]
    # STORAGE_DEVICE_DESCRIPTOR offsets: VendorIdOffset=12, ProductIdOffset=16.
    import struct
    _, _, _, _, _, _, vendor_offset, product_offset, _, _ = struct.unpack_from('<IIBBBBIIII', raw, 0)

    def read_text(offset):
        if not offset or offset >= len(raw):
            return ''
        end = raw.find(b'\0', offset)
        if end < 0:
            end = len(raw)
        return raw[offset:end].decode('mbcs', errors='replace').strip()

    return read_text(vendor_offset), read_text(product_offset)

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

            manufacturer, model = _get_physical_drive_identity(p.mountpoint)

            drives.append({
                "mountpoint": p.mountpoint,
                "device": p.device,
                "fstype": p.fstype,
                "label": label,
                "manufacturer": manufacturer,
                "model": model,
                "total_gb": round(usage.total / (1024 ** 3), 2),
                "used_gb": round(usage.used / (1024 ** 3), 2),
                "free_gb": round(usage.free / (1024 ** 3), 2),
                "percent": usage.percent
            })
        except Exception:
            continue
    return drives
