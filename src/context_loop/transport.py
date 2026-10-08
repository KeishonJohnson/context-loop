"""Codex CLI adapter and bounded subprocess supervision; never invoke a shell."""
import json
import os
import signal
import subprocess
import time
from pathlib import Path
from .storage import ContextLoopError

SCHEMA = {"type": "object", "properties": {"status": {"type": "string", "enum": ["done", "continue", "blocked", "needs_approval"]}, "summary": {"type": "string"}}, "required": ["status", "summary"], "additionalProperties": False}

CITATIONS = {"type": "array", "items": {"type": "object", "properties": {"id": {"type": "string"}, "sha256": {"type": "string"}}, "required": ["id", "sha256"], "additionalProperties": False}}
AUDIT_SCHEMA = {"type": "object", "properties": {"status": {"type": "string", "enum": ["aligned", "conflict", "blocked"]}, "summary": {"type": "string"}, "sources": CITATIONS, "conflicts": {"type": "array", "items": {"type": "string"}}}, "required": ["status", "summary", "sources", "conflicts"], "additionalProperties": False}
EXISTING_SCHEMA = {"type": "object", "properties": {**SCHEMA["properties"], "requirement_ids": {"type": "array", "items": {"type": "string"}}, "sources": CITATIONS, "conflicts": {"type": "array", "items": {"type": "string"}}}, "required": ["status", "summary", "requirement_ids", "sources", "conflicts"], "additionalProperties": False}


def profile(root, name, writable=False, config=None):
    from .config import existing, workspace, validate_write_paths, protected_paths
    from .storage import read_json
    config = config or (read_json(root / "context-loop.json") if (root / "context-loop.json").exists() else {"version": 1})
    rules = {}
    if writable:
        paths = validate_write_paths(root, config) if existing(config) else [workspace(root, config)]
        rules.update({str(p): "write" for p in paths})
        rules.update({str(p): "read" for p in protected_paths(root, config)})
    filesystem = 'filesystem={' + ','.join(json.dumps(k) + '=' + json.dumps(v) for k, v in rules.items()) + '},' if rules else ''
    value = 'permissions={' + name + '={extends=":read-only",' + filesystem + 'network={enabled=false}}}'
    return ["-c", value]


def check_command(codex, root, command, config=None):
    from .config import workspace
    return [codex, "sandbox", "-P", "context-loop-check", "-C", str(workspace(root, config or {"version": 1})), *profile(root, "context-loop-check", config=config), "--", *command]


def agent_command(codex, root, schema, output, config=None, audit=False):
    from .config import workspace
    return [codex, "-a", "never", "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral", "--skip-git-repo-check", "--json", "-C", str(workspace(root, config or {"version": 1})), *profile(root, "context-loop", not audit, config), "-c", 'default_permissions="context-loop"', "--output-schema", str(schema), "-o", str(output), "-"]


def terminate(process):
    if process.poll() is not None:
        # A command can exit after starting background descendants in its group.
        # Clean up the group we created rather than leaving those workers behind.
        try:
            os.killpg(process.pid, signal.SIGTERM)
            time.sleep(.05)
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=3)
    except ProcessLookupError:
        pass

def execute(command, cwd, log, timeout, max_bytes, should_stop, on_child, prompt=None):
    start = time.monotonic()
    with log.open("wb") as stream:
        process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE if prompt is not None else subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        on_child(process.pid)
        reason = None
        try:
            if prompt is not None:
                process.stdin.write(prompt.encode())
                process.stdin.close()
            while process.poll() is None:
                if should_stop():
                    reason = "stopped"
                elif time.monotonic() - start >= timeout:
                    reason = "timeout"
                elif log.stat().st_size > max_bytes:
                    reason = "log_limit"
                if reason:
                    terminate(process)
                    break
                time.sleep(.05)
            if log.stat().st_size > max_bytes:
                reason = "log_limit"
        finally:
            terminate(process)
            on_child(None)
    return {"returncode": process.returncode, "reason": reason, "elapsed": round(time.monotonic() - start, 3)}

def report(output, log, schema=SCHEMA):
    if not output.is_file() or output.stat().st_size > 100_000:
        raise ContextLoopError("Missing or oversized agent summary")
    try:
        value = json.loads(output.read_text())
    except ValueError as exc:
        raise ContextLoopError("Malformed agent JSON summary") from exc
    if not isinstance(value, dict) or set(value) != set(schema["required"]) or value["status"] not in schema["properties"]["status"]["enum"] or not isinstance(value["summary"], str):
        raise ContextLoopError("Agent summary does not match schema")
    if schema is not SCHEMA:
        if not isinstance(value.get("conflicts"), list) or any(not isinstance(s, str) for s in value["conflicts"]):
            raise ContextLoopError("Malformed conflict report")
        if schema is EXISTING_SCHEMA and (not isinstance(value.get("requirement_ids"), list) or any(not isinstance(s, str) for s in value["requirement_ids"])):
            raise ContextLoopError("Malformed requirement citations")
    tokens = 0
    for line in log.read_text(errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "turn.completed":
            usage = event.get("usage", {})
            if not isinstance(usage, dict):
                continue
            tokens += sum(max(0, v) for k in ("input_tokens", "output_tokens") if type(v := usage.get(k, 0)) is int)
    return value, tokens
