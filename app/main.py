from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api import router
from app.config import ROOT, settings
from app.memory import Memory
from app.providers import LiveUsageGate
@asynccontextmanager
async def lifespan(app):
    app.state.memory = Memory()
    app.state.memory.ttl_seconds = settings.session_ttl_seconds
    app.state.busy = set()
    app.state.active_runs = set()
    app.state.live_usage = LiveUsageGate()
    async def reap_sessions():
        while True:
            await asyncio.sleep(min(30, settings.session_ttl_seconds))
            app.state.memory.expire()
    reaper = asyncio.create_task(reap_sessions())
    try:
        yield
    finally:
        reaper.cancel()
        try:
            await reaper
        except asyncio.CancelledError:
            pass
        app.state.memory.close()
app = FastAPI(title='ScopeLine - Freelance Scope Drift Monitor', lifespan=lifespan)
app.include_router(router)
app.mount('/static', StaticFiles(directory=ROOT / 'app/static'), name='static')
# Live calls also pass provider, allowlist, spend, and chat-concurrency checks.
