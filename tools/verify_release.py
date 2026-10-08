"""Validate release content, checksums, and commands from an extracted ZIP."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'
for line in (DIST / 'SHA256SUMS').read_text().splitlines():
    expected, name = line.split('  ', 1)
    assert hashlib.sha256((DIST / name).read_bytes()).hexdigest() == expected, name
with zipfile.ZipFile(DIST / 'context-loop-0.2.0.zip') as archive:
    for name in archive.namelist():
        path = Path(name)
        assert not path.is_absolute() and '..' not in path.parts
        assert not set(path.parts) & {'.private', '.git', '.context-loop', '__pycache__'}
        assert path.name not in {'auth.json', 'token.json', '.env'}
    with tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve()) as directory:
        destination = Path(directory)
        archive.extractall(destination)
        release = destination / 'context-loop-0.2.0'
        app = release / 'context-loop.pyz'
        with zipfile.ZipFile(app) as packaged:
            for name in packaged.namelist():
                if name.endswith('.py') and name != '__main__.py':
                    assert packaged.read(name) == (ROOT / 'src' / name).read_bytes(), name
        def run(*args):
            result = subprocess.run([sys.executable, str(app), *args], capture_output=True, text=True, timeout=20)
            assert result.returncode == 0, result.stderr
            return result.stdout
        assert 'doctor' in run('--help')
        project = destination / 'new-demo'
        run('init', str(project), '--demo')
        assert json.loads(run('status', str(project)))['status'] == 'ready'
        run('stop', str(project))
        assert (project / '.context-loop/stop').exists()
        assert (release / 'README.md').is_file()
print('PASS: checksums, sanitized archive paths, exact packaged source, extracted CLI help/init/status/stop')
