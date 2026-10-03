"""Build the required ScopeLine submission ZIP, Markdown summary, and linked PDF.

Run after deploying the exact commit recorded in metadata. The script rejects blank
required fields and packages only the explicit application allowlist.
"""
from __future__ import annotations

import argparse
import json
import re
import zipfile
import ipaddress
import subprocess
import os
from xml.sax.saxutils import escape
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    'full_name', 'roll_number', 'class_section', 'university_email', 'github_username',
    'github_repository_url', 'final_commit_hash', 'interface_url', 'health_url',
    'arena_url', 'manifest_url', 'docs_url', 'default_model_provider',
    'instructor_access_status', 'hosting_provider', 'example_input', 'expected_result',
    'cold_start_limitations',
)
URL_FIELDS = ('github_repository_url', 'interface_url', 'health_url', 'arena_url', 'manifest_url', 'docs_url')
INCLUDE = ('SUBMISSION.md', 'README.md', 'app', 'data', 'tests', 'evaluation', 'release', 'arena_manifest.json', 'requirements.txt', '.env.example', '.gitignore', '.dockerignore', 'render.yaml', 'Dockerfile', 'run.py', 'vercel.json', 'api')


def load_metadata(path: Path) -> dict[str, str]:
    values = json.loads(path.read_text(encoding='utf-8'))
    missing = [key for key in REQUIRED if not str(values.get(key, '')).strip()]
    if missing:
        raise SystemExit('Missing required metadata: ' + ', '.join(missing))
    values = {key: str(value).strip() for key, value in values.items()}
    placeholders = [key for key, value in values.items() if re.search(r'PENDING_|\[|\]|YOUR[-_ ]|TODO|REPLACE_ME', value, re.I)]
    if placeholders:
        raise SystemExit('Replace placeholder metadata: ' + ', '.join(placeholders))
    roll = values['roll_number'].lower()
    if not re.fullmatch(r'[a-z0-9]+', roll):
        raise SystemExit('roll_number must contain lowercase letters and numbers only')
    if not re.fullmatch(r'[0-9a-f]{40,64}', values['final_commit_hash'], re.IGNORECASE):
        raise SystemExit('final_commit_hash must be a full Git commit hash')
    for field in URL_FIELDS:
        parsed = urlparse(values[field])
        host = (parsed.hostname or '').lower().rstrip('.')
        invalid_host = not host or '.' not in host or host == 'localhost' or host.endswith(('.localhost', '.local', '.invalid', '.example', '.test'))
        try:
            invalid_host = invalid_host or not ipaddress.ip_address(host).is_global
        except ValueError:
            pass
        if parsed.scheme != 'https' or invalid_host or parsed.username or parsed.password:
            raise SystemExit(f'{field} must be a public HTTPS URL')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', values['university_email']):
        raise SystemExit('university_email must be an email address')
    if values['instructor_access_status'].lower() not in {'pending', 'invited', 'accepted', 'confirmed'}:
        raise SystemExit('instructor_access_status must be pending, invited, accepted or confirmed')
    values.setdefault('other_models', 'none')
    values['roll_number'] = roll
    return values


def summary(metadata: dict[str, str]) -> str:
    rows = [
        ('Full name', 'full_name'), ('Roll number', 'roll_number'), ('Class / section', 'class_section'),
        ('University email', 'university_email'), ('GitHub username', 'github_username'),
        ('Agent name', None), ('Domain', None), ('GitHub repository URL', 'github_repository_url'),
        ('Final commit hash', 'final_commit_hash'), ('Working agent interface', 'interface_url'),
        ('Health endpoint (GET)', 'health_url'), ('Arena endpoint (POST)', 'arena_url'),
        ('Manifest endpoint (GET)', 'manifest_url'), ('API documentation', 'docs_url'),
        ('Hosting provider', 'hosting_provider'), ('Default model / provider', 'default_model_provider'),
        ('Other available models', 'other_models'), ('Example input', 'example_input'),
        ('Expected result', 'expected_result'), ('Cold-start / restart limitations', 'cold_start_limitations'),
        ('Repository access', 'instructor_access_status'), ('Public test results', None),
    ]
    lines = ['# ScopeLine submission summary', '']
    fixed = {'Agent name': 'ScopeLine', 'Domain': 'Freelance scope drift monitoring', 'Public test results': 'evaluation/current_local_results.json (local); evaluation/public_results.json (historical public); evaluation/current_public_verification.json (current availability)'}
    for label, key in rows:
        lines.append(f'- {label}: {metadata[key] if key else fixed[label]}')
    return '\n'.join(lines) + '\n'


