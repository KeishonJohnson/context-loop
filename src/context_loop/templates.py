"""Owner-facing starter files; no private data or article copies."""

import sys


DEMO_FUNCTION_CHECK = '''import importlib.util
from pathlib import Path
import sys

module_path = Path.cwd() / "slugify.py"
assert module_path.is_file(), "Create workspace/slugify.py"
spec = importlib.util.spec_from_file_location("demo_slugify", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
cases = {
    "Hello, World!": "hello-world",
    "  Multiple   spaces ": "multiple-spaces",
    "Café déjà vu": "cafe-deja-vu",
    "___Hello---World___": "hello-world",
    "!!!": "",
    "ABC 123": "abc-123",
}
for source, expected in cases.items():
    assert module.slugify(source) == expected, (source, module.slugify(source), expected)
try:
    module.slugify(None)
except TypeError:
    pass
else:
    raise AssertionError("slugify must reject non-string input with TypeError")
print("PASS: 6 behavioral cases and non-string rejection")
'''

DEMO_CLI_CHECK = '''import subprocess
import sys
from pathlib import Path

assert Path("slugify.py").is_file(), "slugify.py is missing"
for source, expected in [("Hello, World!", "hello-world"), ("Café déjà vu", "cafe-deja-vu")]:
    result = subprocess.run([sys.executable, "-B", "slugify.py", source],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert result.stdout == expected + "\\n", repr(result.stdout)
assert Path("README.md").is_file(), "Document the function and CLI in workspace/README.md"
text = Path("README.md").read_text().lower()
assert "slugify" in text and "python" in text, "README must describe use"
print("PASS: CLI output and usage documentation")
'''


def starter(demo: bool) -> tuple[dict, dict[str, str]]:
    config = {
        "version": 1,
        "workspace": "workspace",
        "limits": {
            "max_iterations": 10,
            "max_runtime_seconds": 1800,
            "iteration_timeout_seconds": 300,
            "check_timeout_seconds": 30,
            "max_consecutive_failures": 3,
            "max_log_bytes": 4_000_000,
            "max_reported_tokens": 200_000,
        },
        "tasks": [],
    }
    files = {
        "Goal.md": "# Goal\n\nDescribe the intended outcome and observable definition of done.\n",
        "Constraints.md": "# Constraints\n\n- Work only inside workspace/.\n- No credentials, external messages, deployments, or financial actions.\n- Do not change the goal, task contract, or acceptance checks.\n- If required access or a decision is missing, report blocked.\n",
        "Decisions.md": "# Decisions\n\nRecord owner decisions and their reasons here before a run.\n",
        "Index.md": "# Project index\n\n- [[Goal]]: intended outcome.\n- [[Constraints]]: boundaries.\n- [[Decisions]]: owner decisions and reasons.\n- [[Tasks]]: runner-generated acceptance status.\n- [[Progress]]: runner-generated history, checks, and next action.\n\nCode lives in workspace/. The runner owns .context-loop/.\n",
        ".gitignore": ".context-loop/\n__pycache__/\n*.pyc\n.DS_Store\n",
        "workspace/AGENTS.md": "# Workspace execution\n\nRead the goal, constraints, and decisions supplied in each Context Loop prompt.\nImplement one assigned task per cycle. Inspect existing code before editing.\nWrite only inside this workspace. Do not modify ../context-loop.json, owner notes,\nacceptance checks, or runner state. Do not publish, install packages, send\nmessages, or invoke other agents. Return a truthful structured summary; the\nrunner determines completion independently. Record discoveries in NOTES.md.\n",
    }
    if demo:
        config["tasks"] = [
            {
                "id": "slugify-function",
                "description": "Implement slugify(text) in slugify.py: lowercase, normalize accented Latin characters using Unicode NFKD, keep ASCII letters/digits, replace runs of other characters with one hyphen, trim hyphens, and raise TypeError for non-string input. No external dependencies.",
                "checks": [["{python}", "-B", "{project}/checks/function_check.py"]],
            },
            {
                "id": "slugify-cli",
                "description": "Add a command-line entry point to slugify.py accepting one text argument and printing the slug plus newline; document function and CLI in README.md. Preserve the function behavior.",
                "checks": [["{python}", "-B", "{project}/checks/cli_check.py"]],
            },
        ]
        files.update({
            "Goal.md": "# Goal\n\nBuild a dependency-free Unicode-aware slugify function and command-line tool.\n\nDone means both independent acceptance scripts pass against the final workspace.\n",
            "Decisions.md": "# Decisions\n\n- Use Python standard-library unicodedata and regular expressions.\n- Checks live outside the writable workspace and must not change.\n- This is a disposable example, not a production project.\n",
            "checks/function_check.py": DEMO_FUNCTION_CHECK,
            "checks/cli_check.py": DEMO_CLI_CHECK,
        })
    else:
        config["tasks"] = [{
            "id": "first-task",
            "description": "Replace this task with the first concrete increment toward your goal.",
            "checks": [],
        }]
    return config, files

