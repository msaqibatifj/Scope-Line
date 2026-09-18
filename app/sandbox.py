"""Application-owned fixture sandboxes for File Janitor tools."""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from app.config import ROOT
from app.models import FileRecord


class SandboxError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass
class Sandbox:
    root: Path
    file_paths: dict[str, str]
    origins: dict[str, str]
    operations: dict[str, tuple[str, object]] = field(default_factory=dict)

    @classmethod
    def create(cls) -> 'Sandbox':
        fixture = json.loads((ROOT / 'data' / 'sample_data.json').read_text(encoding='utf-8'))
        root = Path(tempfile.mkdtemp(prefix='file-janitor-'))
        try:
            for directory in fixture['directories']:
                (root / directory).mkdir(parents=True, exist_ok=False)
            paths: dict[str, str] = {}
            origins: dict[str, str] = {}
            for item in fixture['files']:
                relative = cls._validate_fixture_path(item['path'])
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(item['content'], encoding='utf-8')
                paths[item['id']] = relative.as_posix()
                origins[item['id']] = item['origin']
            return cls(root=root, file_paths=paths, origins=origins)
        except Exception:
            shutil.rmtree(root, ignore_errors=True)
            raise

    @staticmethod
    def _validate_fixture_path(value: str) -> PurePosixPath:
        path = PurePosixPath(value)
        if path.is_absolute() or not path.parts or any(part in ('', '.', '..') for part in path.parts):
            raise SandboxError('invalid_fixture_path', 'Fixture path must be a safe relative path.')
        return path

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _resolve_relative(self, relative: str) -> Path:
        path = PurePosixPath(relative)
        if path.is_absolute() or any(part in ('', '.', '..') for part in path.parts):
            raise SandboxError('path_outside_sandbox', 'Paths must remain relative to this sandbox.')
        target = (self.root / Path(*path.parts)).resolve(strict=False)
        if not target.is_relative_to(self.root.resolve()):
            raise SandboxError('path_outside_sandbox', 'Path resolves outside this sandbox.')
        return target

    def file_path(self, file_id: str) -> Path:
        relative = self.file_paths.get(file_id)
        if relative is None:
            raise SandboxError('unknown_file_id', f'Unknown file ID: {file_id}')
        path = self._resolve_relative(relative)
        if path.is_symlink() or not path.is_file():
            raise SandboxError('missing_source', f'File is unavailable: {file_id}')
        return path

    def destination_directory(self, value: str) -> Path:
        path = self._resolve_relative(value)
        if path.is_symlink() or not path.is_dir():
            raise SandboxError('invalid_destination', 'Destination must be an existing sandbox folder.')
        return path

    def record(self, file_id: str) -> FileRecord:
        path = self.file_path(file_id)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return FileRecord(file_id=file_id, path=path.relative_to(self.root).as_posix(), size_bytes=path.stat().st_size, sha256=digest, fixture_origin=self.origins[file_id])

    def all_records(self) -> list[FileRecord]:
        return [self.record(file_id) for file_id in sorted(self.file_paths)]

    def update_path(self, file_id: str, path: Path) -> None:
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(self.root.resolve()):
            raise SandboxError('path_outside_sandbox', 'Result escaped the sandbox.')
        self.file_paths[file_id] = resolved.relative_to(self.root).as_posix()
