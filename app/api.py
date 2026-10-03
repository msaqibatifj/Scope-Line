import json
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse
from app.config import ROOT, settings
from app.models import ArenaRequest, ArenaResponse, ChatRequest
from app.arena import execute
from app.memory import SessionCapacityError
from app.providers import LOCAL_MODEL, available_model_names, default_model_name, model_preflight, model_readiness
router = APIRouter()
@router.get('/')
def index(): return FileResponse(ROOT / 'app/static/index.html')


# Relative asset paths also let the standalone HTML preview work from file://.
@router.get('/style.css', include_in_schema=False)
def stylesheet(): return FileResponse(ROOT / 'app/static/style.css', media_type='text/css')


@router.get('/app.js', include_in_schema=False)
def script(): return FileResponse(ROOT / 'app/static/app.js', media_type='application/javascript')
@router.get('/health')
def health(): return {'status': 'ok', 'implementation': 'scopeline-v1'}
@router.get('/arena/manifest')
def manifest(): return json.loads((ROOT / 'arena_manifest.json').read_text())
@router.get('/models')
def models():
    return {'models': available_model_names(), 'default': default_model_name(), 'readiness': model_readiness()}


def _claim_run(request: Request, run_id: str) -> None:
    active = request.app.state.active_runs
    if len(active) >= settings.max_concurrent_chats:
        raise HTTPException(429, 'Run concurrency limit reached')
    if run_id in active:
        raise HTTPException(409, 'This run is already active')
    active.add(run_id)
@router.post('/run', response_model=ArenaResponse, summary='Run a task')
@router.post('/arena/run', response_model=ArenaResponse)
async def arena_run(payload: ArenaRequest, request: Request):
    _claim_run(request, 'arena:' + payload.request_id)
    try:
        model = default_model_name()
        admitted, reason = request.app.state.live_usage.admit(model)
        if not admitted and not settings.allow_local_fallback:
            return ArenaResponse(request_id=payload.request_id, status='budget_exceeded',
                final_response='The live run admission limit was reached.', stop_reason=reason)
        execution_model = model if admitted else LOCAL_MODEL
        result = await execute(payload, model=execution_model)
        if not admitted:
            result.events.insert(0, {'step': 0, 'event': 'provider_fallback', 'from_model': model, 'to_model': LOCAL_MODEL, 'reason': reason})
        else:
            request.app.state.live_usage.record(model, result.metrics.estimated_cost_usd)
        return result
    finally:
        request.app.state.active_runs.discard('arena:' + payload.request_id)
@router.post('/chat', response_model=ArenaResponse)
async def chat(payload: ChatRequest, request: Request):
    ok, reason = model_preflight(payload.model)
    if not ok:
        raise HTTPException(400, f'Model is not enabled: {reason}')
    busy = request.app.state.busy
    _claim_run(request, 'chat:' + payload.session_id)
    if payload.session_id in busy:
        request.app.state.active_runs.discard('chat:' + payload.session_id)
        raise HTTPException(409, 'This chat is already running')
    admitted, admission_reason = request.app.state.live_usage.admit(payload.model)
    if not admitted and not settings.allow_local_fallback:
        request.app.state.active_runs.discard('chat:' + payload.session_id)
        return ArenaResponse(request_id=payload.request_id, status='budget_exceeded',
            final_response='The live run admission limit was reached.', stop_reason=admission_reason)
    execution_model = payload.model if admitted else LOCAL_MODEL
    busy.add(payload.session_id)
    memory = request.app.state.memory
    try:
        try:
            sandbox = memory.begin(payload.session_id)
        except SessionCapacityError as error:
            raise HTTPException(503, str(error)) from error
        effective_task = memory.resolve(payload.session_id, payload.task)
        execution_payload = payload.model_copy(update={'task': effective_task})
        result = await execute(execution_payload, memory.get(payload.session_id), execution_model, sandbox=sandbox)
        memory.record_result(payload.session_id, effective_task, result)
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
        request.app.state.active_runs.discard('chat:' + payload.session_id)
@router.delete('/chat/{session_id}')
async def reset(session_id: str, request: Request):
    if session_id in request.app.state.busy: raise HTTPException(409, 'Chat is running')
    request.app.state.memory.clear(session_id)
    return {'status': 'cleared'}
