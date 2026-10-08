# Context Loop

A Codex-first local execution partner that works through a goal in bounded loops.
Each cycle gets a fresh Codex session. Markdown preserves your goal and decisions;
independent acceptance checks decide when the work is complete.

**v0.3 supports macOS and Linux with Python 3.11+ and Codex CLI.** The real integration
was tested on macOS with Codex CLI 0.157.0. Claude and Windows are not implemented.

## Start with the standalone package

Download/extract the [latest release ZIP](https://github.com/KeishonJohnson/context-loop/releases/latest). Use the included `context-loop.pyz`; no Python
package dependencies are needed. Install/sign in to Codex separately using the
[official setup instructions](https://developers.openai.com/codex/quickstart).
An existing Codex ChatGPT login works; Context Loop does not copy credentials or
require you to supply an API key. Codex access and usage depend on your account.

```sh
python3 context-loop.pyz doctor
python3 context-loop.pyz init ~/Documents/context-loop-demo --demo
python3 context-loop.pyz run ~/Documents/context-loop-demo
python3 context-loop.pyz status ~/Documents/context-loop-demo
```

The demo builds a small slugify function and CLI. Two separate acceptance scripts
check actual behavior. `run` returns zero only when all final checks pass.

To request a stop from another terminal:

```sh
python3 context-loop.pyz stop ~/Documents/context-loop-demo
```

Ctrl-C also stops the active run. The runner terminates only the child process group
it started. Restart with the same `run` command: existing code is retained and
checks run again before any new agent session.

## Use an existing project

Code can stay in its current repository. Read [the existing-project guide](docs/EXISTING_PROJECTS.md)
and use [the reusable Codex setup instruction](docs/PROJECT_SETUP_PROMPT.md).

```sh
python3 context-loop.pyz inspect /absolute/path/to/project
```

Then attach with explicit source paths and allowed code paths, bind tasks to exact
approved requirements, and review before `approve` and `run`. Original build docs,
guidance, status and selected Obsidian notes govern the work. Hash pinning catches
source drift across restarts, a read-only alignment review flags conflicts before
edits, and independent checks verify results. Progress goes into a visible
`Context Loop/` folder; source notes and existing project instructions are preserved.

The integration is opt-in for each project. No global instructions or other
repositories are changed automatically. Conflict review is model-assisted, so
strong acceptance checks and owner review remain necessary.

## Use it for your own goal

```sh
python3 context-loop.pyz init ~/Documents/my-new-project
```

Edit `Goal.md`, `Constraints.md`, and `Decisions.md`. Replace the placeholder task
in `context-loop.json` with a small concrete increment and one or more executable
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
These are the same local files Context Loop reads and updates. Obsidian is optional;
there is no Obsidian API, subscription, or background sync service. Owner notes
are not automatically rewritten by the agent; it records discoveries in
`workspace/NOTES.md`, which you can review and promote into Decisions yourself.

## Limits and status

Defaults in `context-loop.json` (attached runs also include one read-only alignment review): 10 agent iterations, 30 minutes total per run,
5 minutes per agent turn, 30 seconds per check, 3 consecutive unsuccessful turns,
4 MB log-size stop threshold, and 200,000 reported input + output tokens per run.
No automatic retry loop runs outside those limits. `complete` means all configured
checks passed against the final workspace. Other results include `blocked`,
`needs_approval`, `limit_reached`, `stopped`, `checks_failed`, and `error`. Attached mechanical-only checks can return `checks_passed`; stale
approval is reported as `context_unready`.

Limits reset only when you explicitly start another run; the history, total
iterations, and reported token totals persist. Tokens are reported after a turn,
so this is **not a hard token or dollar cap**. Cached input is included in the
reported count. Failed/interrupted turns may not report usage. Process termination
can add a few seconds of grace; the log threshold is sampled and can overshoot.

Read [architecture and limitations](docs/ARCHITECTURE.md) and
[validation evidence](VALIDATION.md) before adopting this for important work.
Context Loop does not guarantee an agent will solve a goal or discover a weak test.
It does not run indefinitely, trade, deploy, publish, or send external messages.

## Install from source and distribute

```sh
python3 -m pip install .
context-loop doctor
context-loop init ~/Documents/context-loop-demo --demo
context-loop run ~/Documents/context-loop-demo
```

Developer commands:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 tools/verify_sandbox.py
python3 tools/verify_existing_sandbox.py
python3 tools/package.py
```

`dist/` contains the zipapp, a source-and-zipapp distribution ZIP, and SHA256 sums.
Share the ZIP or publish the clean source repository to GitHub. Recipients use
their own Codex login; private project folders, run logs, and credentials are not
included. The public source repository is [KeishonJohnson/context-loop](https://github.com/KeishonJohnson/context-loop).
Release downloads include the ZIP, standalone zipapp, and SHA256 checksums.
No PyPI upload has been performed.

MIT licensed. Design influences and official CLI documentation are attributed in
[SOURCES.md](docs/SOURCES.md).

## Name change in v0.2.0

The product is **Context Loop**, the repository and command are `context-loop`,
and the Python import is `context_loop`. New projects use `context-loop.json`
and `.context-loop/` for their contract and runtime state.

For projects created with the original v0.1.0 release, stop the old runner first,
back up the project, and rename `goalkeeper.json` to `context-loop.json` and
`.goalkeeper/` to `.context-loop/`. Update the old names in the project's
`.gitignore`, index, and workspace instructions, then run the new executable.
Workspace code and prior run history can stay in place; checks are revalidated
on restart. The previous release remains available as historical version 0.1.0.
