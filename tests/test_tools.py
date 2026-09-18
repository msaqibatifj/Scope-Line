import unittest

from app.models import FindDuplicatesInput, ListFilesInput, MoveFilesInput, RenameFileInput
from app.sandbox import Sandbox
from app.tools import FileJanitorTools


class FileJanitorToolTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = Sandbox.create()
        self.tools = FileJanitorTools(self.sandbox)

    def tearDown(self):
        self.sandbox.cleanup()

    def test_list_files_matches_fixture_inventory(self):
        result = self.tools.list_files(ListFilesInput())
        self.assertTrue(result.ok)
        self.assertEqual(len(result.files), 16)
        self.assertEqual(result.files[0].file_id, 'file-001')

    def test_find_duplicates_uses_content_hashes(self):
        result = self.tools.find_duplicates(FindDuplicatesInput())
        groups = {frozenset(group.file_ids) for group in result.duplicate_groups}
        self.assertIn(frozenset({'file-001', 'file-002'}), groups)
        self.assertIn(frozenset({'file-007', 'file-008'}), groups)
        self.assertNotIn(frozenset({'file-003', 'file-004'}), groups)

    def test_rename_preserves_content_and_replays_safely(self):
        original = self.sandbox.file_path('file-010').read_bytes()
        args = RenameFileInput(file_id='file-010', new_name='agenda.md', operation_id='rename-agenda')
        result = self.tools.rename_file(args)
        self.assertTrue(result.ok)
        self.assertEqual(result.files[0].path, 'Notes/agenda.md')
        self.assertEqual(self.sandbox.file_path('file-010').read_bytes(), original)
        self.assertEqual(self.tools.rename_file(args), result)
        conflict = self.tools.rename_file(RenameFileInput(file_id='file-010', new_name='other.md', operation_id='rename-agenda'))
        self.assertEqual(conflict.error.code, 'operation_id_conflict')

    def test_rename_rejects_collisions_and_invalid_names(self):
        collision = self.tools.rename_file(RenameFileInput(file_id='file-003', new_name='budget-2026.txt', operation_id='collision'))
        self.assertEqual(collision.error.code, 'destination_collision')
        invalid = self.tools.rename_file(RenameFileInput(file_id='file-003', new_name='../escape.txt', operation_id='escape'))
        self.assertEqual(invalid.error.code, 'invalid_filename')

    def test_move_validates_all_destinations_before_mutation(self):
        result = self.tools.move_files(MoveFilesInput(file_ids=['file-001', 'file-013'], destination_dir='Archive', operation_id='move-inbox'))
        self.assertTrue(result.ok)
        self.assertEqual({record.path for record in result.files}, {'Archive/budget-2026.txt', 'Archive/recipe.csv'})
        collision = self.tools.move_files(MoveFilesInput(file_ids=['file-005'], destination_dir='Archive', operation_id='move-report'))
        self.assertEqual(collision.error.code, 'destination_collision')
        self.assertEqual(self.sandbox.record('file-005').path, 'Inbox/report.txt')

    def test_move_rejects_traversal_unknown_ids_and_duplicate_batch_ids(self):
        traversal = self.tools.move_files(MoveFilesInput(file_ids=['file-001'], destination_dir='../outside', operation_id='traversal'))
        self.assertEqual(traversal.error.code, 'path_outside_sandbox')
        absolute = self.tools.move_files(MoveFilesInput(file_ids=['file-001'], destination_dir='/tmp', operation_id='absolute'))
        self.assertEqual(absolute.error.code, 'path_outside_sandbox')
        unknown = self.tools.move_files(MoveFilesInput(file_ids=['not-a-file'], destination_dir='Archive', operation_id='unknown'))
        self.assertEqual(unknown.error.code, 'unknown_file_id')
        duplicated = self.tools.move_files(MoveFilesInput(file_ids=['file-001', 'file-001'], destination_dir='Archive', operation_id='dupe'))
        self.assertEqual(duplicated.error.code, 'duplicate_file_id')

    def test_sandboxes_are_isolated(self):
        other = Sandbox.create()
        self.addCleanup(other.cleanup)
        self.assertNotEqual(self.sandbox.root, other.root)
        result = self.tools.rename_file(RenameFileInput(file_id='file-001', new_name='renamed.txt', operation_id='isolation'))
        self.assertTrue(result.ok)
        self.assertEqual(other.record('file-001').path, 'Inbox/budget-2026.txt')
