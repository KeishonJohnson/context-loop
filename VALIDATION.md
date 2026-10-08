# Context Loop v0.3 validation

Validated on macOS with Python 3.14.8 and Codex CLI 0.157.0 on 7 October 2026
Pacific time. Only Context Loop, its disposable fixtures and the previously
requested Desktop guide were changed. No other real project was adopted.

## Automated tests

76 tests passed in the final combined suite, including all 30 legacy managed-mode
regressions. Existing-project cases cover additive attachment, original file and
Git HEAD preservation, mapped source order, selective wiki-note retrieval,
requirement quotations, source/check/task approval pinning across restarts,
conflicts despite green tests, exact citations, persistent review blocks, missing
and ambiguous notes, line-ending changes, malformed context, unapproved runs,
new nested instructions, symlinks, context budgets, status, and model-free checks.
The regression suite also exercises limits, stop, signals and child cleanup.

## Real sandbox evidence

The original four installed-sandbox groups passed. Seven existing-project groups
also passed, comprising 17 write probes: allowed code creation; denied writes to
root/nested guidance, roadmap, configuration, controls, runtime, Git metadata,
unrelated files and external Obsidian notes; denied atomic replacement and deletion
of a protected source; denied nested .codex creation and symlink escape; and a
read-only check profile in the existing source layout. Direct networking remains
disabled. These are actual installed Codex sandbox tests, not mocked permissions.

## Real Codex evidence

- A disposable existing Git repository retained its original source layout. A
  separate Markdown vault supplied an index, selected guidance and its linked
  example. The read-only review reported alignment, the implementation turn cited
  the exact governing hashes and R1/R2 requirements, and independent behavior
  checks passed. Final status: complete, one implementation turn. Audit plus
  implementation reported 145,511 input and output tokens.
- A second fixture deliberately contradicted the roadmap with a mandatory output
  decision. Real Codex identified the conflict and returned blocked before any
  implementation turn. The original source file remained byte-identical. Reported
  usage was 17,891 tokens for the read-only review.
- Changing the successful fixture's selected Obsidian guidance invalidated approval
  before another agent request. Restoring the exact source restored the pinned
  snapshot. Original governing documents, Git baseline and external notes were
  independently checked for preservation.
- Both live fixtures ended with no recorded runner or child process active.

These examples validate the integration; they do not establish universal semantic
conflict detection or minimal token cost. Semantic review is model-assisted.

## Installation and distribution

The v0.3 Python package installs into an isolated local virtual environment and
provides inspect, attach and approve alongside init, run, check, status, stop and
doctor. The standalone zipapp includes the same source bytes. Release verification
checks SHA256 sums, excludes private runtime and credential files, and exercises
commands from an extracted ZIP. It also configures and approves an existing
project through the packaged CLI and passes its check in the real read-only
sandbox without invoking a model. No runtime Python dependencies are declared.

Sources, tests, guides, license and executable are included in
`dist/context-loop-0.3.0.zip`; checksums live in `dist/SHA256SUMS`.
The v0.3 change is committed locally. It has not been pushed or published as a
GitHub release; public v0.2 remains available. This build did not edit global
Codex instructions or enroll a fleet of existing repositories.

## Practical boundaries

Read isolation and hostile-code limitations remain as described in
`docs/ARCHITECTURE.md`. Linux is unverified. Existing .codex configuration is
refused; prepare dependencies and adapt checks to read-only execution. Only
explicit Markdown sources and selected wiki-linked notes are governed. Ordinary
Markdown links and references in prose do not automatically add documents.
Progress notes describe the last recorded run; use status to validate current
approval while the runner is stopped. No background watcher is installed.

Approval is an owner decision, not a model's authority to rewrite the build plan.
Source changes and context violations require reviewed approval. Passing checks
prove only what those owner-provided checks cover; important changes still deserve
review. Token thresholds apply between turns and are not hard spending caps.

Earlier release evidence is preserved in `docs/VALIDATION_V02.md`.
