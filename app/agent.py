"""Student implementation area. This scaffold deliberately does no agent work."""
from app.models import ArenaResponse
async def run_agent(request, history, model):
    # TODO: initialize state and an isolated sandbox for this run.
    # TODO: assemble system policy + history + user goal + runtime observations.
    # TODO: call your model (LangChain allowed), parse and validate one decision.
    # TODO: clarify, execute a tool, retry within limits, or stop.
    # TODO: inject request.arena_config.fault through your tool/model boundary.
    # TODO: count ALL model decisions including repairs against max_steps.
    # TODO: return observations, tool traces, usage metrics and accurate status.
    return ArenaResponse(request_id=request.request_id, status='failed',
        final_response='Starter scaffold is running. Implement the agent in app/agent.py.',
        stop_reason='not_implemented',
        events=[{'step': 0, 'event': 'agent_stop', 'reason': 'not_implemented'}])
