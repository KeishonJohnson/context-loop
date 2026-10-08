"""Validate the owner contract before starting any process."""
import hashlib
import json
import re
import sys
from pathlib import Path
from .storage import GoalkeeperError, read_json

LIMITS = {"max_iterations", "max_runtime_seconds", "iteration_timeout_seconds", "check_timeout_seconds", "max_consecutive_failures", "max_log_bytes", "max_reported_tokens"}

def load(root):
    root = Path(root).absolute()
    if root.resolve() != root:
        raise GoalkeeperError("Project path must not contain symlinks")
    for path in root.rglob("*"):
        if path.is_symlink() and "workspace" not in path.relative_to(root).parts:
            raise GoalkeeperError(f"Control path must not be a symlink: {path}")
    config = read_json(root / "goalkeeper.json")
    if config.get("version") != 1 or config.get("workspace") != "workspace":
        raise GoalkeeperError("Expected version 1 and workspace='workspace'")
    if not (root / "workspace").is_dir() or (root / "workspace").is_symlink():
        raise GoalkeeperError("workspace must be a real directory")
    limits = config.get("limits", {})
    if set(limits) != LIMITS or any(type(v) is not int or v <= 0 for v in limits.values()):
        raise GoalkeeperError("All seven limits must be positive integers")
    tasks = config.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise GoalkeeperError("Define at least one task")
    seen = set()
    for task in tasks:
        ident = task.get("id", "")
        if not isinstance(ident, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", ident) or ident in seen:
            raise GoalkeeperError("Task IDs must be unique safe identifiers")
        seen.add(ident)
        if not isinstance(task.get("description"), str) or not task["description"].strip():
            raise GoalkeeperError("Every task needs a description")
        checks = task.get("checks")
        if not isinstance(checks, list) or not checks:
            raise GoalkeeperError(f"Define independent checks for {ident} before running")
        for check in checks:
            if not isinstance(check, list) or not check or any(not isinstance(a, str) or not a for a in check):
                raise GoalkeeperError("Checks must be nonempty argv arrays")
    for name in ("Goal.md", "Constraints.md", "Decisions.md"):
        if not (root / name).is_file():
            raise GoalkeeperError(f"Missing {name}")
    return root, config

def fingerprint(root):
    digest = hashlib.sha256()
    paths = [root / name for name in ("goalkeeper.json", "Goal.md", "Constraints.md", "Decisions.md")]
    if (root / "checks").exists():
        paths += sorted(p for p in (root / "checks").rglob("*") if p.is_file())
    for path in paths:
        if path.is_symlink():
            raise GoalkeeperError("Contract symlink detected")
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()

def argv(check, root):
    return [a.replace("{python}", sys.executable).replace("{project}", str(root)).replace("{workspace}", str(root / "workspace")) for a in check]
