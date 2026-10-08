"""Disposable project and Obsidian fixtures; contains no user project data."""
from pathlib import Path
import json
import subprocess
from context_loop.adopt import attach, approve
from context_loop.storage import read_json, write_json

GOOD = '''def greet(name):
    if not isinstance(name, str): raise TypeError("name must be text")
    if not name: raise ValueError("name must not be empty")
    return f"Hello, {name}!"
'''
CHECK = '''import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("demo_app", Path("src/app.py"))
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
assert app.greet("Ada") == "Hello, Ada!"
assert app.greet("Bob") == "Hello, Bob!"
try:
    app.greet("")
except ValueError:
    pass
else:
    raise AssertionError("Empty names must be rejected")
print("PASS: governed greeting behavior and empty-name rejection")
'''


def make(base, git=False, approved=True):
    root = base / 'repo'
    vault = base / 'vault'
    (root / 'src').mkdir(parents=True)
    (root / 'docs').mkdir()
    vault.mkdir()
    files = {
        'AGENTS.md': '# Project instructions\nWork only on the approved greeting task in src/app.py. Preserve build docs, decisions and current status. No network, deployment, trading, messages, installs, or changes to Git metadata.\n',
        'src/AGENTS.md': '# Source guidance\nUse Python standard-library code and preserve the greet(name) public interface.\n',
        'src/Policy.md': '# Coding decisions\nNo external dependencies. Preserve governing source documents.\n',
        'src/app.py': 'def greet(name):\n    raise NotImplementedError("approved feature is pending")\n',
        'docs/Build.md': '# Build roadmap\nR1: Return exactly Hello, <name>! for each nonempty name.\nR2: Reject an empty name with ValueError.\nScope: implement this milestone in src/app.py only.\n',
        'docs/Decisions.md': '# Decisions and constraints\nUse Python and no external dependencies. No network, external actions, publishing or extra features. Do not change the project layout.\n',
        'docs/Status.md': '# Current status\nThe greeting feature is pending. The next approved milestone is R1 and R2. No unrelated work is approved.\n',
        'README.md': '# Existing project\nThis original documentation must remain unchanged.\n',
        'Progress.md': '# Original progress\nThis owner status note must never be overwritten.\n',
        'Tasks.md': '# Original tasks\nOriginal task board retained.\n',
        '.gitignore': '__pycache__/\n',
    }
    for name, content in files.items(): (root / name).write_text(content)
    (vault / 'Project Index.md').write_text('# Project index\n[[Guidance]]\n[[Unused]]\n')
    (vault / 'Guidance.md').write_text('# Supporting guidance\nFollow the approved greeting scope; keep validation independent.\n[[Examples]]\n')
    (vault / 'Examples.md').write_text('# Examples\nAda should receive Hello, Ada!\n')
    (vault / 'Unused.md').write_text('# Unrelated research\nUNRELATED_NOTE_MUST_NOT_ENTER_TASK_CONTEXT\n')
    if git:
        subprocess.run(['git', 'init', '-b', 'main', str(root)], capture_output=True, check=True)
        subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(root), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'Frozen fixture baseline'], capture_output=True, check=True)
    originals = {name: (root / name).read_bytes() for name in files}
    attach(root, ['roadmap:roadmap:docs/Build.md', 'decisions:decisions:docs/Decisions.md', 'status:status:docs/Status.md', 'coding-policy:decisions:src/Policy.md'], ['src'], [str(vault / 'Project Index.md')], [str(vault)])
    config = read_json(root / 'context-loop.json')
    config['context']['requirements'] = {
        'R1': {'source': 'roadmap', 'quote': 'Return exactly Hello, <name>! for each nonempty name.'},
        'R2': {'source': 'roadmap', 'quote': 'Reject an empty name with ValueError.'},
    }
    config['tasks'] = [{'id': 'greeting', 'description': 'Implement the documented greet(name) behavior in src/app.py only. Preserve the approved scope and all original governing documents.', 'requirements': ['R1', 'R2'], 'notes': ['Guidance'], 'checks': [['{python}', '-B', '{control}/checks/acceptance.py']]}]
    write_json(root / 'context-loop.json', config)
    (root / 'Context Loop/checks/acceptance.py').write_text(CHECK)
    if approved:
        approve(root, 'Fixture owner approves source mapping, exact requirements, src write scope and independent checks')
    return root, vault, originals
