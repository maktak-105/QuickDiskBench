import os
import sys
import threading
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.drive_manager import get_drive_list
from core.benchmark import BenchmarkRunner

app = FastAPI(title="QuickDiskBench Benchmark API")

# 静的ファイル & テンプレートはリポジトリ直下。このファイルは python/browser/main.py。
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# グローバルベンチマークランナー
current_runner: BenchmarkRunner = None
runner_thread: threading.Thread = None

class StartRequest(BaseModel):
    drive: str
    file_size_mb: int = 512
    profile: str = "cdm"  # "cdm" (with cache) or "raw" (without cache)
    passes: int = 1       # 1, 3, 5, 9
    timeout_sec: float = 60.0

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/drives")
async def list_drives():
    return get_drive_list()

@app.post("/api/start")
async def start_benchmark(req: StartRequest):
    global current_runner, runner_thread

    if current_runner and current_runner.is_running:
        return JSONResponse({"status": "error", "message": "ベンチマークが既に実行中です。"}, status_code=400)

    # ディレクトリの存在確認
    target_dir = req.drive
    if not os.path.exists(target_dir):
        return JSONResponse({"status": "error", "message": f"ドライブ {target_dir} が見つかりません。"}, status_code=404)

    current_runner = BenchmarkRunner(
        target_dir=target_dir,
        file_size_mb=req.file_size_mb,
        profile=req.profile,
        passes=req.passes,
        timeout_sec=req.timeout_sec
    )
    
    runner_thread = threading.Thread(target=current_runner.run_all, daemon=True)
    runner_thread.start()

    return {"status": "ok", "message": "ベンチマークを開始しました。"}

@app.post("/api/stop")
async def stop_benchmark():
    global current_runner
    if current_runner and current_runner.is_running:
        current_runner.stop()
        return {"status": "ok", "message": "停止要求を送信しました。"}
    return {"status": "ok", "message": "実行中ではありません。"}

@app.get("/api/status")
async def get_status():
    global current_runner
    if current_runner:
        return current_runner.current_status
    return {
        "status": "idle",
        "current_test": "",
        "progress_percent": 0.0,
        "current_speed_mbs": 0.0,
        "current_iops": 0.0,
        "elapsed_seconds": 0.0,
        "results": {}
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
