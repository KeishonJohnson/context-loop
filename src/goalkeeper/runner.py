"""One task per fresh turn; independent checks own completion."""
import json
import os
import shutil
import signal
import time
import uuid
from .config import load, fingerprint, argv
from .storage import GoalkeeperError, runtime, lock, read_json, initial_state, save_state, event, write_json, atomic_text
from .transport import SCHEMA, agent_command, check_command, execute, report

class Runner:
    def __init__(self, project, codex=None, executor=execute, sandbox=True):
        self.root, self.config = load(project)
        self.codex = codex or shutil.which("codex")
        if not self.codex:
            raise GoalkeeperError("Install Codex CLI and run codex login first")
        self.executor, self.sandbox = executor, sandbox
        self.rt = runtime(self.root)
        self.stopping = False

    def changed(self):
        return fingerprint(self.root) != self.contract

    def should_stop(self):
        return self.stopping or (self.rt / "stop").exists() or time.monotonic() >= self.deadline

    def child(self, pid):
        self.state["child_pid"] = pid
        save_state(self.root, self.state, self.config)

    def command(self, command, timeout, prompt=None):
        if (self.root / "workspace" / ".codex").exists():
            raise GoalkeeperError("Workspace .codex configuration is not allowed; owner review required")
        if self.changed():
            raise GoalkeeperError("Owner contract changed during run; restart after review")
        self.seq += 1
        log = self.run_dir / f"{self.seq:04d}.log"
        result = self.executor(command, self.root / "workspace", log, min(timeout, max(.01, self.deadline - time.monotonic())), self.config["limits"]["max_log_bytes"], self.should_stop, self.child, prompt)
        if self.changed():
            raise GoalkeeperError("Owner contract changed during run; acceptance rejected")
        if result["reason"]:
            raise GoalkeeperError("Process stopped: " + result["reason"])
        return result, log

    def checks(self, task):
        results = []
        for check in task["checks"]:
            command = argv(check, self.root)
            wrapped = check_command(self.codex, self.root, command) if self.sandbox else command
            outcome, log = self.command(wrapped, self.config["limits"]["check_timeout_seconds"])
            text = log.read_text(errors="replace")
            results.append({"status": "passed" if outcome["returncode"] == 0 else "failed", "command_display": " ".join(command), "summary": text[-1000:].strip().replace("\n", " "), "log": str(log.relative_to(self.root))})
        passed = all(c["status"] == "passed" for c in results)
        self.state["tasks"][task["id"]] = {"status": "passed" if passed else "pending", "checks": results}
        save_state(self.root, self.state, self.config)
        return passed

    def prompt(self, task):
        parts = ["Complete this single assigned task within the writable workspace. Other tasks are not assigned. The runner independently checks acceptance; never edit owner files or checks. No network, publishing, installations, other agents, or external actions. If blocked, say so. Record useful discoveries in workspace NOTES.md. Return the specified JSON summary."]
        for name in ("Goal.md", "Constraints.md", "Decisions.md"):
            parts += [f"\nOWNER {name}:\n" + (self.root / name).read_text()[:30_000]]
        parts += ["\nTASK:\n" + json.dumps(task), "\nPREVIOUS CHECK EVIDENCE:\n" + json.dumps(self.state["tasks"][task["id"]]), "\nRECENT PROGRESS:\n" + json.dumps(self.state["history"][-8:])]
        return "\n".join(parts)

    def run(self, check_only=False):
        with lock(self.root):
            path = self.rt / "state.json"
            self.state = read_json(path) if path.exists() else initial_state(self.config)
            child = self.state.get("child_pid")
            if child:
                try:
                    os.kill(child, 0)
                except ProcessLookupError:
                    pass
                else:
                    raise GoalkeeperError("Prior child PID is still alive; inspect it before restarting. No process was killed.")
            for task in self.config["tasks"]:
                self.state["tasks"].setdefault(task["id"], {"status": "pending", "checks": []})
            self.contract = fingerprint(self.root)
            self.deadline = time.monotonic() + self.config["limits"]["max_runtime_seconds"]
            self.run_dir = self.rt / "runs" / uuid.uuid4().hex
            self.run_dir.mkdir(parents=True, mode=0o700)
            self.seq = 0
            (self.rt / "stop").unlink(missing_ok=True)
            self.state.update(status="running", reason="Checking current workspace", runner_pid=os.getpid(), child_pid=None)
            event(self.state, "Started fresh run; prior results will be revalidated")
            old_handlers = {}
            if __import__("threading").current_thread() is __import__("threading").main_thread():
                for sig in (signal.SIGINT, signal.SIGTERM):
                    old_handlers[sig] = signal.signal(sig, lambda *_: setattr(self, "stopping", True))
            failures = 0
            turns = 0
            token_start = self.state["reported_tokens"]
            try:
                while True:
                    if self.should_stop():
                        self.state.update(status="stopped", reason="Stop requested or runtime limit reached")
                        break
                    pending = [task for task in self.config["tasks"] if not self.checks(task)]
                    if not pending:
                        self.state.update(status="complete", reason="Every independent check passed against the final workspace")
                        break
                    if check_only:
                        self.state.update(status="checks_failed", reason="Independent acceptance checks failed")
                        break
                    limits = self.config["limits"]
                    if turns >= limits["max_iterations"] or self.state["reported_tokens"] - token_start >= limits["max_reported_tokens"]:
                        self.state.update(status="limit_reached", reason="Iteration or reported-token limit reached; resume explicitly")
                        break
                    task = pending[0]
                    turns += 1
                    self.state["iterations"] += 1
                    event(self.state, f"Iteration {self.state['iterations']}: {task['id']}")
                    schema = self.run_dir / "schema.json"
                    output = self.run_dir / f"turn-{turns}.json"
                    write_json(schema, SCHEMA)
                    outcome, log = self.command(agent_command(self.codex, self.root, schema, output), limits["iteration_timeout_seconds"], self.prompt(task))
                    try:
                        summary, tokens = report(output, log)
                        self.state["reported_tokens"] += tokens
                        if outcome["returncode"]:
                            raise GoalkeeperError("Codex exited unsuccessfully")
                    except GoalkeeperError as exc:
                        failures += 1
                        event(self.state, str(exc))
                    else:
                        event(self.state, summary["summary"][:1500])
                        if summary["status"] in ("blocked", "needs_approval"):
                            self.state.update(status=summary["status"], reason=summary["summary"][:1500])
                            break
                        if self.checks(task):
                            failures = 0
                        else:
                            failures += 1
                    if failures >= limits["max_consecutive_failures"]:
                        self.state.update(status="blocked", reason="Consecutive unsuccessful iterations reached configured limit")
                        break
            except (GoalkeeperError, OSError) as exc:
                self.state.update(status="stopped" if self.should_stop() else "error", reason=str(exc))
            finally:
                for sig, handler in old_handlers.items():
                    signal.signal(sig, handler)
                self.state.update(runner_pid=None, child_pid=None)
                event(self.state, self.state["status"] + ": " + self.state["reason"])
                save_state(self.root, self.state, self.config)
            return self.state
