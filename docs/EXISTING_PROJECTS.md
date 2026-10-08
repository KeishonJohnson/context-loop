# Use an existing project without moving its code

Context Loop v0.3 can attach to a repository in its current location. Attachment
adds `context-loop.json`, a visible `Context Loop/` control and progress folder,
and private `.context-loop/` runtime state. It preserves original instructions,
build documents, code, Git metadata, and existing Tasks/Progress notes. It does
not run tasks or approve a plan just because those files were created.

## Read and map the established build

Use the standalone tool from its folder. Substitute your real project path:

```sh
cd ~/projects/context-loop
python3 dist/context-loop.pyz inspect /absolute/path/to/project
```

Inspection lists instruction files and candidate Markdown documents without
modifying the project. Filenames are candidates, not assumed sources of authority.
Identify the real instructions, build roadmap/scope, decisions/constraints, current
status/handoff, and Obsidian project index. Source roles load in that order;
additional specification and research notes follow. Research cannot override the
approved plan. Instructions include applicable ancestor and nested `AGENTS.md`,
`CLAUDE.md`, and `AGENTS.override.md` files.

```sh
python3 dist/context-loop.pyz attach /absolute/path/to/project \
  --source build:roadmap:docs/BUILD.md \
  --source decisions:decisions:docs/DECISIONS.md \
  --source handoff:status:docs/STATUS.md \
  --write-path src \
  --obsidian-root /absolute/path/to/vault \
  --obsidian-index "/absolute/path/to/vault/Project Index.md"
```

Use actual paths; no particular build-document names are required. Existing
instruction files are mapped automatically. Each `--source` has `ID:ROLE:PATH`;
paths inside the project can be relative. External source files must be inside
explicit Obsidian roots, except automatically applicable ancestor instructions.
The Obsidian index option defaults its allowed note root to the index's parent if
no wider vault root was explicitly provided. Obsidian is optional if the project
has no relevant vault notes. A project with no instructions can supply an existing
Markdown guidance source using the `instructions` role.

`--write-path` can repeat for specific files or directories. Whole-project write
permission is refused. Governing sources and nested instruction files remain
read-only even inside an allowed source directory. Protecting those files does
not stop normal source changes in neighboring files. No `.gitignore`, AGENTS,
CLAUDE, source file, or Git setting is rewritten during attachment.

## Bind tasks to governing requirements

Edit the new `context-loop.json`. Keep the limit settings; configure these fields:

```json
{
  "context": {
    "requirements": {
      "R1": {
        "source": "build",
        "quote": "Exact requirement text copied from the approved build document."
      }
    }
  },
  "tasks": [
    {
      "id": "first-approved-increment",
      "description": "Implement the increment described by R1 only.",
      "requirements": ["R1"],
      "context_sources": [],
      "notes": ["Relevant Guidance"],
      "checks": [["{python}", "-B", "{control}/checks/first_check.py"]]
    }
  ]
}
```

This snippet shows the fields to edit, not a replacement for the full generated
configuration. Keep `context.sources`, `context.obsidian_roots`, the context
budget, mode, workspace, and write paths. Requirement quotations must occur
verbatim in a mapped roadmap, decision, or specification source. Tasks cannot be
approved without real checks or valid requirement bindings. Store trusted check
scripts in `Context Loop/checks/`, outside the code's write permissions.
`{project}` and `{workspace}` refer to the existing repository root; `{control}`
refers to the visible control folder. Checks execute without a shell.

## Use Obsidian notes selectively

A mapped index uses ordinary `[[Note]]` or `[[folder/Note]]` wiki links. A task's
`notes` list selects exact link targets from that index; aliases and heading
suffixes are removed when identifying the target. Selected notes and their
immediate wiki-linked supporting notes are loaded. Other vault content is not
sent to the model. `context_sources` selects additional mapped source IDs.

Missing or ambiguous links stop validation. Use explicit paths to disambiguate
notes. Absolute links, traversal, symlinked notes, and targets outside the project
or declared note roots are refused. The full selected governing context is loaded;
over-budget text is refused instead of silently truncated. Standard Markdown
links do not trigger automatic note retrieval in v0.3; map those documents directly.

Progress goes to `Context Loop/Index.md`, `Tasks.md`, and `Progress.md`. Open the
existing project in Obsidian, or a vault containing it, to view those files. The
folder is visible to Obsidian, while private runtime logs stay in `.context-loop/`.
Existing source notes and status documents are never rewritten by the runner.
For a separate vault, open the source index there and the project's output notes
where the project lives; the tool does not install sync or copy private notes.

## Review then approve

Review mapped paths, source roles, exact requirement quotations, allowed write
paths, and independent acceptance checks. Resolve contradictory instructions in
the governing documents before approval. Record your decision:

```sh
python3 dist/context-loop.pyz approve /absolute/path/to/project \
  --note "I approve these source mappings, requirement bindings, checks, and write paths."
python3 dist/context-loop.pyz run /absolute/path/to/project
```

Approval pins hashes across restarts. Changed sources, selected notes, checks,
source mappings, scope, or tasks require a new explicit approval. It cannot run
with a silently updated baseline. Approval cannot be changed while a runner is
active. New unlisted nested instructions also stop execution.

A real read-only Codex review checks the approved corpus and task bindings for
conflicting scope or direction before edits. Each implementation turn receives
its governing context and must return the exact source hashes and requirement
IDs. Missing or mismatched provenance, or a reported conflict, blocks acceptance
and requires owner review plus fresh approval. Passing tests cannot override that
block. Every final task check runs against the current code before completion.

Semantic conflict detection is model-assisted, not a proof that every possible
contradiction or deviation will be found. Requirement binding, hash pinning, write
protection, and acceptance checks provide separate mechanical guardrails. Choose
checks that prove the intended behavior, and review important changes.

## Stop resume and check

Use the same `stop`, `status`, and `run` commands as for a managed project. Ctrl-C
also stops an active runner. Resume preserves source code and history, reruns the
alignment review, and revalidates checks. A prior context violation cannot be
cleared by restarting with the same approval. A fresh reviewed approval is needed.

`check` never invokes a model. On an attached project it returns `checks_passed`
when mechanical checks succeed, without claiming the alignment review passed.
`run` performs that review and can return `complete`. Status reports
`context_unready` if an apparently completed project's approval has become stale.

The v0.2 managed-project workflow remains supported. Existing project `.codex`
configuration is currently refused rather than silently loading custom settings
that could widen permissions. Prepare dependencies before execution; network and
package installation remain blocked. A background process editing governing
notes will intentionally stop the run and require review. No other project is
adopted, migrated, or started automatically.

Progress notes describe the last recorded run. When a runner is stopped, use
`status` to validate the current source approval; no background watcher is installed.
