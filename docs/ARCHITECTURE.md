# Architecture and boundaries

## Execution

1. Validate a new managed project's owner configuration, paths, and task checks.
2. Acquire an exclusive `flock`; reject concurrent runners for the same project.
3. Recover atomic state and rerun acceptance checks against current code.
4. Choose the first pending task; supply the owner goal, constraints, decisions,
   recent progress, and failed check evidence to a fresh `codex exec` process.
5. Supervise the process, parse its schema-constrained JSON, record reported usage,
   and independently run the configured check commands.
6. Repeat within limits. All checks run against the final workspace before complete.

Generated task/progress Markdown is a view of runner state. An agent saying
“done” never sets a task to passed. A `blocked` or `needs_approval` report stops
rather than silently assuming access or approval. No autonomous background service
is installed. Keep the terminal running, or manage the process using your own
supervisor; Context Loop itself does not prevent laptop sleep.

## Directory layout

```text
managed-project/
  Goal.md, Constraints.md, Decisions.md     owner context
  context-loop.json, checks/                 owner acceptance contract
  Index.md, Tasks.md, Progress.md           readable Obsidian views
  workspace/                               agent-writable source and NOTES.md
  .context-loop/state.json                   atomic private runtime state
  .context-loop/run.lock                     process lock (file can persist)
  .context-loop/runs/<uuid>/                  local prompts' outputs and check logs
```

Runtime files stay on the owner's machine and are excluded by the starter's
`.gitignore`. Logs can contain project content; review them before sharing.

## Codex integration

The adapter uses root `-a never`, fresh `exec` with `--ephemeral`,
`--ignore-user-config`, `--ignore-rules`, `--json`, `--output-schema`, and `-o`.
It defines its own named permissions extending `:read-only`, disables direct
network access, and grants write permission only to the absolute workspace path.
Checks run through `codex sandbox -P` with a read-only, network-disabled profile.
No production fallback executes unsandboxed checks. The Python test suite injects
an explicit fake adapter and unsandboxed fixture checks only in temporary test
projects; those options are not exposed by the public CLI.

Direct child-command network access is blocked; the Codex CLI still contacts its
model service. Files outside the workspace can be readable under the read-only
baseline. This is **write containment, not a private-file read isolation guarantee**.
Do not use it for adversarial code or expose sensitive readable content expecting
this harness to hide it. Codex's internal sandbox implementation is a dependency;
verify it on your platform with `tools/verify_sandbox.py`.

## Persistence and recovery

State writes use temporary files, fsync, and atomic replacement. A restart keeps
workspace code and revalidates prior successes. A dead recorded child is recoverable;
a recorded child PID still alive causes a conservative refusal, never an unverified
kill. An abrupt SIGKILL of the runner can leave a child alive; inspect/stop that
specific process manually before restarting. PID reuse can cause the same refusal.
Graceful SIGINT, SIGTERM, and stop requests terminate the owned active child group.
Checks and Codex commands run with no shell interpolation.

## Limits of the MVP

- Tested on macOS only; Linux implementation uses POSIX primitives but is unverified.
- Python 3.11+ and compatible installed Codex CLI are prerequisites.
- Acceptance checks are trusted owner code, not supplied or rewritten by the agent.
  They test behavior but are not an adversarial proof against an implementation
  deliberately exploiting a test process. Review high-impact changes yourself.
- A filesystem race with an outside process changing files is not fully prevented.
  Contract hashes detect changes at command boundaries. Do not edit contracts
  while a run is active. Symlinked control paths and workspace roots are rejected.
- Owner goal, constraints, decisions and files under `checks/` are frozen per run;
  dependencies stored elsewhere are not hashed. Put acceptance scripts in checks/.
- `.codex` workspace configuration stops execution. Arbitrary custom integrations,
  per-project agent plugins, and network package installs are outside v0.2 scope.
- No dollar cap, guaranteed context efficiency, or guaranteed convergence.
  Reported token threshold is a between-turn guard; interrupted usage may be absent.
- Total storage across runs is not capped. Individual log thresholds are sampled,
  not exact byte caps; review/archive local logs when necessary.
- No GitHub upload, Obsidian automation API, Claude adapter, trade execution,
  migration of existing projects, or distributed multi-agent coordination.
