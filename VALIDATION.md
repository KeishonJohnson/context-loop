# Validation — Goalkeeper v0.1

Validation performed on macOS, Python 3.14.8, Codex CLI 0.157.0 using its existing
ChatGPT login. No production project was modified or adopted into this harness.

## Verified

- Automated unit/integration suite: 30 tests cover actual behavioral acceptance,
  model false-completion claims, final regression detection, restart revalidation,
  stale state, live-child refusal, malformed JSON, blocked/approval responses,
  contract tampering, iteration/token limits, runtime/check timeouts, stop requests,
  SIGTERM handling, process termination/escalation, background descendant cleanup, logs, lock contention,
  missing checks, existing-folder refusal, path/symlink rules, and sandbox argv.
- `tools/verify_sandbox.py`: four real installed-sandbox checks passed, demonstrating
  workspace writes, denied contract/sibling writes, read-only check execution, and
  denied direct network calls against an otherwise reachable local HTTP fixture.
- Real disposable Codex demo: two successful fresh agent turns built the slugify
  function and CLI. Every final behavioral check passed under the read-only sandbox.
  The initial permission-profile parse attempt failed safely and was corrected;
  the retained local history records three failed startup turns followed by two
  successful turns. Completion required no owner intervention or acceptance edits.
- The real successful run reported 174,949 input + output tokens (cached input
  included). This proves functionality, not a claim of minimal token cost.
- Source installation into a private virtual environment successfully built and
  installed `goalkeeper-codex==0.1.0`; no runtime dependencies are declared.

## Release checks

- Installed source CLI `doctor` and `--help`: passed.
- Standalone zipapp help, init, status, stop, and check commands: passed. An empty
  fresh demo correctly returned `checks_failed` without running an agent.
- Standalone zipapp `run` against the real completed demo: independently reran
  the final sandboxed checks, returned `complete`, and used no further agent turns.
- `tools/verify_release.py`: checksums, safe archive paths, exclusion of private
  runtime/credential files, packaged-source equality, and extracted CLI commands
  passed. The archive contains source, documentation, tests, license, and zipapp.
- Local repository initialized on `main`; implementation and release evidence
  committed. No remote configured or published. Distribution files remain in dist/.
- All test/demonstration processes finished; final demo state has no runner or
  active child PID. The source-suite process inspection required execution outside
  the outer tool sandbox; the production check profiles stayed sandboxed.

Completion contract: **COMPLETE** on 7 October 2026 Pacific time. SHA256 sums are
in `dist/SHA256SUMS`; hashes are generated after packaging rather than embedded
here to avoid an archive self-reference.

## Practical limits

See `docs/ARCHITECTURE.md` for write containment versus read privacy, trusted-check
limitations, external file races, SIGKILL/PID recovery, token reporting, sampled
log thresholds, and platform scope. Linux has not been validated. No remote
publishing, continuous background daemon, deployment, or existing-project changes
are part of this release.
