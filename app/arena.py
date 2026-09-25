"""Common boundary; ordinary Arena requests have no chat memory."""
import asyncio
import logging
from time import perf_counter
from app.agent import run_agent
from app.config import settings
from app.models import ArenaResponse
from app.sandbox import Sandbox
log = logging.getLogger('arena')
async def execute(request, history=None, model='unconfigured', sandbox=None):
    started = perf_counter()
    request = request.model_copy(deep=True)
    request.arena_config.max_steps = min(request.arena_config.max_steps, settings.max_steps)
    owns_sandbox = sandbox is None
    try:
        if owns_sandbox:
            sandbox = Sandbox.create()
        async with asyncio.timeout(settings.run_timeout_seconds):
            result = await run_agent(request, history or [], model, sandbox=sandbox)
            result = ArenaResponse.model_validate(result)
    except TimeoutError:
        result = ArenaResponse(request_id=request.request_id, status='budget_exceeded',
            final_response='The run timed out.', stop_reason='time_budget_reached')
    except Exception:
        result = ArenaResponse(request_id=request.request_id, status='failed',
            final_response='The run stopped due to an internal error.', stop_reason='internal_error')
    finally:
        if owns_sandbox and sandbox is not None:
            sandbox.cleanup()
    result.metrics.latency_ms = (perf_counter() - started) * 1000
    if len(result.model_dump_json().encode()) > 50000:
        result = ArenaResponse(request_id=request.request_id, status='failed',
            final_response='Response exceeded the size limit.', stop_reason='response_too_large')
    log.info('request=%s status=%s steps=%s', request.request_id, result.status, result.steps)
    return result
