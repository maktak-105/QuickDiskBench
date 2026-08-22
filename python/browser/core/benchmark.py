import os
import sys
import time
import random
import ctypes
from ctypes import wintypes
from typing import Callable, Optional, Dict, Any, List
from core.win32_io import Win32DirectIO, AlignedBuffer, OVERLAPPED, kernel32, WAIT_OBJECT_0, ERROR_IO_PENDING

SECTOR_SIZE = 4096  # 4KiB Sector
DEFAULT_BENCHMARK_TIMEOUT_SEC = 60.0

# C++ Native Engine DLL Loader
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
NATIVE_DLL_PATH = os.path.join(_REPO_ROOT, "core", "native", "engine_x64.dll")
native_dll = None
PROGRESS_CALLBACK_TYPE = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_double, ctypes.c_double, ctypes.c_double)

if sys.platform == 'win32' and os.path.exists(NATIVE_DLL_PATH):
    try:
        native_dll = ctypes.CDLL(NATIVE_DLL_PATH)
        native_dll.run_benchmark_test.restype = ctypes.c_int
        native_dll.run_benchmark_test.argtypes = [
            wintypes.LPCWSTR,
            ctypes.c_int,
            ctypes.c_uint64,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            PROGRESS_CALLBACK_TYPE,
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double)
        ]
        native_dll.set_benchmark_timeout_sec.restype = ctypes.c_int
        native_dll.set_benchmark_timeout_sec.argtypes = [ctypes.c_double]
    except Exception as e:
        print(f"[警告] C++ ネイティブ DLL のロードに失敗しました: {e}")
        native_dll = None

import statistics

