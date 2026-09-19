import os
import sys
import ctypes
from ctypes import wintypes
import time
from typing import List, Tuple

# Windows Flags & Constants
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_ALWAYS = 4
CREATE_ALWAYS = 2
TRUNCATE_EXISTING = 5
FILE_ATTRIBUTE_NORMAL = 0x80
FILE_FLAG_NO_BUFFERING = 0x20000000
FILE_FLAG_WRITE_THROUGH = 0x80000000
FILE_FLAG_OVERLAPPED = 0x40000000

MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x04

INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
WAIT_OBJECT_0 = 0
ERROR_IO_PENDING = 997

if sys.platform == 'win32':
    kernel32 = ctypes.windll.kernel32

    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE
    ]

    kernel32.WriteFile.restype = wintypes.BOOL
    kernel32.WriteFile.argtypes = [
        wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID
    ]

    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.ReadFile.argtypes = [
        wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID
    ]

    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    kernel32.SetFilePointerEx.restype = wintypes.BOOL
    kernel32.SetFilePointerEx.argtypes = [
        wintypes.HANDLE, ctypes.c_int64, ctypes.POINTER(ctypes.c_int64), wintypes.DWORD
    ]

    kernel32.SetEndOfFile.restype = wintypes.BOOL
    kernel32.SetEndOfFile.argtypes = [wintypes.HANDLE]

    kernel32.VirtualAlloc.restype = wintypes.LPVOID
    kernel32.VirtualAlloc.argtypes = [wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]

    kernel32.VirtualFree.restype = wintypes.BOOL
    kernel32.VirtualFree.argtypes = [wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD]

    kernel32.CreateEventW.restype = wintypes.HANDLE
    kernel32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]

    kernel32.ResetEvent.restype = wintypes.BOOL
    kernel32.ResetEvent.argtypes = [wintypes.HANDLE]

    kernel32.GetOverlappedResult.restype = wintypes.BOOL
    kernel32.GetOverlappedResult.argtypes = [
        wintypes.HANDLE, wintypes.LPVOID, ctypes.POINTER(wintypes.DWORD), wintypes.BOOL
    ]

    kernel32.WaitForMultipleObjects.restype = wintypes.DWORD
    kernel32.WaitForMultipleObjects.argtypes = [
        wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE), wintypes.BOOL, wintypes.DWORD
    ]

    kernel32.CancelIo.restype = wintypes.BOOL
    kernel32.CancelIo.argtypes = [wintypes.HANDLE]


class OVERLAPPED(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_void_p),
        ("InternalHigh", ctypes.c_void_p),
        ("Offset", wintypes.DWORD),
        ("OffsetHigh", wintypes.DWORD),
        ("hEvent", wintypes.HANDLE),
    ]


