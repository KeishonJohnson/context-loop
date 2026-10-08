# Context Loop development

Work only in this repository. Do not access or change existing trading, Jarvis,
PenMod, or other projects. Read docs/BUILD_GOAL.md before implementation.
Codex is the only live agent adapter in v0.2. Keep dependencies to the Python
standard library at runtime. Never substitute agent claims for acceptance checks.
Freeze the owner contract for each run. Keep control files outside the agent's
writable workspace. Never bypass the Codex sandbox or execute checks unsandboxed
in production. Tests use temporary directories and explicit test doubles.
No remote publishing, credential copying, orders, or changes to system settings.