class BenchmarkRunner:
    def __init__(self, target_dir: str, file_size_mb: int = 512, profile: str = "cdm", passes: int = 1, timeout_sec: float = DEFAULT_BENCHMARK_TIMEOUT_SEC):
        self.target_dir = target_dir
        self.file_size_bytes = file_size_mb * 1024 * 1024
        self.profile = profile.lower()  # "cdm" (with cache) or "raw" (without cache)
        self.passes = max(1, min(passes, 9))
        self.timeout_sec = max(1.0, min(float(timeout_sec), 3600.0))
        self.write_through = (self.profile == "raw")
        
        # 書き込み権限テスト (C:\ 直下などは権限が必要なため TEMP ディレクトリにフォールバック)
        test_path = os.path.join(target_dir, "QuickDiskBench_test.dat")
        try:
            with open(test_path, 'a') as f:
                pass
            os.remove(test_path)
            self.test_filename = test_path
        except (PermissionError, OSError):
            import tempfile
            drive_letter = os.path.splitdrive(target_dir)[0].upper()
            system_temp = tempfile.gettempdir()
            system_drive = os.path.splitdrive(system_temp)[0].upper()
            if drive_letter == system_drive:
                self.test_filename = os.path.join(system_temp, "QuickDiskBench_test.dat")
            else:
                self.test_filename = test_path

        self.is_running = False
        self.should_stop = False
        self._stop_flag = ctypes.c_int(0)
        self._benchmark_start_time = None

        self.current_status = {
            "status": "idle",
            "profile": self.profile,
            "passes": self.passes,
            "current_pass": 1,
            "engine": "C++ Native (LLVM Clang)" if native_dll else "Python Win32 DirectIO",
            "current_test": "",
            "progress_percent": 0.0,
            "current_speed_mbs": 0.0,
            "current_iops": 0.0,
            "elapsed_seconds": 0.0,
            "error_msg": "",
            "results": {
                # 1. SEQ1M Q8T1
                "seq_q8_read_mbs": 0.0,
                "seq_q8_read_std": 0.0,
                "seq_q8_write_mbs": 0.0,
                "seq_q8_write_std": 0.0,
                # 2. SEQ1M Q1T1
                "seq_read_mbs": 0.0,
                "seq_read_std": 0.0,
                "seq_write_mbs": 0.0,
                "seq_write_std": 0.0,
                # 3. RND4K Q32T1
                "rnd4k_q32_read_mbs": 0.0,
                "rnd4k_q32_read_std": 0.0,
                "rnd4k_q32_read_iops": 0.0,
                "rnd4k_q32_write_mbs": 0.0,
                "rnd4k_q32_write_std": 0.0,
                "rnd4k_q32_write_iops": 0.0,
                # 4. RND4K Q1T1
                "rnd4k_read_mbs": 0.0,
                "rnd4k_read_std": 0.0,
                "rnd4k_read_iops": 0.0,
                "rnd4k_write_mbs": 0.0,
                "rnd4k_write_std": 0.0,
                "rnd4k_write_iops": 0.0,
            }
        }

    def stop(self):
        self.should_stop = True
        self._stop_flag.value = 1

    def _update_elapsed(self):
        if self._benchmark_start_time is not None:
            self.current_status["elapsed_seconds"] = round(
                max(0.0, time.perf_counter() - self._benchmark_start_time), 3
            )

    def run_all(self, progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.is_running = True
        self.should_stop = False
        self._stop_flag.value = 0
        self._benchmark_start_time = time.perf_counter()
        self.current_status["status"] = "running"
        self.current_status["error_msg"] = ""

        try:
            # 1. SEQ1M Q8T1 (Write & Read)
            self._run_multi_pass(self._run_seq_q8_write, "seq_q8_write_mbs", None, progress_callback)
            if self.should_stop: return
            self._run_multi_pass(self._run_seq_q8_read, "seq_q8_read_mbs", None, progress_callback)
            if self.should_stop: return

            # 2. SEQ1M Q1T1 (Write & Read)
            self._run_multi_pass(self._run_seq_q1_write, "seq_write_mbs", None, progress_callback)
            if self.should_stop: return
            self._run_multi_pass(self._run_seq_q1_read, "seq_read_mbs", None, progress_callback)
            if self.should_stop: return

            # 3. RND4K Q32T1 (Write & Read)
            self._run_multi_pass(self._run_random_4k_q32_write, "rnd4k_q32_write_mbs", "rnd4k_q32_write_iops", progress_callback)
            if self.should_stop: return
            self._run_multi_pass(self._run_random_4k_q32_read, "rnd4k_q32_read_mbs", "rnd4k_q32_read_iops", progress_callback)
            if self.should_stop: return

            # 4. RND4K Q1T1 (Write & Read)
            self._run_multi_pass(self._run_random_4k_q1_write, "rnd4k_write_mbs", "rnd4k_write_iops", progress_callback)
            if self.should_stop: return
            self._run_multi_pass(self._run_random_4k_q1_read, "rnd4k_read_mbs", "rnd4k_read_iops", progress_callback)
            if self.should_stop: return

            self.current_status["status"] = "completed"
            self.current_status["progress_percent"] = 100.0
            self.current_status["current_test"] = "ベンチマーク完了"
        except Exception as e:
            self.current_status["status"] = "error"
            self.current_status["error_msg"] = str(e)
            self.current_status["current_test"] = f"エラー: {str(e)}"
        finally:
            self._update_elapsed()
            self._cleanup()
            self.is_running = False
            if progress_callback:
                progress_callback(self.current_status)

    def _run_multi_pass(self, test_fn, res_key_mbs: str, res_key_iops: Optional[str], callback):
        samples_mbs = []
        samples_iops = []

        for p in range(self.passes):
            if self.should_stop: break
            self.current_status["current_pass"] = p + 1
            test_fn(callback)
            
            # Record current pass result
            cur_mbs = self.current_status["results"].get(res_key_mbs, 0.0)
            if cur_mbs > 0:
                samples_mbs.append(cur_mbs)
            if res_key_iops:
                cur_iops = self.current_status["results"].get(res_key_iops, 0.0)
                if cur_iops > 0:
                    samples_iops.append(cur_iops)

        if samples_mbs:
            mean_val = statistics.mean(samples_mbs)
            std_val = statistics.stdev(samples_mbs) if len(samples_mbs) > 1 else 0.0
            self.current_status["results"][res_key_mbs] = round(mean_val, 2)
            self.current_status["results"][res_key_mbs.replace("_mbs", "") + "_std"] = round(std_val, 2)
            self.current_status["results"][res_key_mbs.replace("_mbs", "") + "_max"] = round(max(samples_mbs), 2)
            self.current_status["results"][res_key_mbs.replace("_mbs", "") + "_min"] = round(min(samples_mbs), 2)

        if res_key_iops and samples_iops:
            mean_iops = statistics.mean(samples_iops)
            std_iops = statistics.stdev(samples_iops) if len(samples_iops) > 1 else 0.0
            self.current_status["results"][res_key_iops] = round(mean_iops, 1)
            self.current_status["results"][res_key_iops.replace("_iops", "") + "_iops_std"] = round(std_iops, 1)

    def _run_native(self, test_type: int, block_size: int, q_depth: int, test_name: str, res_key_mbs: str, res_key_iops: Optional[str], callback) -> bool:
        if not native_dll:
            return False

        if native_dll.set_benchmark_timeout_sec(ctypes.c_double(self.timeout_sec)) != 0:
            return False

        pass_label = f" (Pass {self.current_status.get('current_pass', 1)}/{self.passes})" if self.passes > 1 else ""
        self.current_status["current_test"] = test_name + pass_label
        out_speed = ctypes.c_double(0.0)
        out_iops = ctypes.c_double(0.0)

        def on_prog(name, speed, iops, pct):
            self._update_elapsed()
            self.current_status["current_speed_mbs"] = round(speed, 2)
            self.current_status["current_iops"] = round(iops, 1)
            self.current_status["progress_percent"] = round(pct, 1)
            self.current_status["results"][res_key_mbs] = round(speed, 2)
            if res_key_iops:
                self.current_status["results"][res_key_iops] = round(iops, 1)
            if callback:
                callback(self.current_status)

        cb = PROGRESS_CALLBACK_TYPE(on_prog)
        wt = 1 if (self.write_through and (test_type == 1 or test_type == 3)) else 0

        res = native_dll.run_benchmark_test(
            self.test_filename,
            test_type,
            self.file_size_bytes,
            block_size,
            q_depth,
            wt,
            cb,
            ctypes.byref(self._stop_flag),
            ctypes.byref(out_speed),
            ctypes.byref(out_iops)
        )

        if res == 0:
            self.current_status["results"][res_key_mbs] = round(out_speed.value, 2)
            if res_key_iops:
                self.current_status["results"][res_key_iops] = round(out_iops.value, 1)
            return True
        return False

    # -------------------------------------------------------------
    # 1. SEQ1M Q8T1 (1MB Block, Queue Depth = 8)
    # -------------------------------------------------------------
    def _run_seq_q8_write(self, callback):
        if self._run_native(1, 1024 * 1024, 8, "SEQ1M Q8T1 書き込み", "seq_q8_write_mbs", None, callback):
            return

        self.current_status["current_test"] = "SEQ1M Q8T1 書き込み"
        block_size = 1024 * 1024  # 1MB
        blocks = max(1, self.file_size_bytes // block_size)

        io = Win32DirectIO(self.test_filename, direct_io=True, write_through=self.write_through)
        io.preallocate(self.file_size_bytes)
        io.open_for_write()
        buffer = AlignedBuffer(block_size)
        buffer.fill_pattern(0xA5)

        try:
            start_time = time.perf_counter()
            written_bytes = 0
            for i in range(blocks):
                if self.should_stop: break
                io.write_sync(buffer, block_size)
                written_bytes += block_size

                elapsed = time.perf_counter() - start_time
                if elapsed > 0:
                    speed = (written_bytes / (1024 * 1024)) / elapsed
                    self.current_status["current_speed_mbs"] = round(speed, 2)
                    self.current_status["current_iops"] = round(speed * 1024 / 1024, 1)
                    self.current_status["progress_percent"] = round((i + 1) / blocks * 100, 1)
                    self.current_status["results"]["seq_q8_write_mbs"] = round(speed, 2)
                    if callback: callback(self.current_status)
        finally:
            io.close()
            buffer.free()

    def _run_seq_q8_read(self, callback):
        if self._run_native(2, 1024 * 1024, 8, "SEQ1M Q8T1 読み込み", "seq_q8_read_mbs", None, callback):
            return

        self.current_status["current_test"] = "SEQ1M Q8T1 読み込み"
        block_size = 1024 * 1024  # 1MB
        blocks = max(1, self.file_size_bytes // block_size)

        io = Win32DirectIO(self.test_filename, direct_io=True)
        io.open_for_read()
        buffer = AlignedBuffer(block_size)

        try:
            start_time = time.perf_counter()
            read_bytes = 0
            for i in range(blocks):
                if self.should_stop: break
                io.read_sync(buffer, block_size)
                read_bytes += block_size

                elapsed = time.perf_counter() - start_time
                if elapsed > 0:
                    speed = (read_bytes / (1024 * 1024)) / elapsed
                    self.current_status["current_speed_mbs"] = round(speed, 2)
                    self.current_status["current_iops"] = round(speed * 1024 / 1024, 1)
                    self.current_status["progress_percent"] = round((i + 1) / blocks * 100, 1)
                    self.current_status["results"]["seq_q8_read_mbs"] = round(speed, 2)
                    if callback: callback(self.current_status)
        finally:
            io.close()
            buffer.free()

    # -------------------------------------------------------------
    # 2. SEQ1M Q1T1 (1MB Block, Queue Depth = 1)
    # -------------------------------------------------------------
    def _run_seq_q1_write(self, callback):
        if self._run_native(1, 1024 * 1024, 1, "SEQ1M Q1T1 書き込み", "seq_write_mbs", None, callback):
            return

        self.current_status["current_test"] = "SEQ1M Q1T1 書き込み"
        block_size = 1024 * 1024  # 1MB
        blocks = max(1, self.file_size_bytes // block_size)

        io = Win32DirectIO(self.test_filename, direct_io=True, write_through=self.write_through)
        io.open_for_write()
        buffer = AlignedBuffer(block_size)
        buffer.fill_pattern(0x5A)

        try:
            io.seek(0)
            start_time = time.perf_counter()
            written_bytes = 0
            for i in range(blocks):
                if self.should_stop: break
                io.write_sync(buffer, block_size)
                written_bytes += block_size

                elapsed = time.perf_counter() - start_time
                if elapsed > 0:
                    speed = (written_bytes / (1024 * 1024)) / elapsed
                    self.current_status["current_speed_mbs"] = round(speed, 2)
                    self.current_status["current_iops"] = round(speed * 1024 / 1024, 1)
                    self.current_status["progress_percent"] = round((i + 1) / blocks * 100, 1)
                    self.current_status["results"]["seq_write_mbs"] = round(speed, 2)
                    if callback: callback(self.current_status)
        finally:
            io.close()
            buffer.free()

    def _run_seq_q1_read(self, callback):
        if self._run_native(2, 1024 * 1024, 1, "SEQ1M Q1T1 読み込み", "seq_read_mbs", None, callback):
            return

        self.current_status["current_test"] = "SEQ1M Q1T1 読み込み"
        block_size = 1024 * 1024  # 1MB
        blocks = max(1, self.file_size_bytes // block_size)

        io = Win32DirectIO(self.test_filename, direct_io=True)
        io.open_for_read()
        buffer = AlignedBuffer(block_size)

        try:
            io.seek(0)
            start_time = time.perf_counter()
            read_bytes = 0
            for i in range(blocks):
                if self.should_stop: break
                io.read_sync(buffer, block_size)
                read_bytes += block_size

                elapsed = time.perf_counter() - start_time
                if elapsed > 0:
                    speed = (read_bytes / (1024 * 1024)) / elapsed
                    self.current_status["current_speed_mbs"] = round(speed, 2)
                    self.current_status["current_iops"] = round(speed * 1024 / 1024, 1)
                    self.current_status["progress_percent"] = round((i + 1) / blocks * 100, 1)
                    self.current_status["results"]["seq_read_mbs"] = round(speed, 2)
                    if callback: callback(self.current_status)
        finally:
            io.close()
            buffer.free()

    # -------------------------------------------------------------
    # 3. RND4K Q32T1 (Random 4KB, Queue Depth = 32 Overlapped)
    # -------------------------------------------------------------
    def _run_random_4k_q32_write(self, callback):
        if self._run_native(3, SECTOR_SIZE, 32, "RND4K Q32T1 書き込み", "rnd4k_q32_write_mbs", "rnd4k_q32_write_iops", callback):
            return

        self.current_status["current_test"] = "RND4K Q32T1 書き込み"
        block_size = SECTOR_SIZE
        q_depth = 32
        total_sectors = max(1, self.file_size_bytes // block_size)
        num_ops = min(3000, total_sectors)
        max_duration = self.timeout_sec

        io = Win32DirectIO(self.test_filename, direct_io=True, write_through=self.write_through, overlapped=True)
        io.open_for_write()

        buffers = [AlignedBuffer(block_size) for _ in range(q_depth)]
        for buf in buffers: buf.fill_pattern(0x33)
        events = [kernel32.CreateEventW(None, True, False, None) for _ in range(q_depth)]
        overlapped_arr = (OVERLAPPED * q_depth)()
        events_arr = (wintypes.HANDLE * q_depth)(*events)

        for i in range(q_depth):
            overlapped_arr[i].hEvent = events[i]

        offsets = [random.randint(0, total_sectors - 1) * block_size for _ in range(num_ops)]
        
        try:
            start_time = time.perf_counter()
            issued_ops = 0
            completed_ops = 0
            active_slots = [False] * q_depth

            # Initial issue
            for i in range(q_depth):
                if issued_ops >= num_ops: break
                off = offsets[issued_ops]
                overlapped_arr[i].Offset = off & 0xFFFFFFFF
                overlapped_arr[i].OffsetHigh = (off >> 32) & 0xFFFFFFFF
                kernel32.ResetEvent(events[i])
                res = kernel32.WriteFile(io.handle, buffers[i].ptr, block_size, None, ctypes.byref(overlapped_arr[i]))
                if res or kernel32.GetLastError() == ERROR_IO_PENDING:
                    active_slots[i] = True
                    issued_ops += 1

            while completed_ops < num_ops:
                elapsed = time.perf_counter() - start_time
                if self.should_stop or elapsed >= max_duration: break

                wait_res = kernel32.WaitForMultipleObjects(q_depth, events_arr, False, 50)
                if WAIT_OBJECT_0 <= wait_res < WAIT_OBJECT_0 + q_depth:
                    slot = wait_res - WAIT_OBJECT_0
                    transferred = wintypes.DWORD(0)
                    if kernel32.GetOverlappedResult(io.handle, ctypes.byref(overlapped_arr[slot]), ctypes.byref(transferred), False):
                        completed_ops += 1
                        active_slots[slot] = False
                        kernel32.ResetEvent(events[slot])

                        if issued_ops < num_ops and not self.should_stop and (time.perf_counter() - start_time < max_duration):
                            off = offsets[issued_ops]
                            overlapped_arr[slot].Offset = off & 0xFFFFFFFF
                            overlapped_arr[slot].OffsetHigh = (off >> 32) & 0xFFFFFFFF
                            res = kernel32.WriteFile(io.handle, buffers[slot].ptr, block_size, None, ctypes.byref(overlapped_arr[slot]))
                            if res or kernel32.GetLastError() == ERROR_IO_PENDING:
                                active_slots[slot] = True
                                issued_ops += 1

                if elapsed > 0:
                    iops = completed_ops / elapsed
                    speed = (completed_ops * block_size / (1024 * 1024)) / elapsed
                    pct = min(100.0, (completed_ops / num_ops) * 100)
                    self.current_status["current_speed_mbs"] = round(speed, 2)
                    self.current_status["current_iops"] = round(iops, 1)
                    self.current_status["progress_percent"] = round(pct, 1)
                    self.current_status["results"]["rnd4k_q32_write_mbs"] = round(speed, 2)
                    self.current_status["results"]["rnd4k_q32_write_iops"] = round(iops, 1)
                    if callback and (completed_ops % 25 == 0 or completed_ops == num_ops):
                        callback(self.current_status)

            if self.should_stop:
                io.cancel_io()
        finally:
            io.close()
            for b in buffers: b.free()
            for ev in events: kernel32.CloseHandle(ev)

    def _run_random_4k_q32_read(self, callback):
        if self._run_native(4, SECTOR_SIZE, 32, "RND4K Q32T1 読み込み", "rnd4k_q32_read_mbs", "rnd4k_q32_read_iops", callback):
            return

        self.current_status["current_test"] = "RND4K Q32T1 読み込み"
        block_size = SECTOR_SIZE
        q_depth = 32
        total_sectors = max(1, self.file_size_bytes // block_size)
        num_ops = min(3000, total_sectors)
        max_duration = self.timeout_sec

        io = Win32DirectIO(self.test_filename, direct_io=True, overlapped=True)
        io.open_for_read()

        buffers = [AlignedBuffer(block_size) for _ in range(q_depth)]
        events = [kernel32.CreateEventW(None, True, False, None) for _ in range(q_depth)]
        overlapped_arr = (OVERLAPPED * q_depth)()
        events_arr = (wintypes.HANDLE * q_depth)(*events)

        for i in range(q_depth):
            overlapped_arr[i].hEvent = events[i]

        offsets = [random.randint(0, total_sectors - 1) * block_size for _ in range(num_ops)]
        
        try:
            start_time = time.perf_counter()
            issued_ops = 0
            completed_ops = 0
            active_slots = [False] * q_depth

            for i in range(q_depth):
                if issued_ops >= num_ops: break
                off = offsets[issued_ops]
                overlapped_arr[i].Offset = off & 0xFFFFFFFF
                overlapped_arr[i].OffsetHigh = (off >> 32) & 0xFFFFFFFF
                kernel32.ResetEvent(events[i])
                res = kernel32.ReadFile(io.handle, buffers[i].ptr, block_size, None, ctypes.byref(overlapped_arr[i]))
                if res or kernel32.GetLastError() == ERROR_IO_PENDING:
                    active_slots[i] = True
                    issued_ops += 1

            while completed_ops < num_ops:
                elapsed = time.perf_counter() - start_time
                if self.should_stop or elapsed >= max_duration: break

                wait_res = kernel32.WaitForMultipleObjects(q_depth, events_arr, False, 50)
                if WAIT_OBJECT_0 <= wait_res < WAIT_OBJECT_0 + q_depth:
                    slot = wait_res - WAIT_OBJECT_0
                    transferred = wintypes.DWORD(0)
                    if kernel32.GetOverlappedResult(io.handle, ctypes.byref(overlapped_arr[slot]), ctypes.byref(transferred), False):
                        completed_ops += 1
                        active_slots[slot] = False
                        kernel32.ResetEvent(events[slot])

                        if issued_ops < num_ops and not self.should_stop and (time.perf_counter() - start_time < max_duration):
                            off = offsets[issued_ops]
                            overlapped_arr[slot].Offset = off & 0xFFFFFFFF
                            overlapped_arr[slot].OffsetHigh = (off >> 32) & 0xFFFFFFFF
                            res = kernel32.ReadFile(io.handle, buffers[slot].ptr, block_size, None, ctypes.byref(overlapped_arr[slot]))
                            if res or kernel32.GetLastError() == ERROR_IO_PENDING:
                                active_slots[slot] = True
                                issued_ops += 1

                if elapsed > 0:
                    iops = completed_ops / elapsed
                    speed = (completed_ops * block_size / (1024 * 1024)) / elapsed
                    pct = min(100.0, (completed_ops / num_ops) * 100)
                    self.current_status["current_speed_mbs"] = round(speed, 2)
                    self.current_status["current_iops"] = round(iops, 1)
                    self.current_status["progress_percent"] = round(pct, 1)
                    self.current_status["results"]["rnd4k_q32_read_mbs"] = round(speed, 2)
                    self.current_status["results"]["rnd4k_q32_read_iops"] = round(iops, 1)
                    if callback and (completed_ops % 25 == 0 or completed_ops == num_ops):
                        callback(self.current_status)

            if self.should_stop:
                io.cancel_io()
        finally:
            io.close()
            for b in buffers: b.free()
            for ev in events: kernel32.CloseHandle(ev)

    # -------------------------------------------------------------
    # 4. RND4K Q1T1 (Random 4KB, Queue Depth = 1)
    # -------------------------------------------------------------
    def _run_random_4k_q1_write(self, callback):
        if self._run_native(3, SECTOR_SIZE, 1, "RND4K Q1T1 書き込み", "rnd4k_write_mbs", "rnd4k_write_iops", callback):
            return

        self.current_status["current_test"] = "RND4K Q1T1 書き込み"
        block_size = SECTOR_SIZE
        total_sectors = max(1, self.file_size_bytes // block_size)
        num_ops = min(2000, total_sectors)
        max_duration = self.timeout_sec

        io = Win32DirectIO(self.test_filename, direct_io=True, write_through=self.write_through)
        io.open_for_write()
        buffer = AlignedBuffer(block_size)
        buffer.fill_pattern(0x77)

        offsets = [random.randint(0, total_sectors - 1) * block_size for _ in range(num_ops)]
        try:
            start_time = time.perf_counter()
            completed_ops = 0
            for idx, offset in enumerate(offsets):
                elapsed = time.perf_counter() - start_time
                if self.should_stop or elapsed >= max_duration: break

                io.seek(offset)
                io.write_sync(buffer, block_size)
                completed_ops += 1

                if elapsed > 0:
                    iops = completed_ops / elapsed
                    speed = (completed_ops * block_size / (1024 * 1024)) / elapsed
                    pct = min(100.0, ((idx + 1) / num_ops) * 100)
                    self.current_status["current_speed_mbs"] = round(speed, 2)
                    self.current_status["current_iops"] = round(iops, 1)
                    self.current_status["progress_percent"] = round(pct, 1)
                    self.current_status["results"]["rnd4k_write_mbs"] = round(speed, 2)
                    self.current_status["results"]["rnd4k_write_iops"] = round(iops, 1)
                    if callback and (idx % 20 == 0 or idx == num_ops - 1):
                        callback(self.current_status)
        finally:
            io.close()
            buffer.free()

    def _run_random_4k_q1_read(self, callback):
        if self._run_native(4, SECTOR_SIZE, 1, "RND4K Q1T1 読み込み", "rnd4k_read_mbs", "rnd4k_read_iops", callback):
            return

        self.current_status["current_test"] = "RND4K Q1T1 読み込み"
        block_size = SECTOR_SIZE
        total_sectors = max(1, self.file_size_bytes // block_size)
        num_ops = min(2000, total_sectors)
        max_duration = self.timeout_sec

        io = Win32DirectIO(self.test_filename, direct_io=True)
        io.open_for_read()
        buffer = AlignedBuffer(block_size)

        offsets = [random.randint(0, total_sectors - 1) * block_size for _ in range(num_ops)]
        try:
            start_time = time.perf_counter()
            completed_ops = 0
            for idx, offset in enumerate(offsets):
                elapsed = time.perf_counter() - start_time
                if self.should_stop or elapsed >= max_duration: break

                io.seek(offset)
                io.read_sync(buffer, block_size)
                completed_ops += 1

                if elapsed > 0:
                    iops = completed_ops / elapsed
                    speed = (completed_ops * block_size / (1024 * 1024)) / elapsed
                    pct = min(100.0, ((idx + 1) / num_ops) * 100)
                    self.current_status["current_speed_mbs"] = round(speed, 2)
                    self.current_status["current_iops"] = round(iops, 1)
                    self.current_status["progress_percent"] = round(pct, 1)
                    self.current_status["results"]["rnd4k_read_mbs"] = round(speed, 2)
                    self.current_status["results"]["rnd4k_read_iops"] = round(iops, 1)
                    if callback and (idx % 20 == 0 or idx == num_ops - 1):
                        callback(self.current_status)
        finally:
            io.close()
            buffer.free()

    def _cleanup(self):
        if os.path.exists(self.test_filename):
            try:
                os.remove(self.test_filename)
            except Exception:
                pass
