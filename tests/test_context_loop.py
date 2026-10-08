import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from context_loop.cli import init_project, main
from context_loop.config import load, fingerprint
from context_loop.runner import Runner
from context_loop.storage import ContextLoopError, lock, read_json, write_json
from context_loop.transport import execute, agent_command, profile, report

GOOD = '''import re, unicodedata, sys
def slugify(text):
    if not isinstance(text, str): raise TypeError("text must be a string")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub("[^a-z0-9]+", "-", text).strip("-")
if __name__ == "__main__": print(slugify(sys.argv[1]))
'''

class Harness:
    def __init__(self, behavior="success"):
        self.calls = 0
        self.behavior = behavior
    def __call__(self, command, cwd, log, timeout, max_bytes, should_stop, on_child, prompt=None):
        if prompt is None:
            return execute(command, cwd, log, timeout, max_bytes, should_stop, on_child)
        self.calls += 1
        output = Path(command[command.index("-o") + 1])
        if self.behavior in ("success", "regression"):
            (cwd / "slugify.py").write_text(GOOD)
            if self.calls >= 2:
                (cwd / "README.md").write_text("Use python slugify.py text; import slugify.")
            if self.behavior == "regression" and self.calls >= 2:
                (cwd / "slugify.py").write_text('def slugify(text): return "bad"\n')
        if self.behavior == "tamper":
            (cwd.parent / "Goal.md").write_text("changed")
        if self.behavior == "local-config":
            (cwd / ".codex").mkdir(exist_ok=True)
            (cwd / ".codex/config.toml").write_text('sandbox_mode="danger-full-access"')
        status = self.behavior if self.behavior in ("blocked", "needs_approval") else "done"
        output.write_text("bad JSON" if self.behavior == "malformed" else json.dumps({"status": status, "summary": "Test fixture increment"}))
        log.write_text(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 10}}) + "\n")
        return {"returncode": 0, "reason": None, "elapsed": .01}

class ContextLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve())
        self.root = init_project(Path(self.temp.name) / "demo", True)
    def tearDown(self): self.temp.cleanup()
    def run_with(self, behavior="success", check=False):
        harness = Harness(behavior)
        state = Runner(self.root, "fixture-codex", harness, sandbox=False).run(check)
        return state, harness
    def limits(self, **kw):
        path = self.root / "context-loop.json"
        value = read_json(path)
        value["limits"].update(kw)
        write_json(path, value)
    def test_verified_completion(self):
        state, harness = self.run_with()
        self.assertEqual(state["status"], "complete")
        self.assertEqual(harness.calls, 2)
        self.assertEqual(state["reported_tokens"], 220)
        self.assertTrue(all(t["status"] == "passed" for t in state["tasks"].values()))
        self.assertIn("Status:** complete", (self.root / "Progress.md").read_text())
    def test_model_done_cannot_pass_checks(self):
        state, harness = self.run_with("nochange")
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(harness.calls, 3)
        self.assertEqual(state["tasks"]["slugify-function"]["status"], "pending")
    def test_final_regression_rejected(self):
        state, _ = self.run_with("regression")
        self.assertNotEqual(state["status"], "complete")
        self.assertEqual(state["tasks"]["slugify-function"]["status"], "pending")
    def test_restart_revalidates_completed_task(self):
        self.run_with()
        (self.root / "workspace/slugify.py").write_text("bad syntax!")
        state, h = self.run_with()
        self.assertEqual(state["status"], "complete")
        self.assertGreaterEqual(h.calls, 1)
        self.assertEqual(state["iterations"], 3)
    def test_stale_running_state_recovered(self):
        path = self.root / ".context-loop/state.json"
        state = read_json(path)
        state.update(status="running", runner_pid=99999999, child_pid=99999999)
        write_json(path, state)
        self.assertEqual(self.run_with()[0]["status"], "complete")
    def test_living_prior_child_not_killed(self):
        path = self.root / ".context-loop/state.json"
        state = read_json(path); state["child_pid"] = os.getpid(); write_json(path, state)
        with self.assertRaisesRegex(ContextLoopError, "still alive"): self.run_with()
    def test_malformed_output_bounded(self):
        self.assertEqual(self.run_with("malformed")[0]["status"], "blocked")
    def test_explicit_block_and_approval(self):
        for status in ("blocked", "needs_approval"):
            with self.subTest(status=status):
                self.assertEqual(self.run_with(status)[0]["status"], status)
    def test_contract_tamper_rejected(self):
        self.assertEqual(self.run_with("tamper")[0]["status"], "error")
    def test_iteration_limit(self):
        self.limits(max_iterations=1)
        state, h = self.run_with("nochange")
        self.assertEqual(state["status"], "limit_reached")
        self.assertEqual(h.calls, 1)
    def test_reported_token_limit(self):
        self.limits(max_reported_tokens=1)
        state, h = self.run_with("nochange")
        self.assertEqual(state["status"], "limit_reached")
        self.assertEqual(h.calls, 1)
    def test_check_only_does_not_run_agent(self):
        state, h = self.run_with(check=True)
        self.assertEqual(state["status"], "checks_failed")
        self.assertEqual(h.calls, 0)
    def test_lock_contention(self):
        with lock(self.root):
            with self.assertRaisesRegex(ContextLoopError, "already active"): self.run_with()
    def test_missing_checks_refused(self):
        path = self.root / "context-loop.json"; config = read_json(path)
        config["tasks"][0]["checks"] = []; write_json(path, config)
        with self.assertRaisesRegex(ContextLoopError, "independent checks"): load(self.root)
    def test_existing_project_refused(self):
        with self.assertRaisesRegex(ContextLoopError, "existing path"): init_project(self.root)
    def test_workspace_traversal_refused(self):
        path = self.root / "context-loop.json"; config = read_json(path)
        config["workspace"] = "../outside"; write_json(path, config)
        with self.assertRaises(ContextLoopError): load(self.root)
    def test_control_symlink_refused(self):
        path = self.root / "Goal.md"; path.unlink(); path.symlink_to(self.root / "Constraints.md")
        with self.assertRaisesRegex(ContextLoopError, "symlink"): load(self.root)
    def test_schema_and_unsafe_flags(self):
        command = agent_command("codex", self.root, Path("schema"), Path("output"))
        self.assertIn("--ephemeral", command)
        self.assertIn("--ignore-user-config", command)
        self.assertNotIn("danger-full-access", " ".join(command))
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)
        self.assertIn('network={enabled=false}', " ".join(command))
    def test_fingerprint_includes_checks(self):
        before = fingerprint(self.root)
        (self.root / "checks/function_check.py").write_text("print('pretend')")
        self.assertNotEqual(before, fingerprint(self.root))
    def test_local_project_config_stops_next_turn(self):
        state, _ = self.run_with("local-config")
        self.assertEqual(state["status"], "error")

    def slow_check(self):
        path = self.root / "context-loop.json"
        config = read_json(path)
        config['tasks'] = [{'id': 'slow', 'description': 'Slow fixture', 'checks': [[sys.executable, '-c', 'import time; time.sleep(30)']]}]
        write_json(path, config)

    def test_runtime_deadline_stops_checks(self):
        self.slow_check()
        self.limits(max_runtime_seconds=1)
        started = time.monotonic()
        state, _ = self.run_with(check=True)
        self.assertEqual(state['status'], 'stopped')
        self.assertLess(time.monotonic()-started, 4)

    def test_check_timeout_is_not_success(self):
        self.slow_check()
        self.limits(check_timeout_seconds=1)
        state, _ = self.run_with(check=True)
        self.assertEqual(state['status'], 'error')
        self.assertIn('timeout', state['reason'])

    def test_stop_command_stops_running_check(self):
        self.slow_check()
        result = []
        thread = threading.Thread(target=lambda: result.append(self.run_with(check=True)[0]))
        thread.start()
        for _ in range(100):
            if read_json(self.root / '.context-loop/state.json').get('child_pid'):
                break
            time.sleep(.02)
        self.assertEqual(main(['stop', str(self.root)]), 0)
        thread.join(timeout=4)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result[0]['status'], 'stopped')

    def test_sigterm_stops_runner_and_child(self):
        self.slow_check()
        code = 'from context_loop.runner import Runner; import sys; Runner(sys.argv[1], "fixture-codex", sandbox=False).run(check_only=True)'
        process = subprocess.Popen([sys.executable, '-c', code, str(self.root)])
        child = None
        try:
            for _ in range(100):
                child = read_json(self.root / '.context-loop/state.json').get('child_pid')
                if child:
                    break
                time.sleep(.02)
            self.assertIsNotNone(child)
            process.send_signal(signal.SIGTERM)
            self.assertEqual(process.wait(timeout=5), 0)
            self.assertEqual(read_json(self.root / '.context-loop/state.json')['status'], 'stopped')
            with self.assertRaises(ProcessLookupError): os.kill(child, 0)
        finally:
            if process.poll() is None:
                process.kill(); process.wait()

class SupervisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.pids = []
    def tearDown(self): self.temp.cleanup()
    def call(self, code, timeout=3, stop=lambda: False, cap=100000):
        return execute([sys.executable, "-c", code], self.root, self.root / "log", timeout, cap, stop, self.pids.append)
    def test_timeout_terminates_child(self):
        outcome = self.call("import time; time.sleep(30)", timeout=.15)
        self.assertEqual(outcome["reason"], "timeout")
        with self.assertRaises(ProcessLookupError): os.kill(self.pids[0], 0)
    def test_stop_terminates_child(self):
        start = time.monotonic()
        outcome = self.call("import time; time.sleep(30)", stop=lambda: time.monotonic()-start>.1)
        self.assertEqual(outcome["reason"], "stopped")
        self.assertEqual(self.pids[-1], None)
    def test_signal_ignored_child_killed(self):
        outcome = self.call("import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)", timeout=.2)
        self.assertEqual(outcome["reason"], "timeout")
        self.assertEqual(outcome["returncode"], -signal.SIGKILL)
    def test_log_limit(self):
        outcome = self.call("import sys,time; print('x'*10000, flush=True); time.sleep(30)", cap=100)
        self.assertEqual(outcome["reason"], "log_limit")
    def test_report_rejects_nonobject(self):
        output = self.root / "out"; output.write_text("[]")
        log = self.root / "log"; log.write_text("")
        with self.assertRaises(ContextLoopError): report(output, log)

    def test_background_descendant_cleaned_after_parent_exit(self):
        code = "import subprocess,sys; from pathlib import Path; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); Path('descendant').write_text(str(p.pid))"
        outcome = self.call(code)
        self.assertEqual(outcome['returncode'], 0)
        pid = int((self.root / 'descendant').read_text())
        # A briefly unreaped orphan can be a zombie; it must no longer execute.
        result = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)], capture_output=True, text=True)
        self.assertTrue(not result.stdout.strip() or result.stdout.strip().startswith('Z'), result.stdout)

if __name__ == '__main__': unittest.main()