class AlignedBuffer:
    """VirtualAlloc で確保したセクターアライメント済みメモリバッファ"""
    def __init__(self, size: int):
        self.size = size
        if sys.platform == 'win32':
            self.ptr = kernel32.VirtualAlloc(None, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
            if not self.ptr:
                raise MemoryError("Failed to allocate aligned memory via VirtualAlloc")
        else:
            self.buffer = bytearray(size)
            self.ptr = (ctypes.c_char * size).from_buffer(self.buffer)

    def fill_pattern(self, pattern_byte: int = 0xA5):
        if sys.platform == 'win32' and self.ptr:
            ctypes.memset(self.ptr, pattern_byte, self.size)

    def free(self):
        if sys.platform == 'win32' and self.ptr:
            kernel32.VirtualFree(self.ptr, 0, MEM_RELEASE)
            self.ptr = None


class Win32DirectIO:
    """
    Win32 Unbuffered Direct I/O & Overlapped I/O
    OSキャッシュを常に使わず、キャッシュあり (write_through=False: ハードウェアキャッシュ使用)
    およびキャッシュなし (write_through=True: ハードウェアキャッシュの影響を抑制) に対応
    """
    def __init__(self, filepath: str, direct_io: bool = True, write_through: bool = False, overlapped: bool = False):
        self.filepath = filepath
        self.direct_io = direct_io and (sys.platform == 'win32')
        self.write_through = write_through
        self.overlapped = overlapped
        self.handle = None

    def preallocate(self, file_size_bytes: int):
        """ファイルを事前に指定サイズでディスク上にアロケーション"""
        if not self.direct_io:
            return
        h = kernel32.CreateFileW(
            self.filepath,
            GENERIC_READ | GENERIC_WRITE,
            0,
            None,
            CREATE_ALWAYS,
            FILE_ATTRIBUTE_NORMAL,
            None
        )
        if h != INVALID_HANDLE_VALUE:
            li = ctypes.c_int64(file_size_bytes)
            kernel32.SetFilePointerEx(h, li, None, 0)
            kernel32.SetEndOfFile(h)
            kernel32.CloseHandle(h)

    def open_for_write(self):
        if self.direct_io:
            flags = FILE_ATTRIBUTE_NORMAL | FILE_FLAG_NO_BUFFERING
            if self.write_through:
                flags |= FILE_FLAG_WRITE_THROUGH
            if self.overlapped:
                flags |= FILE_FLAG_OVERLAPPED

            self.handle = kernel32.CreateFileW(
                self.filepath,
                GENERIC_READ | GENERIC_WRITE,
                0,  # 排他アクセス
                None,
                OPEN_ALWAYS,
                flags,
                None
            )
            if self.handle == INVALID_HANDLE_VALUE:
                error_code = kernel32.GetLastError()
                raise IOError(f"Failed to open file for write: Windows Error {error_code}")
        else:
            self.fp = open(self.filepath, 'wb+')

    def open_for_read(self):
        if self.direct_io:
            flags = FILE_ATTRIBUTE_NORMAL | FILE_FLAG_NO_BUFFERING
            if self.overlapped:
                flags |= FILE_FLAG_OVERLAPPED

            self.handle = kernel32.CreateFileW(
                self.filepath,
                GENERIC_READ,
                0,
                None,
                OPEN_ALWAYS,
                flags,
                None
            )
            if self.handle == INVALID_HANDLE_VALUE:
                error_code = kernel32.GetLastError()
                raise IOError(f"Failed to open file for read: Windows Error {error_code}")
        else:
            self.fp = open(self.filepath, 'rb')

    def seek(self, offset: int):
        if self.direct_io and self.handle and not self.overlapped:
            new_pos = ctypes.c_int64()
            kernel32.SetFilePointerEx(self.handle, ctypes.c_int64(offset), ctypes.byref(new_pos), 0)
        elif hasattr(self, 'fp'):
            self.fp.seek(offset)

    def write_sync(self, buffer: AlignedBuffer, size: int) -> int:
        if self.direct_io and self.handle:
            written = wintypes.DWORD(0)
            res = kernel32.WriteFile(self.handle, buffer.ptr, size, ctypes.byref(written), None)
            if not res:
                raise IOError(f"Win32 WriteFile failed: Code {kernel32.GetLastError()}")
            return written.value
        return 0

    def read_sync(self, buffer: AlignedBuffer, size: int) -> int:
        if self.direct_io and self.handle:
            read_bytes = wintypes.DWORD(0)
            res = kernel32.ReadFile(self.handle, buffer.ptr, size, ctypes.byref(read_bytes), None)
            if not res:
                raise IOError(f"Win32 ReadFile failed: Code {kernel32.GetLastError()}")
            return read_bytes.value
        return 0

    def cancel_io(self):
        if self.direct_io and self.handle:
            kernel32.CancelIo(self.handle)

    def close(self):
        if self.direct_io and self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None
        elif hasattr(self, 'fp') and not self.fp.closed:
            self.fp.close()
