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
from .adopt import inspect_project, attach, approve
from .config import load, existing, control, contract_digest
from .context import verify_approval


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
    for name in ("inspect", "approve", "attach"):
        cmd = sub.add_parser(name)
        cmd.add_argument("project")
        if name == "approve":
            cmd.add_argument("--note", required=True)
        if name == "attach":
            cmd.add_argument("--source", action="append", default=[])
            cmd.add_argument("--write-path", action="append", default=[])
            cmd.add_argument("--obsidian-index", action="append", default=[])
            cmd.add_argument("--obsidian-root", action="append", default=[])
    sub.add_parser("doctor")
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            print(json.dumps(inspect_project(args.project), indent=2))
            return 0
        if args.command == "attach":
            print(attach(args.project, args.source, args.write_path, args.obsidian_index, args.obsidian_root))
            print("Scaffold added; existing documents preserved. Configure and review before approve/run.")
            return 0
        if args.command == "approve":
            approved = approve(args.project, args.note)
            print(json.dumps({"approval": approved["id"], "digest": approved["digest"], "note": approved["note"]}, indent=2))
            return 0
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
            config = read_json(root / "context-loop.json")
            if existing(config):
                try:
                    load(root)
                    approved = verify_approval(root, contract_digest(root, config))
                    if state.get("context_violation") == approved["id"]:
                        raise ContextLoopError("Prior context violation requires owner review and fresh approval")
                except ContextLoopError as exc:
                    state = dict(state, status="context_unready", reason=str(exc))
        else:
            config = read_json(root / "context-loop.json")
            print(f"Running {args.command}; live evidence: {control(root, config) / 'Progress.md'}", flush=True)
            state = Runner(root).run(check_only=args.command == "check")
        print(json.dumps({k: state[k] for k in ("status", "reason", "iterations", "reported_tokens")}, indent=2))
        return 0 if state["status"] in ("ready", "complete", "checks_passed") else 1
    except (ContextLoopError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"Context Loop: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
