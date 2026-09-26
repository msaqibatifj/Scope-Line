"""Compare configured live models on the same ScopeLine cases."""
from __future__ import annotations

import argparse
import hashlib
import sys
from contextlib import contextmanager
import subprocess
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx


ROOT = Path(__file__).resolve().parent
DEFAULT_MODELS = [
    'gemini-3.1-flash-lite',
    'gemini-3.5-flash-lite',
]


def validate_comparison_server(metadata: dict[str, Any], models: list[str]) -> None:
    readiness = metadata.get('readiness', {})
    if readiness.get('model_fallback_enabled') is not False or readiness.get('fallback_enabled') is not False:
        raise ValueError('Start the server with ALLOW_MODEL_FALLBACK=false and ALLOW_LOCAL_FALLBACK=false before comparing models.')
    missing = set(models) - set(metadata.get('models', []))
    if missing:
        raise ValueError('Comparison models are not enabled: ' + ', '.join(sorted(missing)))


def expected_checks(case: dict[str, Any], result: dict[str, Any]) -> tuple[bool, bool]:
    # Step 1: score the terminal result and the selected action separately.
    # Terminal status and required evidence are stable; model-written reasons are not.
    terminal_ok = result.get('status') == case['expected_status'] and not any(
        event.get('event') == 'provider_fallback' for event in result.get('events', [])
    )
    calls = result.get('tool_calls', [])
    events = result.get('events', [])
    action_checks: list[bool] = []
    if 'expected_tool' in case:
        action_checks.append(any(call.get('tool') == case['expected_tool'] for call in calls))
    if 'expected_tool_outcome' in case:
        action_checks.append(any(call.get('outcome') == case['expected_tool_outcome'] for call in calls))
    if 'expected_event' in case:
        action_checks.append(any(event.get('event') == case['expected_event'] for event in events))
    action_ok = all(action_checks) if action_checks else terminal_ok
    if 'expected_text' in case:
        terminal_ok = terminal_ok and case['expected_text'] in result.get('final_response', '')
    return terminal_ok and action_ok, action_ok


def contract_is_valid(result: dict[str, Any]) -> bool:
    # Step 2: check the common Arena response shape returned to evaluators.
    required = {'arena_version', 'request_id', 'status', 'final_response', 'steps', 'stop_reason', 'tool_calls', 'errors', 'events', 'metrics'}
    if not required.issubset(result):
        return False
    steps = result.get('steps')
    if not isinstance(steps, int) or isinstance(steps, bool) or not 0 <= steps <= 6:
        return False
    if not isinstance(result.get('final_response'), str) or not result['final_response']:
        return False
    if not isinstance(result.get('tool_calls'), list) or not isinstance(result.get('errors'), list) or not isinstance(result.get('events'), list):
        return False
    metrics = result.get('metrics')
    if not isinstance(metrics, dict):
        return False
    model_calls = metrics.get('model_calls')
    if model_calls is not None and (not isinstance(model_calls, int) or isinstance(model_calls, bool) or model_calls < 0):
        return False
    for key in ('input_tokens', 'output_tokens'):
        value = metrics.get(key)
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
            return False
    cost = metrics.get('estimated_cost_usd')
    if cost is not None and (not isinstance(cost, (int, float)) or isinstance(cost, bool) or cost < 0):
        return False
    return True


def save(output: Path, models: list[str], records: list[dict[str, Any]]) -> None:
    # Step 3: aggregate completed runs and preserve partial evidence.
    summaries = {}
    for model in models:
        rows = [row for row in records if row['model'] == model]
        completed = [row for row in rows if row.get('http_ok')]
        latencies = [row['latency_ms'] for row in completed if row.get('latency_ms') is not None]
        known_costs = [row.get('cost_usd') for row in rows if row.get('cost_usd') is not None]
        summaries[model] = {
            'runs': len(rows),
            'task_successes': sum(bool(row.get('task_success')) for row in rows),
            'valid_contracts': sum(bool(row.get('contract_valid')) for row in rows),
            'correct_actions': sum(bool(row.get('correct_action')) for row in rows),
            'average_latency_ms': round(sum(latencies) / len(latencies), 2) if latencies else None,
            'input_tokens': sum(row.get('input_tokens') or 0 for row in rows),
            'output_tokens': sum(row.get('output_tokens') or 0 for row in rows),
            'reported_cost_usd': round(sum(known_costs), 8) if len(known_costs) == len(rows) else None,
            'cost_known_runs': len(known_costs),
            'fallback_runs': sum(bool(row.get('fallback_used')) for row in rows),
        }
    payload = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'models': models,
        'summaries': summaries,
        'runs': records,
        'source_revision': _source_revision(),
        'source_sha256': {str(p.relative_to(ROOT.parent)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT.parent / 'app').glob('*.py'))},
        'cost_note': 'Costs may be estimated under the configured free-tier assumption, not provider billing receipts.',
        'live_only': bool(records) and all(row.get('http_ok') and not row.get('fallback_used') for row in records),
    }
    output.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def _source_revision() -> str | None:
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True, cwd=ROOT.parent).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


