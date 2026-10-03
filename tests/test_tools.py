import unittest

from app.models import AnalyzeScopeDriftInput, DraftChangeRequestInput, InspectAgreementInput, ListProjectsInput
from app.sandbox import Sandbox, SandboxError
from app.tools import ScopeDriftTools


class ScopeDriftToolTests(unittest.TestCase):
    def setUp(self):
        # Each test gets independent sample agreements, analyses, and drafts.
        self.sandbox = Sandbox.create()
        self.tools = ScopeDriftTools(self.sandbox)

    def tearDown(self):
        self.sandbox.cleanup()

    def test_list_projects_matches_fixture(self):
        result = self.tools.list_projects(ListProjectsInput())
        self.assertTrue(result.ok)
        self.assertEqual(len(result.projects), 3)
        self.assertEqual(result.projects[0].project_id, 'project-001')

    def test_inspect_agreement_returns_scope_and_requests(self):
        result = self.tools.inspect_agreement(InspectAgreementInput(project_id='project-001'))
        self.assertTrue(result.ok)
        self.assertIn('E-commerce, checkout, and inventory systems', result.projects[0].exclusions)
        self.assertEqual([item.request_id for item in result.requests], ['request-001', 'request-002', 'request-003'])

    def test_analyze_explicit_exclusion_as_scope_drift(self):
        result = self.tools.analyze_scope_drift(AnalyzeScopeDriftInput(project_id='project-001', request_id='request-001'))
        self.assertTrue(result.ok)
        self.assertEqual(result.analysis.classification, 'scope_drift')
        self.assertTrue(any(item.category == 'explicit_exclusion' for item in result.analysis.findings))

    def test_analyze_matching_deliverable_as_within_scope(self):
        result = self.tools.analyze_scope_drift(AnalyzeScopeDriftInput(project_id='project-001', request_id='request-002'))
        self.assertTrue(result.ok)
        self.assertEqual(result.analysis.classification, 'within_scope')
        self.assertTrue(any(item.evidence == 'home page' for item in result.analysis.findings))

    def test_analyze_vague_request_as_ambiguous(self):
        result = self.tools.analyze_scope_drift(AnalyzeScopeDriftInput(project_id='project-001', request_id='request-003'))
        self.assertTrue(result.ok)
        self.assertEqual(result.analysis.classification, 'ambiguous')
        self.assertEqual(result.analysis.confidence, 'low')

    def test_negated_scope_signal_is_ambiguous(self):
        result = self.tools.analyze_scope_drift(AnalyzeScopeDriftInput(
            project_id='project-001', request_text='Please do not add checkout to the home page.',
        ))
        self.assertEqual(result.analysis.classification, 'ambiguous')
        self.assertEqual(result.analysis.findings[0].category, 'conflicting_evidence')

    def test_mixed_scope_signals_are_ambiguous(self):
        result = self.tools.analyze_scope_drift(AnalyzeScopeDriftInput(
            project_id='project-001', request_text='Update the home page and add checkout.',
        ))
        self.assertEqual(result.analysis.classification, 'ambiguous')
        self.assertEqual(result.analysis.findings[0].category, 'conflicting_evidence')

    def test_revision_limit_can_create_scope_drift(self):
        result = self.tools.analyze_scope_drift(AnalyzeScopeDriftInput(
            project_id='project-003',
            request_text='Please make another color correction revision.',
        ))
        self.assertEqual(result.analysis.classification, 'scope_drift')
        self.assertTrue(any(item.category == 'revision_limit' for item in result.analysis.findings))

    def test_request_must_belong_to_project(self):
        result = self.tools.analyze_scope_drift(AnalyzeScopeDriftInput(project_id='project-002', request_id='request-001'))
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, 'request_project_mismatch')

    def test_draft_requires_confirmed_drift_and_replays_safely(self):
        analysis = self.tools.analyze_scope_drift(AnalyzeScopeDriftInput(project_id='project-001', request_id='request-001')).analysis
        args = DraftChangeRequestInput(project_id='project-001', analysis_id=analysis.analysis_id, operation_id='draft-checkout')
        result = self.tools.draft_change_request(args)
        self.assertTrue(result.ok)
        self.assertEqual(result.draft.status, 'draft_only')
        self.assertIn('no fee or deadline will change', result.draft.body)
        self.assertEqual(self.tools.draft_change_request(args), result)
        conflict = self.tools.draft_change_request(DraftChangeRequestInput(
            project_id='project-001', analysis_id=analysis.analysis_id, operation_id='draft-checkout-other'
        ))
        self.assertTrue(conflict.ok)

    def test_operation_id_conflict_is_rejected(self):
        first = self.tools.analyze_scope_drift(AnalyzeScopeDriftInput(project_id='project-001', request_id='request-001')).analysis
        second = self.tools.analyze_scope_drift(AnalyzeScopeDriftInput(project_id='project-002', request_id='request-004')).analysis
        self.tools.draft_change_request(DraftChangeRequestInput(project_id='project-001', analysis_id=first.analysis_id, operation_id='same-op'))
        result = self.tools.draft_change_request(DraftChangeRequestInput(project_id='project-002', analysis_id=second.analysis_id, operation_id='same-op'))
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, 'operation_id_conflict')

    def test_draft_rejects_within_scope_analysis(self):
        analysis = self.tools.analyze_scope_drift(AnalyzeScopeDriftInput(project_id='project-001', request_id='request-002')).analysis
        result = self.tools.draft_change_request(DraftChangeRequestInput(
            project_id='project-001', analysis_id=analysis.analysis_id, operation_id='not-drift'
        ))
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, 'change_request_not_supported')

    def test_sandboxes_are_isolated(self):
        other = Sandbox.create()
        self.addCleanup(other.cleanup)
        analysis = self.tools.analyze_scope_drift(AnalyzeScopeDriftInput(project_id='project-001', request_id='request-001')).analysis
        self.assertIn(analysis.analysis_id, self.sandbox.analyses)
        self.assertNotIn(analysis.analysis_id, other.analyses)
        self.assertNotEqual(self.sandbox.root, other.root)

    def test_unknown_project_raises_typed_error(self):
        with self.assertRaises(SandboxError) as error:
            self.sandbox.project('project-999')
        self.assertEqual(error.exception.code, 'unknown_project_id')


    def test_photo_quantity_above_agreement_is_scope_drift(self):
        result = self.tools.analyze_scope_drift(AnalyzeScopeDriftInput(
            project_id='project-003', request_text='Please deliver 100 product photos on a neutral background.'
        ))
        self.assertEqual(result.analysis.classification, 'scope_drift')
        self.assertIn('exceeds 20', result.analysis.findings[0].evidence)

    def test_episode_quantity_and_duration_above_agreement_are_scope_drift(self):
        result = self.tools.analyze_scope_drift(AnalyzeScopeDriftInput(
            project_id='project-002', request_text='Please master ten 90 minute episodes.'
        ))
        self.assertEqual(result.analysis.classification, 'scope_drift')
        evidence = ' '.join(item.evidence for item in result.analysis.findings)
        self.assertIn('exceeds 4', evidence)
        self.assertIn('exceeds 45', evidence)

    def test_brush_dust_does_not_match_rush_exclusion(self):
        result = self.tools.analyze_scope_drift(AnalyzeScopeDriftInput(
            project_id='project-003', request_text='Please brush dust off the product photos.'
        ))
        self.assertNotEqual(result.analysis.classification, 'scope_drift')
        self.assertFalse(any(item.evidence == 'rush' for item in result.analysis.findings))

    def test_written_and_hour_duration_limits_are_scope_drift(self):
        photo = self.tools.analyze_scope_drift(AnalyzeScopeDriftInput(
            project_id='project-003', request_text='Deliver twenty five product photos on a neutral background.'
        ))
        duration = self.tools.analyze_scope_drift(AnalyzeScopeDriftInput(
            project_id='project-002', request_text='Mastering for four episodes of 2 hours each.'
        ))
        self.assertEqual(photo.analysis.classification, 'scope_drift')
        self.assertEqual(duration.analysis.classification, 'scope_drift')

    def test_unmatched_material_work_is_not_approved(self):
        result = self.tools.analyze_scope_drift(AnalyzeScopeDriftInput(
            project_id='project-003',
            request_text='Deliver twenty product photos on a neutral background and build a custom mobile app.',
        ))
        self.assertEqual(result.analysis.classification, 'scope_drift')
        self.assertTrue(any(item.category == 'missing_evidence' for item in result.analysis.findings))
