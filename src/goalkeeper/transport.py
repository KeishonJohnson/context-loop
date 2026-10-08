"""Codex CLI adapter and bounded subprocess supervision; never invoke a shell."""
import json
import os
import signal
import subprocess
import time
from pathlib import Path
from .storage import GoalkeeperError

SCHEMA = {"type": "object", "properties": {"status": {"type": "string", "enum": ["done", "continue", "blocked", "needs_approval"]}, "summary": {"type": "string"}}, "required": ["status", "summary"], "additionalProperties": False}

def profile(root, name, writable=False):
    filesystem = ('filesystem={' + json.dumps(str(root / "workspace")) + '="write"},') if writable else ''
    value = 'permissions={' + name + '={extends=":read-only",' + filesystem + 'network={enabled=false}}}'
    return ["-c", value]

def check_command(codex, root, command):
    return [codex, "sandbox", "-P", "goalkeeper-check", "-C", str(root / "workspace"), *profile(root, "goalkeeper-check"), "--", *command]

def agent_command(codex, root, schema, output):
    return [codex, "-a", "never", "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral", "--skip-git-repo-check", "--json", "-C", str(root / "workspace"), *profile(root, "goalkeeper", True), "-c", 'default_permissions="goalkeeper"', "--output-schema", str(schema), "-o", str(output), "-"]

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

def report(output, log):
    if not output.is_file() or output.stat().st_size > 100_000:
        raise GoalkeeperError("Missing or oversized agent summary")
    try:
        value = json.loads(output.read_text())
    except ValueError as exc:
        raise GoalkeeperError("Malformed agent JSON summary") from exc
    if not isinstance(value, dict) or set(value) != {"status", "summary"} or value["status"] not in SCHEMA["properties"]["status"]["enum"] or not isinstance(value["summary"], str):
        raise GoalkeeperError("Agent summary does not match schema")
    tokens = 0
    for line in log.read_text(errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "turn.completed":
            usage = event.get("usage", {})
            tokens += sum(max(0, v) for k in ("input_tokens", "output_tokens") if type(v := usage.get(k, 0)) is int)
    return value, tokens
