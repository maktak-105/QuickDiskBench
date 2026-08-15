import os
import sys
import ctypes
from ctypes import wintypes
import time

# Windows Flags
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_ALWAYS = 4
CREATE_ALWAYS = 2
TRUNCATE_EXISTING = 5
FILE_ATTRIBUTE_NORMAL = 0x80
FILE_FLAG_NO_BUFFERING = 0x20000000
FILE_FLAG_WRITE_THROUGH = 0x80000000

MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x04

INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

if sys.platform == 'win32':
    kernel32 = ctypes.windll.kernel32

    CreateFileW = kernel32.CreateFileW
    CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE
    ]
    CreateFileW.restype = wintypes.HANDLE

    WriteFile = kernel32.WriteFile
    WriteFile.argtypes = [
        wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID
    ]
    WriteFile.restype = wintypes.BOOL

    ReadFile = kernel32.ReadFile
    ReadFile.argtypes = [
        wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID
    ]
    ReadFile.restype = wintypes.BOOL

    CloseHandle = kernel32.CloseHandle
    CloseHandle.argtypes = [wintypes.HANDLE]
    CloseHandle.restype = wintypes.BOOL

    SetFilePointerEx = kernel32.SetFilePointerEx
    SetFilePointerEx.argtypes = [
        wintypes.HANDLE, ctypes.c_int64, ctypes.POINTER(ctypes.c_int64), wintypes.DWORD
    ]
    SetFilePointerEx.restype = wintypes.BOOL

    VirtualAlloc = kernel32.VirtualAlloc
    VirtualAlloc.argtypes = [wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    VirtualAlloc.restype = wintypes.LPVOID

    VirtualFree = kernel32.VirtualFree
    VirtualFree.argtypes = [wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD]
    VirtualFree.restype = wintypes.BOOL


class AlignedBuffer:
    """VirtualAlloc で確保したセクターアライメント済みメモリバッファ"""
    def __init__(self, size: int):
        self.size = size
        if sys.platform == 'win32':
            self.ptr = VirtualAlloc(None, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
            if not self.ptr:
                raise MemoryError("Failed to allocate aligned memory via VirtualAlloc")
        else:
            self.buffer = bytearray(size)
            self.ptr = (ctypes.c_char * size).from_buffer(self.buffer)

    def fill_pattern(self, pattern: bytes = b'\xAA'):
        """バッファを指定パターンで満たす"""
        ctypes.memset(self.ptr, pattern[0], self.size)

    def free(self):
        if sys.platform == 'win32' and self.ptr:
            VirtualFree(self.ptr, 0, MEM_RELEASE)
            self.ptr = None


class Win32DirectIO:
    """
    Win32 Unbuffered Direct I/O
    FILE_FLAG_NO_BUFFERING および FILE_FLAG_WRITE_THROUGH により
    OSキャッシュを完全にバイパスして直接ディスクにアクセスします。
    """
    def __init__(self, filepath: str, direct_io: bool = True):
        self.filepath = filepath
        self.direct_io = direct_io and (sys.platform == 'win32')
        self.handle = None

    def open_for_write(self):
        if self.direct_io:
            flags = FILE_ATTRIBUTE_NORMAL | FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH
            self.handle = CreateFileW(
                self.filepath,
                GENERIC_READ | GENERIC_WRITE,
                0,  # 排他アクセス
                None,
                CREATE_ALWAYS,
                flags,
                None
            )
            if self.handle == INVALID_HANDLE_VALUE:
                error_code = kernel32.GetLastError()
                # Direct I/O で権限等エラーになった場合はフォールバック
                flags = FILE_ATTRIBUTE_NORMAL
                self.direct_io = False
                self.handle = CreateFileW(
                    self.filepath, GENERIC_WRITE, 0, None, CREATE_ALWAYS, flags, None
                )
                if self.handle == INVALID_HANDLE_VALUE:
                    raise IOError(f"Failed to open file for write: Windows Error {error_code}")
        else:
            self.fp = open(self.filepath, 'wb+')

    def open_for_read(self):
        if self.direct_io:
            flags = FILE_ATTRIBUTE_NORMAL | FILE_FLAG_NO_BUFFERING
            self.handle = CreateFileW(
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
                self.direct_io = False
                self.fp = open(self.filepath, 'rb')
        else:
            self.fp = open(self.filepath, 'rb')

    def seek(self, offset: int):
        if self.direct_io and self.handle:
            new_pos = ctypes.c_int64()
            SetFilePointerEx(self.handle, ctypes.c_int64(offset), ctypes.byref(new_pos), 0)  # FILE_BEGIN = 0
        elif hasattr(self, 'fp'):
            self.fp.seek(offset)

    def write(self, buffer: AlignedBuffer, size: int) -> int:
        if self.direct_io and self.handle:
            written = wintypes.DWORD(0)
            res = WriteFile(self.handle, buffer.ptr, size, ctypes.byref(written), None)
            if not res:
                raise IOError(f"Win32 WriteFile failed: Code {kernel32.GetLastError()}")
            return written.value
        elif hasattr(self, 'fp'):
            # Fallback
            raw_bytes = ctypes.string_at(buffer.ptr, size) if hasattr(buffer, 'ptr') else buffer.buffer[:size]
            self.fp.write(raw_bytes)
            self.fp.flush()
            os.fsync(self.fp.fileno())
            return size
        return 0

    def read(self, buffer: AlignedBuffer, size: int) -> int:
        if self.direct_io and self.handle:
            read_bytes = wintypes.DWORD(0)
            res = ReadFile(self.handle, buffer.ptr, size, ctypes.byref(read_bytes), None)
            if not res:
                raise IOError(f"Win32 ReadFile failed: Code {kernel32.GetLastError()}")
            return read_bytes.value
        elif hasattr(self, 'fp'):
            data = self.fp.read(size)
            return len(data)
        return 0

    def close(self):
        if self.direct_io and self.handle:
            CloseHandle(self.handle)
            self.handle = None
        elif hasattr(self, 'fp') and not self.fp.closed:
            self.fp.close()
