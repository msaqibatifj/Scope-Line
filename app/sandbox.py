"""Isolated, application-owned project records for scope-monitor tools."""
from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from app.config import ROOT
from app.models import ChangeRequestDraft, ClientRequestRecord, ProjectRecord, ScopeAnalysis


class SandboxError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass
class Sandbox:
    """A private copy of sample agreements, requests, analyses, and drafts."""

    root: Path
    projects: dict[str, dict]
    requests: dict[str, dict]
    analyses: dict[str, ScopeAnalysis] = field(default_factory=dict)
    drafts: dict[str, ChangeRequestDraft] = field(default_factory=dict)
    operations: dict[str, tuple[str, object]] = field(default_factory=dict)

    @classmethod
    def create(cls) -> 'Sandbox':
        fixture = json.loads((ROOT / 'data' / 'sample_data.json').read_text(encoding='utf-8'))
        root = Path(tempfile.mkdtemp(prefix='scope-drift-'))
        try:
            projects = {item['project_id']: item for item in fixture['projects']}
            requests = {item['request_id']: item for item in fixture['requests']}
            if len(projects) != len(fixture['projects']) or len(requests) != len(fixture['requests']):
                raise SandboxError('duplicate_fixture_id', 'Fixture IDs must be unique.')
            return cls(root=root, projects=projects, requests=requests)
        except Exception:
            shutil.rmtree(root, ignore_errors=True)
            raise

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def project(self, project_id: str) -> ProjectRecord:
        item = self.projects.get(project_id)
        if item is None:
            raise SandboxError('unknown_project_id', f'Unknown project ID: {project_id}')
        # Matching signals are internal evidence indexes, not public agreement fields.
        public_fields = {name: item[name] for name in ProjectRecord.model_fields}
        return ProjectRecord.model_validate(public_fields)

    def request(self, request_id: str, project_id: str | None = None) -> ClientRequestRecord:
        item = self.requests.get(request_id)
        if item is None:
            raise SandboxError('unknown_request_id', f'Unknown request ID: {request_id}')
        record = ClientRequestRecord.model_validate(item)
        if project_id and record.project_id != project_id:
            raise SandboxError('request_project_mismatch', 'The request does not belong to the selected project.')
        return record

    def all_projects(self) -> list[ProjectRecord]:
        return [self.project(project_id) for project_id in sorted(self.projects)]

    def project_signals(self, project_id: str) -> tuple[list[str], list[str]]:
        self.project(project_id)
        item = self.projects[project_id]
        return list(item.get('within_scope_signals', [])), list(item.get('out_of_scope_signals', []))

    def next_analysis_id(self) -> str:
        return f'analysis-{len(self.analyses) + 1:03d}'

    def next_draft_id(self) -> str:
        return f'draft-{len(self.drafts) + 1:03d}'
