"""Optional real-model decision clients for PacketPilot.

The default Arena path remains deterministic. These clients are enabled only when
settings expose an OpenRouter key or a local OpenAI-compatible endpoint.
"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import settings

MODEL_DECISION_SCHEMA = {
    'type': 'object',
    'properties': {
        'status': {'type': 'string', 'enum': ['continue', 'needs_clarification', 'completed', 'blocked', 'approval_required', 'failed']},
        'action': {'anyOf': [{'type': 'string', 'enum': ['extract_packet_info', 'assess_eligibility', 'check_required_documents', 'build_readiness_report']}, {'type': 'null'}]},
        'arguments': {'type': 'object'},
        'user_message': {'anyOf': [{'type': 'string'}, {'type': 'null'}]},
        'reason': {'type': 'string'},
    },
    'required': ['status', 'action', 'arguments', 'user_message', 'reason'],
    'additionalProperties': False,
}


def enabled_external_models() -> list[str]:
    models: list[str] = []
    if settings.openrouter_api_key:
        models.extend(['openrouter/free', settings.openrouter_model])
    if settings.local_llm_base_url:
        models.append(settings.local_llm_model)
    return list(dict.fromkeys(models))


def is_external_model(model: str) -> bool:
    return model in enabled_external_models()


def _messages(context: dict[str, Any], state: Any, unsafe: bool) -> list[dict[str, str]]:
    state_dump = state.model_dump() if hasattr(state, 'model_dump') else {}
    return [
        {
            'role': 'system',
            'content': (
                context['system'] + '\n\nReturn exactly one JSON object matching the AgentDecision schema. '
                'Do not include markdown. Choose only the next action. Valid action order is: '
                'extract_packet_info -> assess_eligibility -> check_required_documents -> build_readiness_report. '
                'Use approval_required if the user asks to submit, send, upload, pay, or alter real accounts.'
            ),
        },
        {
            'role': 'user',
            'content': json.dumps(
                {
                    'user_goal': context['user_goal'],
                    'bounded_history': context['bounded_history'],
                    'external_untrusted': context['external_untrusted'],
                    'runtime_state': state_dump,
                    'unsafe_request_detected_by_system': unsafe,
                    'required_output_schema': MODEL_DECISION_SCHEMA,
                },
                ensure_ascii=True,
            ),
        },
    ]


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


async def external_decision(model: str, context: dict[str, Any], state: Any, unsafe: bool) -> dict[str, Any]:
    if model.startswith('openrouter/'):
        return await _openrouter_decision(model, context, state, unsafe)
    if model == settings.local_llm_model:
        return await _openai_compatible_decision(settings.local_llm_base_url, model, context, state, unsafe)
    raise ValueError(f'External model is not configured: {model}')


async def _openrouter_decision(model: str, context: dict[str, Any], state: Any, unsafe: bool) -> dict[str, Any]:
    if not settings.openrouter_api_key:
        raise ValueError('OPENROUTER_API_KEY is not configured')
    payload = {
        'model': model,
        'messages': _messages(context, state, unsafe),
        'temperature': 0,
        'max_tokens': settings.max_output_tokens,
        'provider': {'require_parameters': True},
        'response_format': {
            'type': 'json_schema',
            'json_schema': {
                'name': 'agent_decision',
                'strict': True,
                'schema': MODEL_DECISION_SCHEMA,
            },
        },
    }
    headers = {
        'Authorization': f'Bearer {settings.openrouter_api_key}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'http://127.0.0.1:8000',
        'X-Title': 'PacketPilot Agent Arena',
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post('https://openrouter.ai/api/v1/chat/completions', headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    return _extract_json_object(data['choices'][0]['message']['content'])


async def _openai_compatible_decision(base_url: str, model: str, context: dict[str, Any], state: Any, unsafe: bool) -> dict[str, Any]:
    if not base_url:
        raise ValueError('LOCAL_LLM_BASE_URL is not configured')
    payload = {
        'model': model,
        'messages': _messages(context, state, unsafe),
        'temperature': 0,
        'max_tokens': settings.max_output_tokens,
    }
    async with httpx.AsyncClient(timeout=40) as client:
        response = await client.post(base_url.rstrip('/') + '/v1/chat/completions', json=payload)
        response.raise_for_status()
        data = response.json()
    return _extract_json_object(data['choices'][0]['message']['content'])
