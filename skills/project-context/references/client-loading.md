# Client loading

Consult this when designing or checking how instructions reach an agent. Official documentation checked 2026-10-05; recheck the relevant page when client versions, settings or observed behavior differ.

## Codex

Codex constructs guidance at session startup along the project-root-to-working-directory path. Within a directory it selects `AGENTS.override.md`, otherwise `AGENTS.md`, otherwise a configured fallback. The combined chain has a configurable byte limit. Starting at the root does not establish that deeper instructions were injected for a later edit. Verify the effective chain from root and nested starts; use explicit reads for other affected paths. [Official AGENTS.md guide](https://learn.chatgpt.com/docs/agent-configuration/agents-md)

## Claude Code

Ancestor `CLAUDE.md` files load at launch; descendant instructions and path-scoped rules can load on relevant file access. Unconditional imports still cost context. Shell access is not proof that a file-triggered rule loaded.

Current Claude Code supports native `AGENTS.md`, with version, plugin and configuration conditions. Default selection prefers applicable `CLAUDE.md`/`CLAUDE.local.md` files when present. `AGENTS.override.md` is not a shared cross-client override.

A neighboring `CLAUDE.md` containing `@AGENTS.md` remains a supported compatibility adapter. Choose native loading or an adapter from observed behavior; preserve any unique Claude instructions when deduplicating. Check `/context` or `/memory` and test a matching file read. Project `MEMORY.md` and Claude's own auto-memory store are different mechanisms. [Official memory guide](https://code.claude.com/docs/en/memory)

## Verification recipe

Record the client version, launch directory, relevant settings and observed instruction sources within the skill's read boundaries. Test a fresh root session, a nested start, and a root-started task touching a deeper scope. Use permitted, secret-free loading diagnostics plus a concrete task; an agent reciting a path is weaker evidence than observed loading and correct behavior.

For each test, track the root, transitive imports, scoped files and relevant memory actually loaded. Splitting one eager file into several eager imports does not reduce that total. Count unknown loading as unknown, not zero. Keep logs private and report only instruction provenance.

Shared Markdown links are retrieval pointers, not an automatic loader. Put essential action boundaries in always-available guidance; enforce critical invariants in existing code, tests and permission controls. Changing hooks, global settings or execution permissions is separate from a documentation-only migration.

If a supported client cannot be exercised, leave the explicit-read fallback in place and mark automatic loading unverified for that client. Avoid adding an automation layer solely to hide this uncertainty.
