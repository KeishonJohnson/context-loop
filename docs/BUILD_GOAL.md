# Context Loop v0.2 completion contract

Build a shareable, Codex-first local execution partner. It must recover the goal,
decisions and verification evidence between fresh Codex sessions, make incremental
progress, and stop when independent acceptance checks pass or a real boundary is
reached. Existing projects must remain untouched.

Required evidence before marking complete:

- An installable Python CLI and standalone zipapp provide init, run, status,
  stop, check, and doctor.
- Init creates a new managed project with Markdown goal, constraints, decisions,
  progress, tasks, and an index suitable for Obsidian; it refuses existing data.
- Real Codex CLI integration uses fresh sessions, structured JSON, explicit
  limited permissions, and existing login without copying credentials.
- Owner task contract and acceptance scripts remain outside writable workspace;
  only runner-run checks can mark tasks passed. Final checks rerun every task.
- Runtime, iteration, log-size, and consecutive-failure limits are enforced;
  token usage stops subsequent iterations when the reported budget is reached.
- Stop, signals, lock contention, malformed output, failed checks, stale state,
  regression, contract tampering, and restart recovery are tested.
- A real disposable Codex demo reaches independently verified completion.
- Real sandbox tests show code can write only in its workspace and cannot write
  the owner contract or make direct network calls during checks.
- README, architecture, source attribution, limitations, and MIT license exist.
- Local Git history, a sanitized distribution ZIP, executable zipapp, and checksums
  are produced; packaged commands and demo are tested.

No GitHub publishing or PyPI upload is part of this local MVP. No autonomous
trading, browser actions, deployment, or external integrations. Supporting Claude
and Windows is deferred. The user has authorized autonomous work until this
contract is satisfied. Record any residual limitation honestly in VALIDATION.md.

Status: COMPLETE

Evidence: see ../VALIDATION.md. The real Codex demo, 30 automated tests, four
installed-sandbox boundary checks, source installation, extracted distribution
commands, and packaged final acceptance checks passed. Local Git and distribution
artifacts are ready. No existing project was modified and no remote was published.
