# Sources and design influences

This is an original implementation. It contains no copies of private chats,
bookmarks, credentials, or full source articles.

- [OpenAI: Non-interactive Codex](https://learn.chatgpt.com/docs/non-interactive-mode):
  structured results, JSONL events, fresh CLI execution, saved login, usage reports.
- [OpenAI: Permission profiles](https://learn.chatgpt.com/docs/permissions) and
  [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference):
  explicit named filesystem/network permissions. The installed CLI is checked
  alongside documentation because flags can change.
- [OpenAI: Iterative repair loops](https://developers.openai.com/cookbook/examples/codex/build_iterative_repair_loops_with_codex):
  independent evaluation and bounded feedback-driven repair.
- [Anthropic: Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents):
  persistent progress, small increments, and checks across fresh contexts.
- [Anthropic: Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents):
  selective context and durable notes rather than ever-growing chat transcripts.
- [Geoffrey Huntley: Ralph](https://ghuntley.com/ralph/) and
  [HumanLayer: A brief history of Ralph](https://www.humanlayer.dev/blog/brief-history-of-ralph):
  fresh execution loops, clear end states, and verification pressure.
- [Bruce Schneier: Agentic AI's OODA loop problem](https://www.schneier.com/blog/archives/2025/10/agentic-ais-ooda-loop-problem.html):
  untrusted observations should not become authorization for external actions.

Obsidian serves as an optional visual editor for the local Markdown, not as the
execution engine. Other reading-list ideas are deferred where they do not improve
the small Codex-first contract, notably distributed workers and Claude integration.
