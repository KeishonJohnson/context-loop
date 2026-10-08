"""Validate release content, checksums, and commands from an extracted ZIP."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--sandbox-check', action='store_true', help='Also execute a packaged existing-project check through the installed Codex sandbox')
args = parser.parse_args()

ROOT = Path(__file__).resolve().parents[1]
import runpy
VERSION = runpy.run_path(str(ROOT / 'src/context_loop/__init__.py'))['__version__']
DIST = ROOT / 'dist'
for line in (DIST / 'SHA256SUMS').read_text().splitlines():
    expected, name = line.split('  ', 1)
    assert hashlib.sha256((DIST / name).read_bytes()).hexdigest() == expected, name
with zipfile.ZipFile(DIST / f'context-loop-{VERSION}.zip') as archive:
    for name in archive.namelist():
        path = Path(name)
        assert not path.is_absolute() and '..' not in path.parts
        assert not set(path.parts) & {'.private', '.git', '.context-loop', '__pycache__'}
        assert path.name not in {'auth.json', 'token.json', '.env'}
    with tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve()) as directory:
        destination = Path(directory)
        archive.extractall(destination)
        release = destination / f'context-loop-{VERSION}'
        app = release / 'context-loop.pyz'
        with zipfile.ZipFile(app) as packaged:
            for name in packaged.namelist():
                if name.endswith('.py') and name != '__main__.py':
                    assert packaged.read(name) == (ROOT / 'src' / name).read_bytes(), name
        def run(*command_args, expect=0):
            result = subprocess.run([sys.executable, str(app), *command_args], capture_output=True, text=True, timeout=20)
            assert result.returncode == expect, result.stderr + result.stdout
            return result.stdout
        assert all(name in run('--help') for name in ['doctor','attach','inspect','approve'])
        project = destination / 'new-demo'
        run('init', str(project), '--demo')
        assert json.loads(run('status', str(project)))['status'] == 'ready'
        run('stop', str(project))
        assert (project / '.context-loop/stop').exists()
        assert (release / 'README.md').is_file()
        existing = destination / 'existing-project'
        (existing / 'src').mkdir(parents=True)
        files = {'AGENTS.md': '# Instructions\nChange only approved source code. Preserve documents.\n',
                 'Build.md': '# Build roadmap\nR1: Create a greeting containing exactly Context Loop.\n',
                 'Decisions.md': '# Decisions\nUse standard-library Python only. No external actions.\n',
                 'Status.md': '# Status\nThe greeting feature is pending.\n'}
        for name, text in files.items():
            (existing / name).write_text(text)
        before = {name: (existing / name).read_bytes() for name in files}
        assert 'Build.md' in run('inspect', str(existing))
        run('attach', str(existing), '--source', 'build:roadmap:Build.md', '--source', 'decisions:decisions:Decisions.md', '--source', 'status:status:Status.md', '--write-path', 'src')
        for name, content in before.items():
            assert (existing / name).read_bytes() == content
        config_path = existing / 'context-loop.json'
        config = json.loads(config_path.read_text())
        config['context']['requirements'] = {'R1': {'source': 'build', 'quote': 'Create a greeting containing exactly Context Loop.'}}
        config['tasks'] = [{'id': 'greeting', 'description': 'Create the documented greeting in src/greeting.txt only.', 'requirements': ['R1'], 'checks': [['{python}', '-B', '{control}/checks/check.py']]}]
        config_path.write_text(json.dumps(config))
        (existing / 'Context Loop/checks/check.py').write_text('from pathlib import Path\nassert Path("src/greeting.txt").read_text() == "Context Loop"\nprint("PASS: packaged acceptance")\n')
        run('approve', str(existing), '--note', 'Release fixture owner approves the mapped build and checks')
        assert json.loads(run('status', str(existing)))['status'] == 'ready'
        if args.sandbox_check:
            (existing / 'src/greeting.txt').write_text('Context Loop')
            checked = run('check', str(existing))
            assert 'checks_passed' in checked
        run('stop', str(existing))
print('PASS: checksums, sanitized ZIP, exact packaged source, extracted managed CLI and existing-project inspect/attach/approve/status/stop' + ('/sandboxed-check' if args.sandbox_check else ''))
