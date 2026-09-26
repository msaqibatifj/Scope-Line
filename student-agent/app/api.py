import json
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse
from app.config import ROOT, settings
from app.models import ArenaRequest, ArenaResponse, ChatRequest
from app.arena import execute
from app.model_clients import enabled_external_models

router = APIRouter()
ENABLED_MODELS = ['local-contract-v1', 'local-conservative-v1']

@router.get('/')
def index():
    return FileResponse(ROOT / 'app/static/index.html')

@router.get('/health')
def health():
    return {'status': 'ok', 'implementation': 'packetpilot', 'domain': 'scholarship_packet_readiness'}

@router.get('/arena/manifest')
def manifest():
    return json.loads((ROOT / 'arena_manifest.json').read_text(encoding='utf-8-sig'))

@router.get('/models')
def models():
    configured = [settings.model_name] if settings.model_name else []
    available = configured or ENABLED_MODELS + enabled_external_models()
    return {'models': list(dict.fromkeys(available))}

@router.post('/arena/run', response_model=ArenaResponse)
async def arena_run(payload: ArenaRequest):
    return await execute(payload, model=settings.model_name or 'local-contract-v1')

@router.post('/chat', response_model=ArenaResponse)
async def chat(payload: ChatRequest, request: Request):
    if payload.model not in models()['models']:
        raise HTTPException(400, 'Model is not enabled')
    busy = request.app.state.busy
    if payload.session_id in busy:
        raise HTTPException(409, 'This chat is already running')
    busy.add(payload.session_id)
    memory = request.app.state.memory
    try:
        result = await execute(payload, memory.get(payload.session_id), payload.model)
        memory.add(payload.session_id, payload.task, result.final_response)
        return result
    finally:
        busy.discard(payload.session_id)

@router.delete('/chat/{session_id}')
def reset(session_id: str, request: Request):
    if session_id in request.app.state.busy:
        raise HTTPException(409, 'Chat is running')
    request.app.state.memory.clear(session_id)
    return {'status': 'cleared'}
