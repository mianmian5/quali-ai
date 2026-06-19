"""QualiAI WebUI — FastAPI 后端

提供 REST API + SSE 流式接口，前端展示测试执行过程。
"""

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from core.planner import AITestPlanner
from core.executor import PlaywrightExecutor
from core.adb_executor import ADBExecutor
from core.reporter import HTMLReporter

app = FastAPI(title="QualiAI WebUI", version="0.1.0")

web_dir = Path(__file__).resolve().parent
STATIC_DIR = web_dir / "static"
TEMPLATES_DIR = web_dir / "templates"
REPORTS_DIR = web_dir / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# In-memory task store
tasks: dict[str, dict] = {}
task_events: dict[str, asyncio.Queue] = {}


@app.get("/", response_class=HTMLResponse)
async def index():
    html = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.post("/api/plan")
async def plan_test(request: Request):
    """解析自然语言为测试步骤"""
    data = await request.json()
    description = data.get("description", "").strip()
    target_type = data.get("type", "web")  # web / android
    app_package = data.get("app", "")
    url = data.get("url", "")

    if not description:
        return JSONResponse({"error": "请输入测试描述"}, status_code=400)

    planner = AITestPlanner()
    base_url = url if target_type == "web" else app_package
    steps = planner.plan(description, base_url=base_url)

    return JSONResponse({
        "steps": steps,
        "total": len(steps),
        "type": target_type,
    })


@app.post("/api/run")
async def run_test(request: Request):
    """启动测试执行"""
    data = await request.json()
    description = data.get("description", "").strip()
    steps = data.get("steps", [])
    target_type = data.get("type", "web")
    device_id = data.get("device", "")

    if not steps:
        return JSONResponse({"error": "没有测试步骤"}, status_code=400)

    task_id = uuid.uuid4().hex[:12]
    task_events[task_id] = asyncio.Queue()

    tasks[task_id] = {
        "id": task_id,
        "description": description,
        "status": "running",
        "progress": 0,
        "started_at": time.time(),
    }

    asyncio.create_task(_execute_task(task_id, steps, target_type, device_id))
    return JSONResponse({"task_id": task_id})


@app.get("/api/stream/{task_id}")
async def stream_task(task_id: str):
    """SSE 流式返回测试执行进度"""
    queue = task_events.get(task_id)

    async def event_generator():
        if not queue:
            yield "data: {\"type\": \"error\", \"message\": \"task not found\"}\n\n"
            return

        yield "data: {\"type\": \"start\"}\n\n"

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30)
                yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
                if event.get("type") in ("completed", "error"):
                    break
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"

        cleanup(task_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _execute_task(task_id: str, steps: list[dict], target_type: str, device_id: str):
    """后台执行测试"""
    results = []
    try:
        total = len(steps)

        if target_type == "android":
            executor = ADBExecutor(device_id=device_id if device_id else None)
            for i, step in enumerate(steps):
                await _send_progress(task_id, i, total, step)
                result = executor._execute_step(step)
                results.append(result)
                await _send_result(task_id, i, result)
        else:
            executor = PlaywrightExecutor(headless=True)
            # PlaywrightExecutor.run() handles init/cleanup internally
            all_results = executor.run(steps)
            for i, result in enumerate(all_results):
                await _send_progress(task_id, i, total, steps[i] if i < len(steps) else {})
                await _send_result(task_id, i, result)
                results.append(result)

        # complete
        passed = sum(1 for r in results if r.get("passed"))
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100

        # generate report
        description = tasks[task_id].get("description", "test")
        reporter = HTMLReporter(str(REPORTS_DIR))
        report_path = reporter.generate(description, steps, results)
        report_filename = os.path.basename(report_path)

        await _send(task_id, {
            "type": "completed",
            "passed": passed,
            "total": total,
            "failed": total - passed,
            "results": results,
            "report": report_filename,
        })

    except Exception as e:
        tasks[task_id]["status"] = "error"
        await _send(task_id, {"type": "error", "message": str(e)})


async def _send(task_id: str, event: dict):
    queue = task_events.get(task_id)
    if queue:
        await queue.put(event)


async def _send_progress(task_id: str, step_idx: int, total: int, step: dict):
    progress = int(((step_idx + 1) / total) * 100) if total > 0 else 0
    t = tasks.get(task_id, {})
    t["progress"] = progress
    await _send(task_id, {
        "type": "progress",
        "step": step_idx + 1,
        "total": total,
        "progress": progress,
        "action": step.get("action", ""),
        "desc": step.get("desc", ""),
    })


async def _send_result(task_id: str, step_idx: int, result: dict):
    await _send(task_id, {
        "type": "step_result",
        "step": result.get("step", step_idx + 1),
        "action": result.get("action", ""),
        "passed": result.get("passed", False),
        "reason": result.get("reason", ""),
        "duration": result.get("duration", 0),
        "screenshot": result.get("screenshot", ""),
    })


def cleanup(task_id: str):
    task_events.pop(task_id, None)
    tasks.pop(task_id, None)


@app.get("/api/reports")
async def list_reports():
    """列出已有测试报告"""
    report_files = sorted(REPORTS_DIR.glob("*.html"), key=os.path.getmtime, reverse=True)
    reports = []
    for f in report_files[:20]:
        reports.append({
            "name": f.stem,
            "path": f.name,
            "size": f.stat().st_size,
            "time": time.strftime("%Y-%m-%d %H:%M", time.localtime(f.stat().st_mtime)),
        })
    return JSONResponse(reports)


@app.get("/api/reports/{filename}")
async def get_report(filename: str):
    """返回测试报告文件"""
    filepath = REPORTS_DIR / filename
    if not filepath.exists():
        raise HTTPException(404, "Report not found")
    return FileResponse(str(filepath), media_type="text/html")
