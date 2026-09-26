"""Build the required ScopeLine submission ZIP, Markdown summary, and linked PDF.

Run after deploying the exact commit recorded in metadata. The script rejects blank
required fields and packages only the explicit application allowlist.
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    'full_name', 'roll_number', 'class_section', 'university_email', 'github_username',
    'github_repository_url', 'final_commit_hash', 'interface_url', 'health_url',
    'arena_url', 'manifest_url', 'docs_url', 'default_model_provider',
    'instructor_access_status',
)
URL_FIELDS = ('github_repository_url', 'interface_url', 'health_url', 'arena_url', 'manifest_url', 'docs_url')
INCLUDE = ('SUBMISSION.md', 'README.md', 'app', 'data', 'tests', 'evaluation', 'release', 'arena_manifest.json', 'requirements.txt', '.env.example', '.gitignore', '.dockerignore', 'render.yaml', 'Dockerfile', 'run.py', 'vercel.json', 'api')


def load_metadata(path: Path) -> dict[str, str]:
    values = json.loads(path.read_text(encoding='utf-8'))
    missing = [key for key in REQUIRED if not str(values.get(key, '')).strip()]
    if missing:
        raise SystemExit('Missing required metadata: ' + ', '.join(missing))
    roll = str(values['roll_number']).strip().lower()
    if not roll.replace('_', '').isalnum() or ' ' in roll:
        raise SystemExit('roll_number must be lowercase letters/numbers/underscores only')
    values['roll_number'] = roll
    return {key: str(value).strip() for key, value in values.items()}


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
    fixed = {'Agent name': 'ScopeLine', 'Domain': 'Freelance scope drift monitoring', 'Public test results': 'evaluation/public_results.json'}
    for label, key in rows:
        lines.append(f'- {label}: {metadata[key] if key else fixed[label]}')
    return '\n'.join(lines) + '\n'


def pdf_escape(value: str) -> str:
    return value.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def linked_pdf(path: Path, metadata: dict[str, str]) -> None:
    # A deliberately small, standards-compliant one-page PDF with clickable URI annotations.
    lines = [line[2:] for line in summary(metadata).splitlines() if line.startswith('- ')]
    content = ['BT', '/F1 10 Tf', '50 760 Td']
    for index, line in enumerate(lines):
        if index:
            content.append('0 -25 Td')
        content.append(f'({pdf_escape(line[:150])}) Tj')
    content.append('ET')
    annotations = []
    for field in URL_FIELDS:
        url = metadata[field]
        row = lines.index(next(line for line in lines if url in line))
        annotations.append(f'<< /Type /Annot /Subtype /Link /Rect [45 {735 - row * 25} 550 {750 - row * 25}] /Border [0 0 0] /A << /S /URI /URI ({pdf_escape(url)}) >> >>')
    annotation_ids = range(6, 6 + len(annotations))
    annots = ' '.join(f'{item} 0 R' for item in annotation_ids)
    stream = '\n'.join(content)
    objects = [
        '<< /Type /Catalog /Pages 2 0 R >>',
        '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R /Annots [{annots}] >>',
        f'<< /Length {len(stream.encode())} >>\nstream\n{stream}\nendstream',
        '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        *annotations,
    ]
    raw = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for number, value in enumerate(objects, 1):
        offsets.append(len(raw))
        raw.extend(f'{number} 0 obj\n{value}\nendobj\n'.encode())
    start = len(raw)
    raw.extend(f'xref\n0 {len(objects) + 1}\n0000000000 65535 f \n'.encode())
    raw.extend(''.join(f'{offset:010d} 00000 n \n' for offset in offsets[1:]).encode())
    raw.extend(f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode())
    path.write_bytes(raw)


def build_zip(path: Path, roll_number: str) -> None:
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for item in INCLUDE:
            source = ROOT / item
            if source.is_file():
                archive.write(source, Path(roll_number) / source.name)
            elif source.is_dir():
                for child in source.rglob('*'):
                    if child.is_file() and '__pycache__' not in child.parts and child.suffix != '.pyc':
                        archive.write(child, Path(roll_number) / child.relative_to(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    metadata = load_metadata(args.metadata)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    markdown = summary(metadata)
    (ROOT / 'SUBMISSION.md').write_text(markdown, encoding='utf-8')
    (args.output_dir / f'{metadata["roll_number"]}_submission.pdf').parent.mkdir(parents=True, exist_ok=True)
    linked_pdf(args.output_dir / f'{metadata["roll_number"]}_submission.pdf', metadata)
    build_zip(args.output_dir / f'{metadata["roll_number"]}.zip', metadata['roll_number'])
    print('Created submission artifacts in', args.output_dir)


if __name__ == '__main__':
    main()
