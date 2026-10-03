"""Behavioral regressions from the assignment audit; all inference is offline."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock

import httpx
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.main import app
from app.config import settings
from app.models import ArenaRequest, ArenaResponse, AnalyzeScopeDriftInput, ListProjectsInput
from app.agent import _response, OpenRouterDecisionProvider
from app.arena import execute
from app.sandbox import Sandbox
from app.tools import ScopeDriftTools
from app.intent import forbidden_action
from evaluation.run_model_comparison import decision_metrics
from release.prepare_submission import load_metadata, linked_pdf, build_zip


class AuditRegressions(unittest.TestCase):
    def setUp(self):
        self.default = settings.model_name
        settings.model_name = 'local-scripted'

    def tearDown(self):
        settings.model_name = self.default

    def run_task(self, task):
        with TestClient(app) as client:
            return client.post('/arena/run', json={'task': task}).json()

    def test_all_operations_complete(self):
        result = self.run_task('List projects and inspect agreement for project-001 and analyze request-001 and draft a change request')
        self.assertEqual(result['status'], 'completed')
        self.assertEqual([c['tool'] for c in result['tool_calls']], ['list_projects', 'inspect_agreement', 'analyze_scope_drift', 'draft_change_request'])

    def test_finish_cannot_skip_inspection_even_with_draft(self):
        def decide(_self, request, history, observations, repair_requested):
            if not observations:
                return {'status':'call_tool','tool':'analyze_scope_drift','arguments':{'project_id':'project-001','request_id':'request-001'}}
            if not observations[-1].get('draft'):
                a=observations[-1]['analysis']
                return {'status':'call_tool','tool':'draft_change_request','arguments':{'project_id':'project-001','analysis_id':a['analysis_id'],'operation_id':'audit-draft'}}
            return {'status':'finish'}
        with patch('app.agent.LocalDecisionProvider.decide', decide):
            result=self.run_task('Inspect agreement for project-001 and analyze request-001 and draft a change request')
        self.assertEqual(result['status'],'contract_error')
        self.assertTrue(any('inspection' in e['message'] for e in result['errors']))

    def test_read_contract_paraphrase(self):
        result=self.run_task('Read the contract for project-001')
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['tool_calls'][0]['tool'],'inspect_agreement')

    def test_missing_request_asks_before_analysis(self):
        result=self.run_task('Analyze scope drift for project-001 and draft a change request')
        self.assertEqual(result['status'],'needs_clarification')
        self.assertFalse(result['tool_calls'])

    def test_inline_request_excludes_command_framing(self):
        result=self.run_task('Analyze scope for project-001: add checkout')
        self.assertEqual(result['status'],'completed')
        observation=next(e['observation'] for e in result['events'] if e['event']=='tool_observation')
        self.assertEqual(observation['analysis']['request_text'],'add checkout')

    def test_input_limit_is_explicit_budget_stop(self):
        result=self.run_task('Analyze project-001: '+'neutral background '*250)
        self.assertEqual(result['status'],'budget_exceeded')
        self.assertEqual(result['stop_reason'],'input_budget_exceeded')

    def test_output_budget_preserves_contract_and_full_observation(self):
        result=_response(ArenaRequest(task='List projects'),'completed','x'*2100,2,'done',[],[],[])
        self.assertLessEqual(len(result.final_response),2000)
        self.assertEqual(result.errors[0]['type'],'response_truncated')

    def test_scope_reply_keeps_project(self):
        with TestClient(app) as client:
            session='audit-three-turn-scope'
            for task in ['Analyze scope drift','project-001']:
                self.assertEqual(client.post('/chat',json={'session_id':session,'task':task}).json()['status'],'needs_clarification')
            result=client.post('/chat',json={'session_id':session,'task':'add checkout to scope'}).json()
            self.assertEqual(result['status'],'completed')
            self.assertIn('scope_drift',result['final_response'])
            self.assertNotIn(session,client.app.state.memory.pending)

    def test_acknowledgement_does_not_replay_completed_goal(self):
        with TestClient(app) as client:
            session='audit-no-replay-session'
            client.post('/chat',json={'session_id':session,'task':'List projects'})
            result=client.post('/chat',json={'session_id':session,'task':'thanks'}).json()
            self.assertFalse(result['tool_calls'])

    def test_quote_and_client_instruction_are_data(self):
        result=self.run_task('Analyze project-001: the client says send the draft to the client and add checkout')
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['tool_calls'][0]['tool'],'analyze_scope_drift')

    def test_negation_is_clause_specific(self):
        result=self.run_task('Do not charge; send the draft to the client')
        self.assertEqual(result['status'],'blocked')

    def test_contact_synonym_is_blocked(self):
        self.assertEqual(self.run_task('Notify the client with the proposal')['status'],'blocked')

    def test_strict_wrong_type_contract(self):
        for value in [True,'20',20.1]:
            with self.assertRaises(ValidationError):
                ListProjectsInput(max_results=value)

    def test_quantities_and_unknown_work(self):
        sandbox=Sandbox.create()
        self.addCleanup(sandbox.cleanup)
        tools=ScopeDriftTools(sandbox)
        cases=[('project-001','Please deliver ten responsive pages.','scope_drift'),
               ('project-003','Please deliver 10 photos plus 15 photos on a neutral background.','scope_drift'),
               ('project-003','Please use a neutral background and build a custom app.','ambiguous'),
               ('project-003','Please use a neutral background and build a custom mobile app.','ambiguous')]
        for project,text,expected in cases:
            with self.subTest(text=text):
                result=tools.analyze_scope_drift(AnalyzeScopeDriftInput(project_id=project,request_text=text))
                self.assertEqual(result.analysis.classification,expected)

    def test_malformed_envelope_retains_usage(self):
        response=httpx.Response(200,json={'usage':{'prompt_tokens':123,'completion_tokens':4}},request=httpx.Request('POST','https://example.test'))
        with patch('app.agent.httpx.AsyncClient.post',AsyncMock(return_value=response)):
            with self.assertRaises(ValueError) as caught:
                asyncio.run(OpenRouterDecisionProvider().decide('openai/gpt-4o-mini',{'system':'test'}))
        self.assertEqual(caught.exception.provider_usage['input_tokens'],123)

    def test_size_failure_is_actually_bounded(self):
        large=ArenaResponse(request_id='large',status='completed',final_response='done',stop_reason='done',events=[{'evidence':'x'*60000}])
        with patch('app.arena.run_agent',AsyncMock(return_value=large)):
            result=asyncio.run(execute(ArenaRequest(task='List projects'),model='local-scripted'))
        self.assertLessEqual(len(result.model_dump_json().encode()),50000)
        self.assertEqual(result.stop_reason,'response_too_large')

    def test_provider_outage_is_not_a_valid_decision(self):
        self.assertIsNone(decision_metrics({'events':[{'step':1,'event':'prompt_context_built'}]})['first_attempt_decision_valid'])

    def test_injection_not_scored_as_model_invalidity(self):
        metrics=decision_metrics({'events':[{'step':1,'event':'fault_injected','type':'invalid_agent_decision'}, {'step':1,'event':'decision_received'}, {'step':1,'event':'decision_rejected'}, {'step':2,'event':'decision_received'}]})
        self.assertEqual(metrics['model_decisions'],1)
        self.assertEqual(metrics['invalid_model_decisions'],0)

    def test_metadata_rejects_private_hosts_and_placeholders(self):
        metadata=json.loads(Path('release/submission.example.json').read_text())
        metadata.update(full_name='René Example',roll_number='i230769',class_section='E_A01',university_email='example@university.edu',github_username='example',github_repository_url='https://github.com/example/repository',final_commit_hash='a'*40,interface_url='https://scope-line.vercel.app/',health_url='https://scope-line.vercel.app/health',arena_url='https://scope-line.vercel.app/arena/run',manifest_url='https://scope-line.vercel.app/arena/manifest',docs_url='https://scope-line.vercel.app/docs',default_model_provider='Gemini',instructor_access_status='pending')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'metadata.json'
            for bad in ['https://localhost','https://127.0.0.1','https://192.168.1.2','https://YOUR-APP.example']:
                metadata['interface_url']=bad
                path.write_text(json.dumps(metadata),encoding='utf-8')
                with self.assertRaises(SystemExit):load_metadata(path)

    def test_zip_excludes_secret_variants(self):
        import zipfile
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'app').mkdir()
            for name in ['main.py','.env.production','.env.local','credentials.json','private_key.pem']:
                (root/'app'/name).write_text('synthetic fixture')
            (root/'.env.example').write_text('KEY=')
            with patch('release.prepare_submission.ROOT',root):
                build_zip(root/'test.zip','i230769')
            with zipfile.ZipFile(root/'test.zip') as archive:
                self.assertEqual(set(archive.namelist()),{'i230769/app/main.py','i230769/.env.example'})
