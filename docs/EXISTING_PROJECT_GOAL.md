# Existing project context integration goal

Build Context Loop v0.3 so a project can retain its code layout and original
instructions, while approved build documents, guidance, and Obsidian Markdown
govern every execution cycle. Never migrate another real project during this build.

Completion contract:

- Attach adds only dedicated configuration/control/output files; original code,
  instructions, Git metadata, and notes remain byte-identical.
- Explicit source roles load instructions, roadmap/scope, decisions/constraints,
  current status, Obsidian index, and relevant task notes in a defined order.
- Tasks cite exact requirements from approved source documents and have independent
  acceptance checks. Missing/ambiguous sources, links, or requirements fail closed.
- Approval pins hashes of the task contract, governing sources, and checks across
  restarts. Any change needs a new owner approval; no silent rebaselining.
- A read-only alignment review flags semantic conflicts before edits; execution
  summaries must cite their task requirements and loaded source hashes. Document
  honestly that semantic drift detection is model-assisted, not a formal guarantee.
- Write permissions are restricted to explicitly allowed project paths. Governing
  documents, instruction files, checks, control files, Git metadata, and external
  notes remain protected. Check processes remain read-only and network-disabled.
- Runtime checks detect source/contract drift; final checks cover all tasks. Stop,
  resume, concurrent runners, and legacy managed-project behavior stay functional.
- Tests cover real repositories and separate Obsidian fixtures, conflicts, source
  changes, provenance, task-note retrieval, symlinks, unapproved contexts, and
  real sandbox boundaries. A real Codex existing-project demo must complete.
- Documentation, reusable adoption prompt, versioned local package, installer,
  and extracted-package verification are complete. Commit the reviewed change
  locally; remote release publication is a separate step.

Status: COMPLETE

Evidence: ../VALIDATION.md records 76 passing tests, original and existing-mode
real sandbox probes, a real Codex implementation following approved build docs
and selected Obsidian notes, a real conflict refusal before edits, source-drift
refusal, source installation and extracted distribution checks. The code, guides,
adoption prompt and local v0.3 package are complete. No other existing project was
migrated, and no remote publication was performed for this goal.
