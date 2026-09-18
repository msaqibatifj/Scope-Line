"""Typed, sandbox-bound File Janitor tools."""
from __future__ import annotations

from collections import defaultdict
from typing import Callable

from app.models import DuplicateGroup, FindDuplicatesInput, ListFilesInput, MoveFilesInput, RenameFileInput, ToolError, ToolResult
from app.sandbox import Sandbox, SandboxError


class FileJanitorTools:
    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox

    def list_files(self, args: ListFilesInput) -> ToolResult:
        return ToolResult(ok=True, files=self.sandbox.all_records()[:args.max_results])

    def find_duplicates(self, args: FindDuplicatesInput) -> ToolResult:
        try:
            ids = args.file_ids or sorted(self.sandbox.file_paths)
            records = [self.sandbox.record(file_id) for file_id in ids]
        except SandboxError as error:
            return self._error(error)
        groups: dict[str, list[str]] = defaultdict(list)
        for record in records:
            groups[record.sha256].append(record.file_id)
        duplicates = [DuplicateGroup(sha256=digest, file_ids=ids) for digest, ids in groups.items() if len(ids) > 1]
        return ToolResult(ok=True, files=records, duplicate_groups=duplicates)

    def rename_file(self, args: RenameFileInput) -> ToolResult:
        signature = f'rename:{args.file_id}:{args.new_name}'
        replay = self._replay(args.operation_id, signature)
        if replay is not None:
            return replay
        try:
            source = self.sandbox.file_path(args.file_id)
            if args.new_name in ('.', '..') or '/' in args.new_name or '\\' in args.new_name:
                raise SandboxError('invalid_filename', 'New name must be a single filename.')
            destination = source.with_name(args.new_name)
            if destination.exists() or destination.is_symlink():
                raise SandboxError('destination_collision', 'A file already exists with that name.')
            before = source.read_bytes()
            source.replace(destination)
            self.sandbox.update_path(args.file_id, destination)
            if destination.read_bytes() != before:
                raise SandboxError('verification_failed', 'Renamed file content changed unexpectedly.')
            result = ToolResult(ok=True, operation_id=args.operation_id, affected_file_ids=[args.file_id], files=[self.sandbox.record(args.file_id)])
            self.sandbox.operations[args.operation_id] = (signature, result)
            return result
        except SandboxError as error:
            return self._error(error, args.operation_id)
        except OSError as error:
            return self._error(SandboxError('rename_failed', str(error)), args.operation_id)

    def move_files(self, args: MoveFilesInput) -> ToolResult:
        signature = f'move:{",".join(args.file_ids)}:{args.destination_dir}'
        replay = self._replay(args.operation_id, signature)
        if replay is not None:
            return replay
        try:
            if len(set(args.file_ids)) != len(args.file_ids):
                raise SandboxError('duplicate_file_id', 'A batch cannot include the same file more than once.')
            destination_dir = self.sandbox.destination_directory(args.destination_dir)
            sources = [(file_id, self.sandbox.file_path(file_id)) for file_id in args.file_ids]
            destinations = [(file_id, source, destination_dir / source.name) for file_id, source in sources]
            names = [destination.name for _, _, destination in destinations]
            if len(set(names)) != len(names):
                raise SandboxError('destination_collision', 'Two selected files would have the same destination name.')
            for _, source, destination in destinations:
                if source.parent == destination_dir:
                    raise SandboxError('no_op_move', 'A source is already in the requested destination.')
                if destination.exists() or destination.is_symlink():
                    raise SandboxError('destination_collision', f'Destination already exists: {destination.name}')
            moved: list[str] = []
            for file_id, source, destination in destinations:
                source.replace(destination)
                self.sandbox.update_path(file_id, destination)
                moved.append(file_id)
            records = [self.sandbox.record(file_id) for file_id in moved]
            result = ToolResult(ok=True, operation_id=args.operation_id, affected_file_ids=moved, files=records)
            self.sandbox.operations[args.operation_id] = (signature, result)
            return result
        except SandboxError as error:
            return self._error(error, args.operation_id)
        except OSError as error:
            return self._error(SandboxError('move_failed', str(error)), args.operation_id)

    def _replay(self, operation_id: str, signature: str) -> ToolResult | None:
        existing = self.sandbox.operations.get(operation_id)
        if existing is None:
            return None
        if existing[0] == signature:
            return existing[1]
        return ToolResult(ok=False, operation_id=operation_id, error=ToolError(code='operation_id_conflict', message='Operation ID was already used for a different action.'))

    @staticmethod
    def _error(error: SandboxError, operation_id: str | None = None) -> ToolResult:
        return ToolResult(ok=False, operation_id=operation_id, error=ToolError(code=error.code, message=str(error)))


TOOLS: dict[str, Callable] = {
    'list_files': FileJanitorTools.list_files,
    'find_duplicates': FileJanitorTools.find_duplicates,
    'rename_file': FileJanitorTools.rename_file,
    'move_files': FileJanitorTools.move_files,
}
