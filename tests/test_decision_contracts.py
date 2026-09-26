"""Regression cases from the first live Gemini comparison."""
import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agent import DECISION_INPUTS, DirectDecisionProvider, _parse_openrouter_decision, decision_tool_definitions
from app.config import settings
from app.main import app
from app.models import AgentDecision


def provider_response(name, arguments):
    return {'choices': [{'message': {'tool_calls': [{'function': {
        'name': name, 'arguments': json.dumps(arguments),
    }}]}}]}


class DecisionContractTests(unittest.TestCase):
    def test_valid_per_tool_decisions_are_translated_to_internal_contract(self):
        cases = {
            'list_projects': {'max_results': 7},
            'inspect_agreement': {'project_id': 'project-001'},
            'analyze_scope_drift': {'project_id': 'project-001', 'request_id': 'request-001'},
            'draft_change_request': {'project_id': 'project-001', 'analysis_id': 'analysis-001', 'operation_id': 'draft-project-001-analysis-001'},
            'finish': {'reason': 'The requested observation is complete.'},
            'ask_clarification': {'reason': 'Missing project', 'user_message': 'Which project?'},
            'block': {'reason': 'Outside authority', 'user_message': 'I cannot send messages.'},
        }
        for name, arguments in cases.items():
            with self.subTest(name=name):
                decision = AgentDecision.model_validate(_parse_openrouter_decision(provider_response(name, arguments)))
                self.assertEqual(decision.tool or decision.status, name)

    def test_live_failure_arguments_are_rejected_without_silent_filtering(self):
        cases = [
            ('inspect_agreement', {'project_id': 'project-001', 'max_results': 1}),
            ('analyze_scope_drift', {'project_id': 'project-001'}),
            ('analyze_scope_drift', {'project_id': 'project-001', 'request_text': None, 'request_id': None}),
            ('draft_change_request', {'project_id': 'project-001', 'analysis_id': 'analysis-001'}),
            ('finish', {'reason': 'x' * 501}),
            ('ask_clarification', {'reason': 'missing', 'user_message': 'x' * 1001}),
        ]
        for name, arguments in cases:
            with self.subTest(name=name, fields=list(arguments)):
                with self.assertRaises(ValidationError):
                    _parse_openrouter_decision(provider_response(name, arguments))

    def test_provider_schemas_expose_tool_constraints(self):
        schemas = {item['function']['name']: item['function']['parameters'] for item in decision_tool_definitions()}
        self.assertEqual(set(schemas['inspect_agreement']['properties']), {'project_id'})
        self.assertIn('operation_id', schemas['draft_change_request']['required'])
        self.assertEqual(schemas['finish']['properties']['reason']['maxLength'], 500)
        self.assertEqual(schemas['ask_clarification']['properties']['user_message']['maxLength'], 1000)
        self.assertEqual(schemas['list_projects']['properties']['max_results']['maximum'], 100)
        for schema in schemas.values():
            self.assertFalse(schema['additionalProperties'])

    def test_multiple_calls_and_unknown_tools_are_rejected(self):
        with self.assertRaises(ValueError):
            _parse_openrouter_decision(provider_response('send_email', {}))
        response = provider_response('list_projects', {})
        response['choices'][0]['message']['tool_calls'] *= 2
        with self.assertRaises(ValueError):
            _parse_openrouter_decision(response)

    def test_finish_renders_tool_evidence_instead_of_invented_model_text(self):
        decisions = [({'status': 'call_tool', 'tool': 'list_projects', 'arguments': {}, 'reason': 'list'}, {}),
                     ({'status': 'finish', 'reason': 'done', 'user_message': 'An invoice was sent.'}, {})]
        with patch.object(settings, 'model_name', 'local-scripted'), patch('app.agent.LocalDecisionProvider.decide', side_effect=[d for d, _ in decisions]), TestClient(app) as client:
            result = client.post('/run', json={'task': 'List projects'}).json()
        self.assertEqual(result['status'], 'completed')
        self.assertIn('project-001', result['final_response'])
        self.assertNotIn('invoice', result['final_response'])

    def test_completed_listing_rejects_unrequested_followup_tool(self):
        decisions = [
            ({'status': 'call_tool', 'tool': 'list_projects', 'arguments': {}, 'reason': 'list'}, {}),
            ({'status': 'call_tool', 'tool': 'analyze_scope_drift', 'arguments': {
                'project_id': 'project-001', 'request_id': 'request-001',
            }, 'reason': 'analyze'}, {}),
            ({'status': 'call_tool', 'tool': 'analyze_scope_drift', 'arguments': {
                'project_id': 'project-001', 'request_id': 'request-001',
            }, 'reason': 'analyze'}, {}),
        ]
        with patch.object(settings, 'model_name', 'local-scripted'), patch(
            'app.agent.LocalDecisionProvider.decide', side_effect=[d for d, _ in decisions]
        ), TestClient(app) as client:
            result = client.post('/run', json={'task': 'List projects'}).json()
        self.assertEqual(result['status'], 'contract_error')
        self.assertIn('already complete', result['errors'][-1]['message'])

    def test_timeout_failure_retains_exception_type(self):
        import httpx
        with patch.object(settings, 'model_name', 'gemini-3.1-flash-lite'), patch.object(settings, 'allowed_models', 'gemini-3.1-flash-lite'), patch.object(settings, 'gemini_api_key', 'test'), patch.object(settings, 'enable_live_models', True), patch.object(settings, 'direct_api_free_tier', True), patch.object(settings, 'allow_model_fallback', False), patch.object(settings, 'allow_local_fallback', False), patch.object(DirectDecisionProvider, 'decide', new=AsyncMock(side_effect=httpx.ReadTimeout(''))), TestClient(app) as client:
            result = client.post('/run', json={'task': 'List projects'}).json()
        self.assertEqual(result['errors'][0]['exception_type'], 'ReadTimeout')
        self.assertEqual(result['errors'][0]['message'], 'ReadTimeout')
