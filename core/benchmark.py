import os
import time
import random
import threading
from typing import Callable, Optional, Dict, Any
from core.win32_io import Win32DirectIO, AlignedBuffer

SECTOR_SIZE = 4096  # 4KiB Sector

class BenchmarkRunner:
    def __init__(self, target_dir: str, file_size_mb: int = 512):
        self.target_dir = target_dir
        self.file_size_bytes = file_size_mb * 1024 * 1024
        
        # 書き込み権限テスト (C:\ 直下などは権限が必要なため TEMP ディレクトリにフォールバック)
        test_path = os.path.join(target_dir, "ssdspeed_test.dat")
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
                self.test_filename = os.path.join(system_temp, "ssdspeed_test.dat")
            else:
                self.test_filename = test_path

        self.is_running = False
        self.should_stop = False

        self.current_status = {
            "status": "idle",
            "current_test": "",
            "progress_percent": 0.0,
            "current_speed_mbs": 0.0,
            "current_iops": 0.0,
            "error_msg": "",
            "results": {
                "seq_write_mbs": 0.0,
                "seq_read_mbs": 0.0,
                "rnd4k_write_mbs": 0.0,
                "rnd4k_write_iops": 0.0,
                "rnd4k_read_mbs": 0.0,
                "rnd4k_read_iops": 0.0,
                "rnd4k_q32_write_mbs": 0.0,
                "rnd4k_q32_write_iops": 0.0,
                "rnd4k_q32_read_mbs": 0.0,
                "rnd4k_q32_read_iops": 0.0,
            }
        }

    def stop(self):
        self.should_stop = True

    def run_all(self, progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.is_running = True
        self.should_stop = False
        self.current_status["status"] = "running"
        self.current_status["error_msg"] = ""

        try:
            # 1. Sequential Write Test (1MiB)
            self._run_seq_write(progress_callback)
            if self.should_stop:
                self.current_status["status"] = "stopped"
                return

            # 2. Sequential Read Test (1MiB)
            self._run_seq_read(progress_callback)
            if self.should_stop:
                self.current_status["status"] = "stopped"
                return

            # 3. Random 4K Q1T1 Write Test
            self._run_random_4k_write(q_depth=1, callback=progress_callback)
            if self.should_stop:
                self.current_status["status"] = "stopped"
                return

            # 4. Random 4K Q1T1 Read Test
            self._run_random_4k_read(q_depth=1, callback=progress_callback)
            if self.should_stop:
                self.current_status["status"] = "stopped"
                return

            # 5. Random 4K Q32T1 Write Test
            self._run_random_4k_write(q_depth=32, callback=progress_callback)
            if self.should_stop:
                self.current_status["status"] = "stopped"
                return

            # 6. Random 4K Q32T1 Read Test
            self._run_random_4k_read(q_depth=32, callback=progress_callback)
            if self.should_stop:
                self.current_status["status"] = "stopped"
                return

            self.current_status["status"] = "completed"
            self.current_status["progress_percent"] = 100.0
            self.current_status["current_test"] = "ベンチマーク完了"
        except Exception as e:
            self.current_status["status"] = "error"
            self.current_status["error_msg"] = str(e)
            self.current_status["current_test"] = f"エラー: {str(e)}"
        finally:
            self._cleanup()
            self.is_running = False
            if progress_callback:
                progress_callback(self.current_status)

    def _run_seq_write(self, callback):
        self.current_status["current_test"] = "シーケンシャル書き込み (1MiB)"
        block_size = 1024 * 1024  # 1MB
        blocks = max(1, self.file_size_bytes // block_size)

        io = Win32DirectIO(self.test_filename, direct_io=True)
        buffer = AlignedBuffer(block_size)
        buffer.fill_pattern(b'\xA5')

        try:
            io.open_for_write()
            start_time = time.perf_counter()
            written_bytes = 0

            for i in range(blocks):
                if self.should_stop: break
                io.write(buffer, block_size)
                written_bytes += block_size

                elapsed = time.perf_counter() - start_time
                if elapsed > 0:
                    speed = (written_bytes / (1024 * 1024)) / elapsed
                    self.current_status["current_speed_mbs"] = round(speed, 2)
                    self.current_status["current_iops"] = round(speed * 1024 / 1024, 1)
                    self.current_status["progress_percent"] = round((i + 1) / blocks * 100, 1)
                    self.current_status["results"]["seq_write_mbs"] = round(speed, 2)
                    if callback:
                        callback(self.current_status)
        finally:
            io.close()
            buffer.free()

    def _run_seq_read(self, callback):
        self.current_status["current_test"] = "シーケンシャル読み込み (1MiB)"
        block_size = 1024 * 1024  # 1MB
        blocks = max(1, self.file_size_bytes // block_size)

        io = Win32DirectIO(self.test_filename, direct_io=True)
        buffer = AlignedBuffer(block_size)

        try:
            io.open_for_read()
            start_time = time.perf_counter()
            read_bytes = 0

            for i in range(blocks):
                if self.should_stop: break
                io.read(buffer, block_size)
                read_bytes += block_size

                elapsed = time.perf_counter() - start_time
                if elapsed > 0:
                    speed = (read_bytes / (1024 * 1024)) / elapsed
                    self.current_status["current_speed_mbs"] = round(speed, 2)
                    self.current_status["current_iops"] = round(speed * 1024 / 1024, 1)
                    self.current_status["progress_percent"] = round((i + 1) / blocks * 100, 1)
                    self.current_status["results"]["seq_read_mbs"] = round(speed, 2)
                    if callback:
                        callback(self.current_status)
        finally:
            io.close()
            buffer.free()

    def _run_random_4k_write(self, q_depth: int, callback):
        test_name = f"ランダム 4KiB 書き込み (Q{q_depth}T1)"
        self.current_status["current_test"] = test_name
        block_size = SECTOR_SIZE  # 4KB
        total_sectors = max(1, self.file_size_bytes // block_size)
        num_ops = min(1500 * (1 if q_depth == 1 else 2), 5000)

        io = Win32DirectIO(self.test_filename, direct_io=True)
        buffer = AlignedBuffer(block_size)
        buffer.fill_pattern(b'\x5A')

        try:
            io.open_for_write()
            offsets = [random.randint(0, total_sectors - 1) * block_size for _ in range(num_ops)]
            
            start_time = time.perf_counter()
            completed_ops = 0

            for idx, offset in enumerate(offsets):
                if self.should_stop: break
                io.seek(offset)
                io.write(buffer, block_size)
                completed_ops += 1

                elapsed = time.perf_counter() - start_time
                if elapsed > 0:
                    iops = completed_ops / elapsed
                    speed = (completed_ops * block_size / (1024 * 1024)) / elapsed
                    self.current_status["current_speed_mbs"] = round(speed, 2)
                    self.current_status["current_iops"] = round(iops, 1)
                    self.current_status["progress_percent"] = round((idx + 1) / num_ops * 100, 1)
                    
                    res_key_mbs = "rnd4k_write_mbs" if q_depth == 1 else "rnd4k_q32_write_mbs"
                    res_key_iops = "rnd4k_write_iops" if q_depth == 1 else "rnd4k_q32_write_iops"
                    self.current_status["results"][res_key_mbs] = round(speed, 2)
                    self.current_status["results"][res_key_iops] = round(iops, 1)

                    if callback and (idx % 20 == 0 or idx == num_ops - 1):
                        callback(self.current_status)
        finally:
            io.close()
            buffer.free()

    def _run_random_4k_read(self, q_depth: int, callback):
        test_name = f"ランダム 4KiB 読み込み (Q{q_depth}T1)"
        self.current_status["current_test"] = test_name
        block_size = SECTOR_SIZE  # 4KB
        total_sectors = max(1, self.file_size_bytes // block_size)
        num_ops = min(1500 * (1 if q_depth == 1 else 2), 5000)

        io = Win32DirectIO(self.test_filename, direct_io=True)
        buffer = AlignedBuffer(block_size)

        try:
            io.open_for_read()
            offsets = [random.randint(0, total_sectors - 1) * block_size for _ in range(num_ops)]
            
            start_time = time.perf_counter()
            completed_ops = 0

            for idx, offset in enumerate(offsets):
                if self.should_stop: break
                io.seek(offset)
                io.read(buffer, block_size)
                completed_ops += 1

                elapsed = time.perf_counter() - start_time
                if elapsed > 0:
                    iops = completed_ops / elapsed
                    speed = (completed_ops * block_size / (1024 * 1024)) / elapsed
                    self.current_status["current_speed_mbs"] = round(speed, 2)
                    self.current_status["current_iops"] = round(iops, 1)
                    self.current_status["progress_percent"] = round((idx + 1) / num_ops * 100, 1)

                    res_key_mbs = "rnd4k_read_mbs" if q_depth == 1 else "rnd4k_q32_read_mbs"
                    res_key_iops = "rnd4k_read_iops" if q_depth == 1 else "rnd4k_q32_read_iops"
                    self.current_status["results"][res_key_mbs] = round(speed, 2)
                    self.current_status["results"][res_key_iops] = round(iops, 1)

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
