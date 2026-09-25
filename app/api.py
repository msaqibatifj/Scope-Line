import json
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse
from app.config import ROOT, settings
from app.models import ArenaRequest, ArenaResponse, ChatRequest
from app.arena import execute
from app.memory import SessionCapacityError
from app.providers import LOCAL_MODEL, available_model_names, default_model_name, model_preflight
router = APIRouter()
@router.get('/')
def index(): return FileResponse(ROOT / 'app/static/index.html')
@router.get('/health')
def health(): return {'status': 'ok', 'implementation': 'scopeline-v1'}
@router.get('/arena/manifest')
def manifest(): return json.loads((ROOT / 'arena_manifest.json').read_text())
@router.get('/models')
def models():
    return {'models': available_model_names(), 'default': default_model_name()}
@router.post('/arena/run', response_model=ArenaResponse)
async def arena_run(payload: ArenaRequest, request: Request):
    model = default_model_name()
    admitted, reason = request.app.state.live_usage.admit(model)
    execution_model = model if admitted else LOCAL_MODEL
    result = await execute(payload, model=execution_model)
    if not admitted:
        result.events.insert(0, {'step': 0, 'event': 'provider_fallback', 'from_model': model, 'to_model': LOCAL_MODEL, 'reason': reason})
    else:
        request.app.state.live_usage.record(model, result.metrics.estimated_cost_usd)
    return result
@router.post('/chat', response_model=ArenaResponse)
async def chat(payload: ChatRequest, request: Request):
    ok, reason = model_preflight(payload.model)
    if not ok:
        raise HTTPException(400, f'Model is not enabled: {reason}')
    busy = request.app.state.busy
    if len(busy) >= settings.max_concurrent_chats:
        raise HTTPException(429, 'Chat concurrency limit reached')
    if payload.session_id in busy: raise HTTPException(409, 'This chat is already running')
    admitted, admission_reason = request.app.state.live_usage.admit(payload.model)
    execution_model = payload.model if admitted else LOCAL_MODEL
    busy.add(payload.session_id)
    memory = request.app.state.memory
    try:
        try:
            sandbox = memory.begin(payload.session_id)
        except SessionCapacityError as error:
            raise HTTPException(503, str(error)) from error
        result = await execute(payload, memory.get(payload.session_id), execution_model, sandbox=sandbox)
        if not admitted:
            result.events.insert(0, {'step': 0, 'event': 'provider_fallback', 'from_model': payload.model, 'to_model': LOCAL_MODEL, 'reason': admission_reason})
        else:
            request.app.state.live_usage.record(payload.model, result.metrics.estimated_cost_usd)
        memory.add(payload.session_id, payload.task, result.final_response)
        return result
    finally:
        if payload.session_id in memory.active:
            memory.end(payload.session_id)
        busy.discard(payload.session_id)
@router.delete('/chat/{session_id}')
async def reset(session_id: str, request: Request):
    if session_id in request.app.state.busy: raise HTTPException(409, 'Chat is running')
    request.app.state.memory.clear(session_id)
    return {'status': 'cleared'}
