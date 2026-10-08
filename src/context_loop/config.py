"""Validate owner contracts for managed and attached projects."""
import hashlib
import json
import re
import sys
from pathlib import Path
from .storage import ContextLoopError, read_json
from .context import CONTROL, prepare, safe_path, source_manifest, instruction_paths

LIMITS = {"max_iterations", "max_runtime_seconds", "iteration_timeout_seconds", "check_timeout_seconds", "max_consecutive_failures", "max_log_bytes", "max_reported_tokens"}


def existing(config):
    return config.get("version") == 2 and config.get("mode") == "existing"


def workspace(root, config):
    return root if existing(config) else root / "workspace"


def control(root, config):
    return root / CONTROL if existing(config) else root


def validate_write_paths(root, config):
    values = config.get("write_paths")
    if not isinstance(values, list) or not values:
        raise ContextLoopError("Existing projects need explicit write_paths before running")
    reserved = {".git", ".codex", ".context-loop", CONTROL, "context-loop.json", "AGENTS.md", "CLAUDE.md", "AGENTS.override.md"}
    result = []
    for value in values:
        if not isinstance(value, str):
            raise ContextLoopError("write_paths must contain relative path strings")
        raw = Path(value)
        if raw.is_absolute() or str(raw) == "." or ".." in raw.parts or raw.parts[0].casefold() in {s.casefold() for s in reserved}:
            raise ContextLoopError("write_paths may not include the project root or control/instruction paths")
        path = safe_path(root / raw)
        if root not in path.parents:
            raise ContextLoopError("Writable path escaped project")
        if path.is_file() and path.name in ("AGENTS.md", "CLAUDE.md", "AGENTS.override.md"):
            raise ContextLoopError("Instruction files cannot be writable")
        result.append(path)
    return result


def load(root):
    root = safe_path(root)
    config = read_json(root / "context-loop.json")
    attached = existing(config)
    if not attached and (config.get("version") != 1 or config.get("workspace") != "workspace"):
        raise ContextLoopError("Expected managed version 1, or version 2 mode='existing'")
    if attached and config.get("workspace") != ".":
        raise ContextLoopError("Existing mode uses the unchanged project root")
    owned = [root / "context-loop.json", root / ".context-loop", control(root, config)]
    for path in owned:
        if path.is_symlink():
            raise ContextLoopError(f"Control path must not be a symlink: {path}")
    if (root / ".context-loop").exists():
        for path in (root / ".context-loop").rglob("*"):
            if path.is_symlink():
                raise ContextLoopError(f"Runtime path must not be a symlink: {path}")
    scan = control(root, config)
    for path in scan.rglob("*"):
        if attached or "workspace" not in path.relative_to(root).parts:
            if path.is_symlink():
                raise ContextLoopError(f"Control path must not be a symlink: {path}")
    target = workspace(root, config)
    if not target.is_dir() or target.is_symlink():
        raise ContextLoopError("Workspace must be a real directory")
    if attached:
        validate_write_paths(root, config)
    limits = config.get("limits", {})
    if not isinstance(limits, dict) or set(limits) != LIMITS or any(type(v) is not int or v <= 0 for v in limits.values()):
        raise ContextLoopError("All seven limits must be positive integers")
    tasks = config.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ContextLoopError("Define at least one task")
    seen = set()
    for task in tasks:
        if not isinstance(task, dict):
            raise ContextLoopError("Task definitions must be objects")
        ident = task.get("id", "")
        if not isinstance(ident, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", ident) or ident in seen:
            raise ContextLoopError("Task IDs must be unique safe identifiers")
        seen.add(ident)
        if not isinstance(task.get("description"), str) or not task["description"].strip():
            raise ContextLoopError("Every task needs a description")
        checks = task.get("checks")
        if not isinstance(checks, list) or not checks:
            raise ContextLoopError(f"Define independent checks for {ident} before running")
        for check in checks:
            if not isinstance(check, list) or not check or any(not isinstance(a, str) or not a for a in check):
                raise ContextLoopError("Checks must be nonempty argv arrays")
    if attached:
        prepare(root, config)
    else:
        for name in ("Goal.md", "Constraints.md", "Decisions.md"):
            if not (root / name).is_file():
                raise ContextLoopError(f"Missing {name}")
    return root, config


def contract_digest(root, config=None):
    config = config or read_json(root / "context-loop.json")
    digest = hashlib.sha256()
    paths = [root / "context-loop.json"]
    if existing(config):
        context = prepare(root, config)
        digest.update(json.dumps(source_manifest(context["sources"]), sort_keys=True).encode())
        digest.update(json.dumps(context["catalog"], sort_keys=True).encode())
        generated = {root / CONTROL / name for name in ("Approval.json", "Tasks.md", "Progress.md", "Index.md")}
        paths += [p for p in (root / CONTROL).rglob("*") if p.is_file() and p not in generated]
    else:
        paths += [root / name for name in ("Goal.md", "Constraints.md", "Decisions.md")]
        if (root / "checks").exists():
            paths += [p for p in (root / "checks").rglob("*") if p.is_file()]
    for path in sorted(paths):
        safe_path(path)
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def fingerprint(root):
    config = read_json(root / "context-loop.json")
    value = contract_digest(root, config)
    if existing(config):
        approval = root / CONTROL / "Approval.json"
        safe_path(approval)
        value += approval.read_text() if approval.exists() else "unapproved"
    return hashlib.sha256(value.encode()).hexdigest()


def protected_paths(root, config):
    if not existing(config):
        return []
    context = prepare(root, config)
    paths = [root / "context-loop.json", root / CONTROL, root / ".context-loop", root / ".git", root / ".codex"]
    paths += [Path(s["path"]) for s in context["sources"]]
    paths += instruction_paths(root, config["write_paths"])
    # Protect instruction/config metadata even if created below an allowed dir.
    for allowed in validate_write_paths(root, config):
        if allowed.is_dir():
            for folder in [allowed, *[p for p in allowed.rglob("*") if p.is_dir() and not p.is_symlink()]]:
                paths += [folder / name for name in ("AGENTS.md", "CLAUDE.md", "AGENTS.override.md", ".codex", ".git")]
    return sorted(set(paths))


def argv(check, root, config=None):
    target = workspace(root, config or read_json(root / "context-loop.json"))
    return [a.replace("{python}", sys.executable).replace("{project}", str(root)).replace("{workspace}", str(target)).replace("{control}", str(control(root, config or read_json(root / "context-loop.json")))) for a in check]
