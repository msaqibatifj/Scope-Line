"""Provider routing and failover checks; all inference HTTP calls are mocked."""
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from app.agent import DirectDecisionProvider
from app.config import settings
from app.main import app
from app.providers import model_preflight, fallback_model_names
from evaluation.run_model_comparison import DEFAULT_MODELS, expected_checks, validate_comparison_server

PRIMARY = 'gemini-3.1-flash-lite'
SECONDARY = 'gemini-3.5-flash-lite'
BACKUP = 'groq/qwen3.8-27b'
CALL = {'status': 'call_tool', 'tool': 'list_projects', 'arguments': {}, 'reason': 'list'}
FINISH = {'status': 'finish', 'user_message': 'Projects listed.', 'reason': 'done'}


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.original = settings.model_dump()
        settings.model_provider = 'gemini'
        settings.model_name = PRIMARY
        settings.allowed_models = ','.join(['local-scripted', PRIMARY, SECONDARY, BACKUP])
        settings.fallback_models = BACKUP
        settings.enable_live_models = True
        settings.allow_model_fallback = True
        settings.allow_local_fallback = False
        settings.direct_api_free_tier = True
        settings.gemini_api_key = 'gemini-test'
        settings.groq_api_key = 'groq-test'
        settings.spend_limit_usd = 0

    def tearDown(self):
        for key, value in self.original.items():
            setattr(settings, key, value)

    def test_models_use_separate_credentials_and_no_cycles(self):
        self.assertEqual(fallback_model_names(PRIMARY), [BACKUP])
        self.assertEqual(fallback_model_names(SECONDARY), [BACKUP])
        self.assertEqual(fallback_model_names(BACKUP), [])
        settings.groq_api_key = ''
        self.assertFalse(model_preflight(BACKUP)[0])
        self.assertTrue(model_preflight(PRIMARY)[0])
        self.assertEqual(fallback_model_names(PRIMARY), [])
        settings.direct_api_free_tier = False
        self.assertEqual(model_preflight(PRIMARY), (False, 'paid_models_disabled_by_spend_limit'))

    def test_direct_http_payload_and_native_model_ids(self):
        for provider, model, native, endpoint, key, effort in [
            ('gemini', PRIMARY, PRIMARY, settings.gemini_base_url, 'gemini-test', 'minimal'),
            ('gemini', SECONDARY, SECONDARY, settings.gemini_base_url, 'gemini-test', 'minimal'),
            ('groq', BACKUP, 'qwen/qwen3.8-27b', settings.groq_base_url, 'groq-test', 'none'),
        ]:
            with self.subTest(model=model):
                response = httpx.Response(200, request=httpx.Request('POST', endpoint), json={
                    'choices': [{'message': {'tool_calls': [{'function': {
                        'name': 'list_projects',
                        'arguments': '{}',
                    }}]}}], 'usage': {'prompt_tokens': 120, 'completion_tokens': 30},
                })
                client = AsyncMock()
                client.__aenter__.return_value = client
                client.post.return_value = response
                with patch('app.agent.httpx.AsyncClient', return_value=client):
                    decision, usage = asyncio.run(DirectDecisionProvider(provider).decide(model, {'system': 'policy'}))
                args, kwargs = client.post.call_args
                self.assertEqual(args[0], endpoint + '/chat/completions')
                self.assertEqual(kwargs['headers']['Authorization'], 'Bearer ' + key)
                self.assertNotIn('X-OpenRouter-Title', kwargs['headers'])
                self.assertEqual(kwargs['json']['model'], native)
                self.assertEqual(kwargs['json']['reasoning_effort'], effort)
                self.assertNotIn('usage', kwargs['json'])
                self.assertEqual(decision['tool'], 'list_projects')
                self.assertEqual(usage['input_tokens'], 120)
                self.assertEqual(usage['estimated_cost_usd'], 0)

    def test_either_gemini_candidate_fails_over_directly_to_qwen(self):
        for candidate in [PRIMARY, SECONDARY]:
            with self.subTest(candidate=candidate):
                calls = []
                async def decide(model, context, repair_error=None):
                    calls.append((model, len(context['tool_observations'])))
                    if model != BACKUP:
                        raise httpx.ReadTimeout('provider unavailable')
                    return (FINISH if context['tool_observations'] else CALL), {'input_tokens': 10, 'output_tokens': 5}
                with patch.object(DirectDecisionProvider, 'decide', side_effect=decide), TestClient(app) as client:
                    result = client.post('/chat', json={'task': 'List projects', 'model': candidate,
                        'session_id': 'comparison-candidate-session'}).json()
                self.assertEqual(result['status'], 'completed')
                self.assertEqual([model for model, _ in calls], [candidate, BACKUP, BACKUP])
                self.assertEqual(calls[-1][1], 1)
                self.assertEqual(result['steps'], 3)
                self.assertEqual(result['metrics']['input_tokens'], 20)
                self.assertEqual([e['to_model'] for e in result['events'] if e['event'] == 'provider_fallback'], [BACKUP])

    def test_failover_is_bounded_by_steps(self):
        with patch.object(DirectDecisionProvider, 'decide', new=AsyncMock(side_effect=httpx.ReadTimeout('timeout'))) as provider, TestClient(app) as client:
            result = client.post('/arena/run', json={'task': 'List projects', 'arena_config': {'max_steps': 1}}).json()
        self.assertEqual(result['status'], 'budget_exceeded')
        self.assertEqual(provider.await_count, 1)

    def test_model_fallback_can_be_disabled_for_comparison(self):
        settings.allow_model_fallback = False
        with patch.object(DirectDecisionProvider, 'decide', new=AsyncMock(side_effect=httpx.ReadTimeout('timeout'))) as provider, TestClient(app) as client:
            result = client.post('/arena/run', json={'task': 'List projects'}).json()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(provider.await_count, 1)
        self.assertFalse(any(e['event'] == 'provider_fallback' for e in result['events']))

    def test_authentication_errors_do_not_trigger_backups(self):
        response = httpx.Response(401, request=httpx.Request('POST', 'https://example.test'))
        error = httpx.HTTPStatusError('Unauthorized', request=response.request, response=response)
        with patch.object(DirectDecisionProvider, 'decide', new=AsyncMock(side_effect=error)) as provider, TestClient(app) as client:
            result = client.post('/arena/run', json={'task': 'List projects'}).json()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(provider.await_count, 1)

    def test_admission_rejection_does_not_silently_run_locally(self):
        with TestClient(app) as client, patch.object(app.state.live_usage, 'admit', return_value=(False, 'live_rate_limit_reached')):
            for endpoint, extra in [('/arena/run', {}), ('/chat', {'session_id': 'provider-test-session', 'model': PRIMARY})]:
                result = client.post(endpoint, json={'task': 'List projects', **extra}).json()
                self.assertEqual(result['status'], 'budget_exceeded')
                self.assertEqual(result['tool_calls'], [])
            self.assertFalse(app.state.active_runs)

    def test_comparison_excludes_backup_success(self):
        case = {'expected_status': 'completed', 'expected_tool': 'list_projects'}
        result = {'status': 'completed', 'tool_calls': [{'tool': 'list_projects'}], 'events': [{'event': 'provider_fallback'}]}
        self.assertFalse(expected_checks(case, result)[0])

    def test_comparison_requires_two_enabled_candidates_and_no_fallback(self):
        self.assertEqual(DEFAULT_MODELS, [PRIMARY, SECONDARY])
        metadata = {'models': DEFAULT_MODELS, 'readiness': {
            'model_fallback_enabled': False, 'fallback_enabled': False}}
        validate_comparison_server(metadata, DEFAULT_MODELS)
        for switch in ['model_fallback_enabled', 'fallback_enabled']:
            metadata['readiness'][switch] = True
            with self.assertRaises(ValueError):
                validate_comparison_server(metadata, DEFAULT_MODELS)
            metadata['readiness'][switch] = False
        metadata['models'] = [PRIMARY]
        with self.assertRaises(ValueError):
            validate_comparison_server(metadata, DEFAULT_MODELS)


    def test_comparison_contract_rejects_bool_steps(self):
        from evaluation.run_model_comparison import contract_is_valid
        result = {
            'arena_version': '0.1', 'request_id': 'x', 'status': 'completed',
            'final_response': 'ok', 'steps': True, 'stop_reason': 'done',
            'tool_calls': [], 'errors': [], 'events': [],
            'metrics': {'model_calls': 1, 'input_tokens': None, 'output_tokens': None, 'estimated_cost_usd': None},
        }
        self.assertFalse(contract_is_valid(result))
        result['steps'] = 1
        self.assertTrue(contract_is_valid(result))