def pdf_escape(value: str) -> str:
    # Built-in Helvetica is WinAnsi only; replace unsupported glyphs rather than
    # emitting an invalid literal string. URLs remain ASCII and are unaffected.
    value = value.encode('cp1252', 'replace').decode('cp1252')
    return value.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def linked_pdf(path: Path, metadata: dict[str, str]) -> None:
    import reportlab
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph
    candidates = [Path(os.environ.get('SUBMISSION_FONT', 'missing.ttf')),
                  Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
                  Path('C:/Windows/Fonts/arial.ttf'), Path(reportlab.__file__).parent / 'fonts/Vera.ttf']
    font = next((candidate for candidate in candidates if candidate.is_file()), None)
    if font is None:
        raise SystemExit('Set SUBMISSION_FONT to a Unicode TrueType font path.')
    pdfmetrics.registerFont(TTFont('Submission', str(font)))
    text = summary(metadata)
    glyphs = pdfmetrics.getFont('Submission').face.charWidths
    if any(ord(c) not in glyphs for c in text if not c.isspace()):
        raise SystemExit('Submission font lacks a metadata character; set SUBMISSION_FONT to a font supporting your name.')
    body = ParagraphStyle('SubmissionBody', fontName='Submission', fontSize=10, leading=15, spaceAfter=9, splitLongWords=True)
    title = ParagraphStyle('SubmissionTitle', parent=body, fontSize=19, leading=25, spaceAfter=18)
    story = [Paragraph('ScopeLine submission summary', title)]
    urls = {metadata[field] for field in URL_FIELDS}
    for line in text.splitlines():
        if not line.startswith('- '):
            continue
        label, value = line[2:].split(': ', 1)
        rendered = escape(value)
        if value in urls:
            rendered = f'<link href="{escape(value, {chr(34): "&quot;"})}" color="#175CD3">{rendered}</link>'
        story.append(Paragraph(f'{escape(label)}: {rendered}', body))
    SimpleDocTemplate(str(path), leftMargin=48, rightMargin=48, topMargin=48, bottomMargin=48, title='ScopeLine submission summary').build(story)


def build_zip(path: Path, roll_number: str) -> None:
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for item in INCLUDE:
            source = ROOT / item
            if source.is_file():
                archive.write(source, Path(roll_number) / source.name)
            elif source.is_dir():
                for child in source.rglob('*'):
                    blocked_parts = {'__pycache__', '.git', '.venv', 'venv', 'node_modules', '.pytest_cache'}
                    secret_file = (child.name == '.env' or child.name.startswith('.env.') or re.search(r'credential|secret|token|private[-_]?key', child.name, re.I)) and child.name != '.env.example'
                    if child.is_file() and not (blocked_parts & set(child.parts)) and not secret_file and child.suffix not in {'.pyc', '.zip', '.pdf', '.log', '.pem', '.key', '.p12'}:
                        archive.write(child, Path(roll_number) / child.relative_to(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    metadata = load_metadata(args.metadata)
    try:
        git = ['git', '-c', f'safe.directory={ROOT}']
        revision = subprocess.check_output([*git, 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        dirty = subprocess.check_output([*git, 'status', '--porcelain', '--untracked-files=all'], cwd=ROOT, text=True).rstrip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise SystemExit('Build the final release from its Git checkout with Git available.') from error
    changed_files = [line[3:] for line in dirty.splitlines()]
    if revision != metadata['final_commit_hash'] or any(name != 'SUBMISSION.md' for name in changed_files):
        raise SystemExit('Commit final source first; only SUBMISSION.md may differ from the checkout matching final_commit_hash.')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    markdown = summary(metadata)
    # Generated metadata is added after the source commit to avoid a self-referential commit hash.
    (ROOT / 'SUBMISSION.md').write_text(markdown, encoding='utf-8')
    (args.output_dir / f'{metadata["roll_number"]}_submission.pdf').parent.mkdir(parents=True, exist_ok=True)
    linked_pdf(args.output_dir / f'{metadata["roll_number"]}_submission.pdf', metadata)
    build_zip(args.output_dir / f'{metadata["roll_number"]}.zip', metadata['roll_number'])
    print('Created submission artifacts in', args.output_dir)


if __name__ == '__main__':
    main()
