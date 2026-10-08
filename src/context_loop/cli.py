"""Context Loop command line."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from .storage import ContextLoopError, atomic_text, write_json, initial_state, save_state, read_json, runtime
from .templates import starter
from .runner import Runner


def init_project(path, demo=False):
    root = Path(path).absolute()
    if root.exists():
        raise ContextLoopError("Refusing existing path; choose a new project folder")
    if root.parent.resolve() != root.parent:
        raise ContextLoopError("Parent must not contain symlinks")
    config, files = starter(demo)
    root.mkdir(parents=True)
    for relative, content in files.items():
        atomic_text(root / relative, content)
    write_json(root / "context-loop.json", config)
    save_state(root, initial_state(config), config)
    return root


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bounded, independently verified Codex execution loops")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("project")
    init.add_argument("--demo", action="store_true")
    for name in ("run", "check", "status", "stop"):
        cmd = sub.add_parser(name)
        cmd.add_argument("project")
    sub.add_parser("doctor")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            print(init_project(args.project, args.demo))
            return 0
        if args.command == "doctor":
            codex = shutil.which("codex")
            print(f"Python: {sys.version.split()[0]} | Codex: {codex or 'missing'}")
            if not codex:
                return 1
            result = subprocess.run([codex, "login", "status"], capture_output=True, text=True, timeout=15)
            print((result.stdout + result.stderr).strip())
            return result.returncode
        root = Path(args.project).absolute()
        if args.command == "stop":
            if not (root / "context-loop.json").is_file():
                raise ContextLoopError("Not a managed project")
            atomic_text(runtime(root) / "stop", "stop requested\n")
            print("Stop requested; the runner will terminate its active child")
            return 0
        if args.command == "status":
            state = read_json(root / ".context-loop" / "state.json")
        else:
            print(f"Running {args.command}; live evidence: {root / 'Progress.md'}", flush=True)
            state = Runner(root).run(check_only=args.command == "check")
        print(json.dumps({k: state[k] for k in ("status", "reason", "iterations", "reported_tokens")}, indent=2))
        return 0 if state["status"] in ("ready", "complete") else 1
    except (ContextLoopError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"Context Loop: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
