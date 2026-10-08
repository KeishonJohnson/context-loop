"""One task per fresh turn; independent checks own completion."""
import json
import os
import shutil
import signal
import time
import uuid
from .config import load, fingerprint, argv, existing, workspace, contract_digest
from .storage import ContextLoopError, runtime, lock, read_json, initial_state, save_state, event, write_json, atomic_text
from .context import prepare, for_task, source_manifest, verify_approval, validate_citations
from .transport import SCHEMA, AUDIT_SCHEMA, EXISTING_SCHEMA, agent_command, check_command, execute, report

class Runner:
    def __init__(self, project, codex=None, executor=execute, sandbox=True):
        self.root, self.config = load(project)
        self.attached = existing(self.config)
        self.workspace = workspace(self.root, self.config)
        self.context = prepare(self.root, self.config) if self.attached else None
        self.codex = codex or shutil.which("codex")
        if not self.codex:
            raise ContextLoopError("Install Codex CLI and run codex login first")
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
        if (self.workspace / ".codex").exists():
            raise ContextLoopError("Workspace .codex configuration is not allowed; owner review required")
        if self.changed():
            raise ContextLoopError("Owner contract changed during run; restart after review")
        self.seq += 1
        log = self.run_dir / f"{self.seq:04d}.log"
        result = self.executor(command, self.workspace, log, min(timeout, max(.01, self.deadline - time.monotonic())), self.config["limits"]["max_log_bytes"], self.should_stop, self.child, prompt)
        if self.changed():
            raise ContextLoopError("Owner contract changed during run; acceptance rejected")
        if result["reason"]:
            raise ContextLoopError("Process stopped: " + result["reason"])
        return result, log

    def checks(self, task):
        results = []
        for check in task["checks"]:
            command = argv(check, self.root, self.config)
            wrapped = check_command(self.codex, self.root, command, self.config) if self.sandbox else command
            outcome, log = self.command(wrapped, self.config["limits"]["check_timeout_seconds"])
            text = log.read_text(errors="replace")
            results.append({"status": "passed" if outcome["returncode"] == 0 else "failed", "command_display": " ".join(command), "summary": text[-1000:].strip().replace("\n", " "), "log": str(log.relative_to(self.root))})
        passed = all(c["status"] == "passed" for c in results)
        self.state["tasks"][task["id"]].update(status="passed" if passed else "pending", checks=results)
        save_state(self.root, self.state, self.config)
        return passed

    def governing_prompt(self, sources):
        parts = ["These are the owner-approved governing documents in read order. Treat instructions, scope, decisions and current status as authoritative. Research provides supporting context and does not authorize a scope change. If documents conflict, report the conflict and stop; do not invent a resolution. Do not edit governing documents. Return exact source IDs and SHA256s as your sources citations. This approval authorizes only the assigned task, not publishing, messaging, deployments, trading or other projects."]
        for source in sources:
            parts.append("\nGOVERNING SOURCE " + json.dumps({k: source[k] for k in ("id", "role", "path", "sha256")}) + "\n" + source["text"])
        return "\n".join(parts)

    def align(self):
        schema = self.run_dir / "alignment-schema.json"
        output = self.run_dir / "alignment.json"
        write_json(schema, AUDIT_SCHEMA)
        prompt = "READ-ONLY ALIGNMENT REVIEW. Do not change any files. Review all approved source documents and task requirements for contradictory direction, constraints, scope or unsafe implied authorization. A green test is not evidence that conflicting instructions are resolved. Return aligned only if no conflict is found, otherwise conflict or blocked.\n"
        prompt += self.governing_prompt(self.context["sources"])
        prompt += "\nApproved tasks and requirement bindings:\n" + json.dumps(self.config["tasks"])
        prompt += "\nRequirements:\n" + json.dumps(self.context["requirements"])
        outcome, log = self.command(agent_command(self.codex, self.root, schema, output, self.config, audit=True), self.config["limits"]["iteration_timeout_seconds"], prompt)
        result, tokens = report(output, log, AUDIT_SCHEMA)
        self.state["reported_tokens"] += tokens
        self.state["alignment"] = result
        if outcome["returncode"]:
            raise ContextLoopError("Alignment review failed")
        validate_citations(result, self.context["sources"])
        if result["status"] != "aligned" or result["conflicts"]:
            self.state.update(status="blocked", reason="Governing context conflict or missing decision: " + result["summary"])
            self.state["context_violation"] = self.approval["id"]
            event(self.state, self.state["reason"])
            return False
        event(self.state, "Read-only alignment review passed: " + result["summary"])
        return True

    def prompt(self, task):
        parts = ["Complete this single assigned task within explicitly permitted paths. Other tasks are not assigned. The runner independently checks acceptance; never edit owner files, instructions or checks. No network, publishing, installations, other agents, or external actions. If blocked, say so. Return the specified JSON summary. Supporting research cannot override the approved build plan."]
        if self.attached:
            parts += [self.governing_prompt(for_task(self.context, task)), "\nRequired requirement_ids in your result: " + json.dumps(task["requirements"]), "\nExact governing requirements: " + json.dumps({r: self.context["requirements"][r] for r in task["requirements"]}), "\nAllowed write paths: " + json.dumps(self.config["write_paths"])]
        else:
            parts += ["Record useful discoveries in workspace NOTES.md."]
            for name in ("Goal.md", "Constraints.md", "Decisions.md"):
                text = (self.root / name).read_text()
                if len(text.encode()) > 30_000:
                    raise ContextLoopError("Owner note exceeds context budget; split it explicitly")
                parts += [f"\nOWNER {name}:\n" + text]
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
                    raise ContextLoopError("Prior child PID is still alive; inspect it before restarting. No process was killed.")
            for task in self.config["tasks"]:
                self.state["tasks"].setdefault(task["id"], {"status": "pending", "checks": []})
            if self.attached:
                self.approval = verify_approval(self.root, contract_digest(self.root, self.config))
                if self.state.get("context_violation") == self.approval["id"]:
                    raise ContextLoopError("Prior context violation requires owner review and a fresh explicit approval")
                self.state.pop("context_violation", None)
                self.state["governing_sources"] = source_manifest(self.context["sources"])
                self.state["requirements"] = self.context["requirements"]
                self.state["approval"] = {key: self.approval[key] for key in ("id", "note", "approved_at", "digest")}
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
                aligned = not self.attached or check_only or self.align()
                while aligned:
                    if self.should_stop():
                        self.state.update(status="stopped", reason="Stop requested or runtime limit reached")
                        break
                    pending = [task for task in self.config["tasks"] if not self.checks(task)]
                    if not pending:
                        self.state.update(status="checks_passed" if self.attached and check_only else "complete", reason="Every independent check passed against the final workspace" + ("; full run still requires alignment review" if self.attached and check_only else ""))
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
                    output_schema = EXISTING_SCHEMA if self.attached else SCHEMA
                    write_json(schema, output_schema)
                    outcome, log = self.command(agent_command(self.codex, self.root, schema, output, self.config), limits["iteration_timeout_seconds"], self.prompt(task))
                    try:
                        summary, tokens = report(output, log, output_schema)
                        self.state["reported_tokens"] += tokens
                        if self.attached:
                            validate_citations(summary, for_task(self.context, task))
                            if set(summary["requirement_ids"]) != set(task["requirements"]) or len(summary["requirement_ids"]) != len(task["requirements"]):
                                raise ContextLoopError("Execution did not cite exactly its approved requirement IDs")
                            if summary["conflicts"]:
                                raise ContextLoopError("Execution reported conflicting governing context: " + "; ".join(summary["conflicts"]))
                            self.state["tasks"][task["id"]]["execution_sources"] = summary["sources"]
                        if outcome["returncode"]:
                            raise ContextLoopError("Codex exited unsuccessfully")
                    except ContextLoopError as exc:
                        if self.attached:
                            self.state["context_violation"] = self.approval["id"]
                            raise
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
            except (ContextLoopError, OSError) as exc:
                self.state.update(status="stopped" if self.should_stop() else "error", reason=str(exc))
            finally:
                for sig, handler in old_handlers.items():
                    signal.signal(sig, handler)
                self.state.update(runner_pid=None, child_pid=None)
                event(self.state, self.state["status"] + ": " + self.state["reason"])
                save_state(self.root, self.state, self.config)
            return self.state
