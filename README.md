# Goalkeeper

A Codex-first local execution partner that works through a goal in bounded loops.
Each cycle gets a fresh Codex session. Markdown preserves your goal and decisions;
independent acceptance checks decide when the work is complete.

**v0.1 supports macOS and Linux with Python 3.11+ and Codex CLI.** The real integration
was tested on macOS with Codex CLI 0.157.0. Claude and Windows are not implemented.

## Start with the standalone package

Download/extract the distribution ZIP. Use the included `goalkeeper.pyz`; no Python
package dependencies are needed. Install/sign in to Codex separately using the
[official setup instructions](https://developers.openai.com/codex/quickstart).
An existing Codex ChatGPT login works; Goalkeeper does not copy credentials or
require you to supply an API key. Codex access and usage depend on your account.

```sh
python3 goalkeeper.pyz doctor
python3 goalkeeper.pyz init ~/Documents/goalkeeper-demo --demo
python3 goalkeeper.pyz run ~/Documents/goalkeeper-demo
python3 goalkeeper.pyz status ~/Documents/goalkeeper-demo
```

The demo builds a small slugify function and CLI. Two separate acceptance scripts
check actual behavior. `run` returns zero only when all final checks pass.

To request a stop from another terminal:

```sh
python3 goalkeeper.pyz stop ~/Documents/goalkeeper-demo
```

Ctrl-C also stops the active run. The runner terminates only the child process group
it started. Restart with the same `run` command: existing code is retained and
checks run again before any new agent session.

## Use it for your own goal

```sh
python3 goalkeeper.pyz init ~/Documents/my-new-project
```

Edit `Goal.md`, `Constraints.md`, and `Decisions.md`. Replace the placeholder task
in `goalkeeper.json` with a small concrete increment and one or more executable
acceptance checks. A starter project deliberately cannot run with empty checks.

```json
{
  "id": "greeting",
  "description": "Create greet.py with a greet(name) function returning Hello, <name>!",
  "checks": [["{python}", "-B", "{project}/checks/greeting_check.py"]]
}
```

Checks are **owner-trusted argument arrays**, run without a shell from `workspace/`.
`{python}`, `{project}`, and `{workspace}` substitute the interpreter and absolute
paths. Store checks in `checks/` outside the agent's writable workspace. Write
checks that prove the intended behavior and relevant regressions; a command that
always returns zero is not evidence. Project-level checks that cover interactions
between tasks should be included in the task contract. All task checks rerun before
completion. Package installation and network calls are blocked in these profiles;
prepare dependencies yourself before the run.

Only `workspace/` is writable by agent commands. The owner contract and runner
state sit outside it. Owner edits during a run invalidate acceptance and stop the
run. Do not add `.codex` project configuration to the managed workspace.
`init` refuses an existing path: it never retrofits or changes another project.
Use a fresh folder; manually copy selected source into its workspace if needed.

## Obsidian

Open the managed project folder as an Obsidian vault, or create it inside your
existing vault. `Index.md` links to Goal, Constraints, Decisions, Tasks, and Progress.
These are the same local files Goalkeeper reads and updates. Obsidian is optional;
there is no Obsidian API, subscription, or background sync service. Owner notes
are not automatically rewritten by the agent; it records discoveries in
`workspace/NOTES.md`, which you can review and promote into Decisions yourself.

## Limits and status

Defaults in `goalkeeper.json`: 10 agent iterations, 30 minutes total per run,
5 minutes per agent turn, 30 seconds per check, 3 consecutive unsuccessful turns,
4 MB log-size stop threshold, and 200,000 reported input + output tokens per run.
No automatic retry loop runs outside those limits. `complete` means all configured
checks passed against the final workspace. Other results include `blocked`,
`needs_approval`, `limit_reached`, `stopped`, `checks_failed`, and `error`.

Limits reset only when you explicitly start another run; the history, total
iterations, and reported token totals persist. Tokens are reported after a turn,
so this is **not a hard token or dollar cap**. Cached input is included in the
reported count. Failed/interrupted turns may not report usage. Process termination
can add a few seconds of grace; the log threshold is sampled and can overshoot.

Read [architecture and limitations](docs/ARCHITECTURE.md) and
[validation evidence](VALIDATION.md) before adopting this for important work.
Goalkeeper does not guarantee an agent will solve a goal or discover a weak test.
It does not run indefinitely, trade, deploy, publish, or send external messages.

## Install from source and distribute

```sh
python3 -m pip install .
goalkeeper doctor
goalkeeper init ~/Documents/goalkeeper-demo --demo
goalkeeper run ~/Documents/goalkeeper-demo
```

Developer commands:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 tools/verify_sandbox.py
python3 tools/package.py
```

`dist/` contains the zipapp, a source-and-zipapp distribution ZIP, and SHA256 sums.
Share the ZIP or publish the clean source repository to GitHub. Recipients use
their own Codex login; private project folders, run logs, and credentials are not
included. No GitHub or PyPI publishing has been performed.

MIT licensed. Design influences and official CLI documentation are attributed in
[SOURCES.md](docs/SOURCES.md).
