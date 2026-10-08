"""Build an allowlisted source ZIP and standalone zipapp using only stdlib."""
import hashlib
from pathlib import Path
import shutil
import tempfile
import zipapp
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'
DIST.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as directory:
    stage = Path(directory)
    shutil.copytree(ROOT / 'src/goalkeeper', stage / 'goalkeeper', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    zipapp.create_archive(stage, DIST / 'goalkeeper.pyz', interpreter='/usr/bin/env python3', main='goalkeeper.cli:main', compressed=True)
allow = ['README.md', 'LICENSE', 'VALIDATION.md', 'pyproject.toml', '.gitignore', 'AGENTS.md']
paths = [ROOT / name for name in allow]
for folder in ('src', 'tests', 'tools', 'docs'):
    paths += [p for p in (ROOT / folder).rglob('*') if p.is_file() and p.suffix in ('.py', '.md') and '__pycache__' not in p.parts]
archive = DIST / 'goalkeeper-0.1.0.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
    for path in sorted(paths):
        output.write(path, 'goalkeeper-0.1.0/' + path.relative_to(ROOT).as_posix())
    output.write(DIST / 'goalkeeper.pyz', 'goalkeeper-0.1.0/goalkeeper.pyz')
checksums = '\n'.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name for p in (DIST / 'goalkeeper.pyz', archive)) + '\n'
(DIST / 'SHA256SUMS').write_text(checksums)
print(checksums, end='')