@contextmanager
def comparison_client(url: str, in_process: bool):
    if not in_process:
        with httpx.Client(timeout=50) as client:
            yield client, url.rstrip('/')
        return
    # The local API transport changes; model inference still uses real provider HTTPS.
    if str(ROOT.parent) not in sys.path:
        sys.path.insert(0, str(ROOT.parent))
    from fastapi.testclient import TestClient
    from app.config import settings
    from app.main import app
    original = settings.allow_model_fallback, settings.allow_local_fallback
    settings.allow_model_fallback = settings.allow_local_fallback = False
    try:
        with TestClient(app) as client:
            yield client, ''
    finally:
        settings.allow_model_fallback, settings.allow_local_fallback = original


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--models', nargs='+', default=DEFAULT_MODELS)
    parser.add_argument('--output', default=str(ROOT / 'gemini_comparison_results.json'))
    parser.add_argument('--delay', type=float, default=20.0, help='Seconds between cases (default: 20).')
    parser.add_argument('--in-process', action='store_true', help='Use the local FastAPI app with real provider calls and both fallback paths disabled.')
    args = parser.parse_args()

    cases = json.loads((ROOT / 'public_cases.json').read_text(encoding='utf-8'))
    output = Path(args.output)
    records: list[dict[str, Any]] = []
    with comparison_client(args.url, args.in_process) as (client, base_url):
        try:
            response = client.get(base_url + '/models')
            response.raise_for_status()
            validate_comparison_server(response.json(), args.models)
        except (httpx.HTTPError, ValueError) as error:
            print(f'Comparison setup error: {error}')
            return 2
        for model_index, model in enumerate(args.models):
            for case_index, case in enumerate(cases):
                payload = dict(case['request'])
                payload.update(session_id=f'compare-{model_index}-{case_index}-{uuid4()}', model=model)
                started = time.perf_counter()
                row: dict[str, Any] = {'model': model, 'case': case['name']}
                try:
                    response = client.post(base_url + '/chat', json=payload)
                    row['http_status'] = response.status_code
                    response.raise_for_status()
                    result = response.json()
                    success, action_ok = expected_checks(case, result)
                    metrics = result.get('metrics', {})
                    row.update(
                        http_ok=True,
                        task_success=success,
                        contract_valid=contract_is_valid(result),
                        correct_action=action_ok,
                        status=result.get('status'),
                        stop_reason=result.get('stop_reason'),
                        steps=result.get('steps'),
                        latency_ms=metrics.get('latency_ms'),
                        model_calls=metrics.get('model_calls'),
                        input_tokens=metrics.get('input_tokens'),
                        output_tokens=metrics.get('output_tokens'),
                        cost_usd=metrics.get('estimated_cost_usd'),
                        tools=[call.get('tool') for call in result.get('tool_calls', [])],
                        error_types=[error.get('type') for error in result.get('errors', [])],
                        provider_errors=[error.get('message') for error in result.get('errors', [])],
                        response=result,
                        transport='in-process API / live provider HTTPS' if args.in_process else args.url,
                        fallback_used=any(event.get('event') == 'provider_fallback' for event in result.get('events', [])),
                    )
                except (httpx.HTTPError, ValueError) as error:
                    row.update(
                        http_ok=False,
                        task_success=False,
                        contract_valid=False,
                        correct_action=False,
                        latency_ms=round((time.perf_counter() - started) * 1000, 2),
                        error_type=type(error).__name__,
                        error=str(error)[:500],
                    )
                client.delete(base_url + '/chat/' + payload['session_id'])
                records.append(row)
                save(output, args.models, records)
                print(f"{model} | {case['name']} | {'PASS' if row['task_success'] else 'FAIL'} | {row.get('stop_reason', row.get('error_type'))}", flush=True)
                if args.delay > 0:
                    time.sleep(args.delay)
    save(output, args.models, records)
    return 0 if records and all(row.get('task_success') for row in records) else 1


if __name__ == '__main__':
    raise SystemExit(main())
