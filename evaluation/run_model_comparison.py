"""Compare configured live models on the same ScopeLine cases."""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx


ROOT = Path(__file__).resolve().parent
DEFAULT_MODELS = [
    'nvidia/nemotron-3-ultra-550b-a55b:free',
    'cohere/north-mini-code:free',
]


def expected_checks(case: dict[str, Any], result: dict[str, Any]) -> tuple[bool, bool]:
    # Step 1: score the terminal result and the selected action separately.
    terminal_ok = (
        result.get('status') == case['expected_status']
        and result.get('stop_reason') == case['expected_stop_reason']
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
    return required.issubset(result) and isinstance(result.get('steps'), int)


def save(output: Path, models: list[str], records: list[dict[str, Any]]) -> None:
    # Step 3: aggregate completed runs and preserve partial evidence.
    summaries = {}
    for model in models:
        rows = [row for row in records if row['model'] == model]
        completed = [row for row in rows if row.get('http_ok')]
        latencies = [row['latency_ms'] for row in completed if row.get('latency_ms') is not None]
        summaries[model] = {
            'runs': len(rows),
            'task_successes': sum(bool(row.get('task_success')) for row in rows),
            'valid_contracts': sum(bool(row.get('contract_valid')) for row in rows),
            'correct_actions': sum(bool(row.get('correct_action')) for row in rows),
            'average_latency_ms': round(sum(latencies) / len(latencies), 2) if latencies else None,
            'input_tokens': sum(row.get('input_tokens') or 0 for row in rows),
            'output_tokens': sum(row.get('output_tokens') or 0 for row in rows),
            'reported_cost_usd': round(sum(row.get('cost_usd') or 0 for row in rows), 8),
        }
    payload = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'models': models,
        'summaries': summaries,
        'runs': records,
    }
    output.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--models', nargs='+', default=DEFAULT_MODELS)
    parser.add_argument('--output', default=str(ROOT / 'model_comparison_results.json'))
    parser.add_argument('--delay', type=float, default=1.0)
    args = parser.parse_args()

    cases = json.loads((ROOT / 'public_cases.json').read_text(encoding='utf-8'))
    output = Path(args.output)
    records: list[dict[str, Any]] = []
    with httpx.Client(timeout=50) as client:
        for model_index, model in enumerate(args.models):
            for case_index, case in enumerate(cases):
                payload = dict(case['request'])
                payload.update(session_id=f'compare-{model_index}-{case_index}-{uuid4()}', model=model)
                started = time.perf_counter()
                row: dict[str, Any] = {'model': model, 'case': case['name']}
                try:
                    response = client.post(args.url.rstrip('/') + '/chat', json=payload)
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
                records.append(row)
                save(output, args.models, records)
                print(f"{model} | {case['name']} | {'PASS' if row['task_success'] else 'FAIL'} | {row.get('stop_reason', row.get('error_type'))}", flush=True)
                if args.delay > 0:
                    time.sleep(args.delay)
    save(output, args.models, records)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
