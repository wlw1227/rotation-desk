"""
Rotation Intel Server
---------------------
FastAPI backend that:
  - Orchestrates all data collectors on a schedule
  - Runs Claude synthesis
  - Serves results to the dashboard via WebSocket + REST
  - Caches results so dashboard loads instantly

Run: python server.py
Dashboard: http://localhost:8000
"""

import os
import sys
import json
import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_ET = ZoneInfo('America/New_York')


def _load_credentials(config_path: str) -> None:
    """Read temp JSON credential file, inject into os.environ, then delete it."""
    try:
        with open(config_path) as f:
            creds = json.load(f)
        for k, v in creds.items():
            if v:
                os.environ[k] = str(v)
        Path(config_path).unlink(missing_ok=True)
    except Exception as e:
        print(f"Warning: could not load credential config file: {e}")


# Parse CLI args before any imports that read os.getenv at module level.
# parse_known_args so uvicorn's own args don't cause errors.
_parser = argparse.ArgumentParser(description="RotationDesk server")
_parser.add_argument("--config-path", default=None,
                     help="Path to JSON file with credentials (written by Tauri, deleted after read)")
_parser.add_argument("--data-dir", default=None,
                     help="App data directory; Telethon session file is written here")
_parser.add_argument("--port", type=int, default=int(os.getenv("PORT", 8000)),
                     help="HTTP/WebSocket port (default: 8000)")
_args, _ = _parser.parse_known_args()

if _args.config_path:
    _load_credentials(_args.config_path)
else:
    # Development fallback: load from .env file
    from dotenv import load_dotenv
    load_dotenv()

if _args.data_dir:
    # Change CWD so Telethon writes rotation_intel.session to the persistent data dir
    os.chdir(_args.data_dir)

sys.path.insert(0, str(Path(__file__).parent))

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from rich import print as rprint
import uvicorn

# Direct imports — all collector/synthesis files live in the project root
from defillama import collect_all as collect_defillama
from telegram import collect_telegram_signals
from claude_engine import synthesize

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    rprint("[bold]Rotation Intel starting...[/bold]")
    asyncio.create_task(run_pipeline())
    scheduler.add_job(run_pipeline, "interval", hours=6, id="pipeline", replace_existing=True)
    scheduler.start()
    rprint("[green]Scheduler started — pipeline runs every 6 hours[/green]")
    rprint(f"[green]Dashboard: http://localhost:{os.getenv('PORT', 8000)}[/green]")
    yield
    scheduler.shutdown()

app = FastAPI(title="Rotation Intel", lifespan=lifespan)

# ── State ──────────────────────────────────────────────────────────────────────

state = {
    "last_run": None,
    "defillama": {},
    "telegram": {},
    "synthesis": {},
    "status": "initializing",
    "next_run": None,
}

connected_clients: list[WebSocket] = []

# ── Data Pipeline ──────────────────────────────────────────────────────────────

async def run_pipeline():
    """
    Full data collection + synthesis pipeline.
    Runs on schedule and on-demand.
    """
    rprint("[bold cyan]━━ Pipeline starting ━━[/bold cyan]")
    state["status"] = "collecting"
    await broadcast({"type": "status", "status": "collecting"})

    try:
        # Step 1: Collect DefiLlama (free, fast ~3-5s)
        rprint("[cyan]Step 1/3: DefiLlama[/cyan]")
        defillama_data = await collect_defillama()
        state["defillama"] = defillama_data
        await broadcast({"type": "defillama_update", "data": _safe_defillama(defillama_data)})

        # Step 2: Collect Telegram signals (free, ~30-60s depending on channels)
        rprint("[cyan]Step 2/3: Telegram[/cyan]")
        telegram_data = await collect_telegram_signals(hours_back=48)
        state["telegram"] = telegram_data
        await broadcast({"type": "telegram_update", "data": telegram_data.get("sectors", {})})

        # Step 3: Claude synthesis (~5-10s, ~$0.05-0.15)
        rprint("[cyan]Step 3/3: Claude synthesis[/cyan]")
        state["status"] = "synthesizing"
        await broadcast({"type": "status", "status": "synthesizing"})

        synthesis = await synthesize(defillama_data, telegram_data)
        state["synthesis"] = synthesis
        state["last_run"] = datetime.now(_ET).isoformat()
        state["status"] = "ready"

        await broadcast({
            "type": "synthesis_update",
            "data": synthesis,
            "last_run": state["last_run"],
        })

        rprint(f"[bold green]━━ Pipeline complete ━━[/bold green]")

    except Exception as e:
        rprint(f"[red]Pipeline error: {e}[/red]")
        state["status"] = "error"
        await broadcast({"type": "error", "message": str(e)})


def _safe_defillama(data: dict) -> dict:
    """Strip large raw data before sending to browser."""
    if not data:
        return {}
    return {
        "collected_at": data.get("collected_at"),
        "top_protocols": data.get("top_revenue_protocols", [])[:10],
        "sector_fees": {
            k: {
                "total_7d": v.get("total_7d"),
                "wow_change_pct": v.get("wow_change_pct"),
                "protocol_count": v.get("protocol_count"),
            }
            for k, v in (data.get("sector_fees") or {}).items()
        }
    }


# ── WebSocket ──────────────────────────────────────────────────────────────────

async def broadcast(message: dict):
    """Send update to all connected dashboard clients."""
    if not connected_clients:
        return
    text = json.dumps(message, default=str)
    disconnected = []
    for ws in connected_clients:
        try:
            await ws.send_text(text)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        connected_clients.remove(ws)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    rprint(f"[dim]Dashboard connected ({len(connected_clients)} clients)[/dim]")

    # Send current state immediately on connect
    await websocket.send_text(json.dumps({
        "type": "full_state",
        "state": {
            "status": state["status"],
            "last_run": state["last_run"],
            "synthesis": state["synthesis"],
            "telegram_sectors": state["telegram"].get("sectors", {}),
            "defillama": _safe_defillama(state["defillama"]),
        }
    }, default=str))

    try:
        while True:
            # Keep connection alive, handle client messages
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "run_now":
                rprint("[yellow]Manual pipeline trigger[/yellow]")
                asyncio.create_task(run_pipeline())

    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        rprint(f"[dim]Dashboard disconnected ({len(connected_clients)} clients)[/dim]")


# ── REST API ───────────────────────────────────────────────────────────────────

@app.get("/api/state")
async def get_state():
    return JSONResponse({
        "status": state["status"],
        "last_run": state["last_run"],
        "synthesis": state["synthesis"],
        "telegram_sectors": state["telegram"].get("sectors", {}),
    })


@app.get("/api/run")
async def trigger_run():
    """Manually trigger a pipeline run."""
    asyncio.create_task(run_pipeline())
    return {"message": "Pipeline started"}


@app.get("/api/synthesis")
async def get_synthesis():
    return JSONResponse(state["synthesis"])


@app.get("/api/defillama")
async def get_defillama():
    return JSONResponse(_safe_defillama(state["defillama"]))


# ── Dashboard HTML ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serves the live dashboard — an enhanced version of the static one."""
    html_path = Path(__file__).parent / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text())
    return HTMLResponse("<h1>Dashboard not found</h1><p>Run build first</p>")


# ── Startup ────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    uvicorn.run(
        app,                    # Pass app object directly (required for PyInstaller)
        host="0.0.0.0",
        port=_args.port,
        reload=False,
        log_level="warning",
    )
