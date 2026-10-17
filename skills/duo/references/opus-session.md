# Paired sessions

The active tool owns dispatch. Codex calls the selected Opus through Claude Code; Claude/Opus calls the selected Codex through Codex CLI. Both request xhigh. Requested effort is not proof of effective effort: managed Claude effort caps can clamp JSON calls silently; report unobserved runtime metadata as unknown. Before creating a record or returning in another chat, read [conversation lifecycle](conversations.md) for discovery, explicit handoff, managed manual resume and acknowledged sync. The peer returns findings to the owner without recursive delegation. Check installed CLI help when the route changes.

## Pair and dispatch

Launch the peer from the owner's current project/worktree directory. `init` inherits its caller's working directory by default; an explicit legacy `--workdir` may only assert that same directory. Start and resume from it. Do not hardcode a project path, infer it from the skill's install location, switch to a temporary prompt/snapshot directory, or silently climb to another repository root. A review packet's location does not choose the session's project. This preserves the native CLI's project association; resume the recorded workdir and exact peer ID.

The lifecycle reference owns discovery, native homes, identity, handoff, sync and manual locking. Keep its canonical pair/results outside disposable worktrees. Obtain the real owner ID from trusted metadata: Codex exposes `CODEX_THREAD_ID`; Claude uses SessionStart hook metadata or its controller-assigned `--session-id`. If unknown, stop binding rather than inventing an ID. Caller claims are not authenticated by this helper.

The helper inherits the caller directory at `init`, then requires that recorded workdir at dispatch. Models can be explicit flags as below or saved Duo selections from [setup](setup.md); changing defaults never changes an existing pair. Replace example paths/models/IDs:

```bash
# Codex owns the task; Opus is its peer. --owner codex is the default.
python3 /path/to/duo/scripts/pair.py init --owner codex \
  --pair /private/task/pair.json --thread "$CODEX_THREAD_ID" \
  --task "Registration repair" \
  --opus-model claude-opus-5-5
python3 /path/to/duo/scripts/pair.py run --owner codex \
  --pair /private/task/pair.json --thread "$CODEX_THREAD_ID" \
  --task-id TASK_ID_RETURNED_BY_INIT \
  --prompt /private/task/brief.md --snapshot COMMIT_SHA_OR_DIFF_ID \
  --packet /private/task/FROZEN_PACKET/manifest.json

# Claude/Opus owns the task; Codex is its peer.
python3 /path/to/duo/scripts/pair.py init --owner claude \
  --pair /private/task/reverse.json --thread ACTUAL_CLAUDE_SESSION_ID \
  --task "Registration repair" \
  --codex-model SELECTED_CODEX_MODEL
python3 /path/to/duo/scripts/pair.py run --owner claude \
  --pair /private/task/reverse.json --thread ACTUAL_CLAUDE_SESSION_ID \
  --task-id TASK_ID_RETURNED_BY_INIT \
  --prompt /private/task/brief.md --snapshot COMMIT_SHA_OR_DIFF_ID \
  --packet /private/task/FROZEN_PACKET/manifest.json
```

Repeat `run` for focused follow-ups after reconciling unread native changes. Opus starts with a preallocated UUID via `--session-id`, then uses `--resume` with that UUID. Codex starts with `exec --json`, stores its returned `thread.started` ID, then uses `exec resume EXACT_ID --json`. Never select `--last` or `--continue`. Adopt older records in place and sync/ack their existing history before continuing.

Opus needs writable native session storage (`CLAUDE_CONFIG_DIR`, otherwise `~/.claude`) even when its review tools are read-only. The helper pins that resolved directory, probes actual write access before calling Claude, and checks the existing conversation before resuming. A preflight failure starts no peer; correct the prerequisite through the host's authorized execution path and retry. The helper never grants permissions, copies credentials, or changes the selected account. Keep the same state directory for this pair.

After a successful Claude response, the helper requires a new assistant message in that exact session's native JSONL transcript matching the returned text. Codex requires matching session/completion events plus newly persisted assistant text in its exact native transcript. An old transcript or metadata-only update cannot establish success. This verifies persisted response evidence without an extra model call; a real start/resume test verifies CLI compatibility. A transcript format the helper cannot verify leaves the call held. Both native state directories are pinned; missing history refuses a resumed call.

The helper validates ownership/workdir/route, serializes calls and retains stdout/stderr. Default timeout is 300 seconds; justify a longer `--timeout`. A launched failure, interruption, wrong session or missing persisted answer leaves the pair held. SIGINT/SIGTERM/SIGHUP and timeout stop its tracked process group; SIGKILL/host failure may leave it running. Inspect saved output, native history and processes before recovery; never reset or replace unresolved work automatically. See [lifecycle](conversations.md) for acknowledgement and manual use.

When the Claude owner uses Bash, set that tool's timeout longer than the helper's (for example Bash `timeout: 360000` with helper `--timeout 300`, or background it and track completion). The default Bash timeout can otherwise end the parent before cleanup. Likewise keep a Codex owner's outer command timeout above the helper's. Do not reset a held pair merely because the terminal ended.

An interrupted first call can leave a native transcript while `started` is still false. Restoring only `ready` would try to create that UUID again; the helper refuses this. Inspect process state and history before recovery. A transcript containing only tool exchanges may require a supervised native `--resume EXACT_ID` while the pair remains held; acquire the same canonical pair's `.lock` with Python `fcntl.flock(LOCK_EX | LOCK_NB)`. Preserve the helper's peer arguments: pinned model, `--effort xhigh`, `--safe-mode`, `--tools Read,Grep,Glob`, `--strict-mcp-config` with empty MCP config, and `-p --output-format stream-json --verbose`; run from the recorded workdir under the pinned Claude config directory. Mark it started/ready only after a completed response is verified in that same transcript. Keep corrupt or truncated JSONL blocked with an inspection error; never silently discard native history to make a check pass.

Automated Opus reviewers use `--safe-mode`, Read/Grep/Glob and strict empty MCP configuration. Native CLI documentation describes safe mode as disabling customizations while retaining authentication and permissions, including managed policy; the helper does not independently enforce every native account/permission configuration. Global configuration is not edited. Put applicable repository instructions, user constraints and required context in the review packet/brief rather than relying on the reviewer's personal plugins. A custom route or unsupported CLI flag requires an explicit compatibility repair, not silent substitution. Managed hooks can still affect startup. Interactive manual seats retain their documented native configuration and may behave differently.

Read/Grep/Glob restrict available tool types, not readable filesystem paths. Neither that allowlist nor a verified packet provides packet-only OS isolation: either reviewer can read other files allowed by its native host permissions. Use host-enforced read boundaries when that isolation is required; source hashes establish byte identity rather than access containment.

Resuming an older session retains plugin text already present in its history. Safe mode does not erase that context; deliberately fork a fresh reviewer when isolation from prior custom instructions is part of acceptance.

Claude output uses `stream-json --verbose`, retaining init, tool and completed-message progress in private mode-600 files. Token-level partial events are omitted; they duplicate content the helper does not consume. Inspect event types, tool names and native history for progress; keep content, thinking and credentials private. New dispatches require exactly one initialization reporting the pinned session/model, only Read/Grep/Glob, no MCP servers and no bypass-permissions mode. The helper retains reported API-key source and permission mode as runtime evidence, not proof of account identity or every policy rule. Only one completed result matching the exact native session and newly persisted answer counts as success. A stream initialization, tool read or partial message is not a completed review. Stored result paths remain inspectable; new dispatches accept the validated JSONL event stream.

Before trusting a new host/route, use a synthetic denied-file canary within actual authority. On Claude Code 2.1.302, a per-invocation `permissions.deny` rule under safe mode was observed to deny Read while preserving the first-party OAuth route; this did not test all user-file or managed-policy configurations. Never put real secrets in a canary or change global policy just to make a test pass.

The 300-second deadline is a wall-clock limit, not proof of a hung model. Inspect progress, native history and cleanup, then narrow the missing deliverable. Use the supervised exact-session recovery above; preserve history and held state until its completion is verified.

Codex uses read-only sandbox, approval policy never, and `--ignore-user-config`; existing account authentication remains available, while custom providers/profiles/MCP are not inherited. The helper does not bypass permissions, authenticate the caller or enforce financial budgets. For source review, prepare and pass the manifest from [workspace lifecycle](workspaces.md); the helper verifies those selected bytes before/after dispatch. A legacy snapshot label alone remains unverified. The owner supplies actual IDs, complete required source coverage, its own xhigh configuration and authorized source/financial scope.

The first brief carries stable scope, decisions, allowed files and acceptance. Follow-ups carry changed evidence. Keep one code owner. Isolate overlapping writes with worktrees or serialize pairs; pairing is not file isolation. A fresh-context review uses an explicit `fork` while retaining earlier evidence.

For an extensive implementation plan, avoid one call that embeds a large source packet and demands the entire detailed plan at xhigh. Ask for a bounded outline from the compact contracts/ownership map, then source-grounded sections with relevant frozen inputs, then a dependency/coverage check in the same exact session. Set a justified per-call `--timeout` and an outer deadline longer than it. A higher timeout alone is not a recovery strategy; after timeout inspect the held call and native history, then narrow the missing deliverable before resuming. Do not treat streamed thinking, a partial section or a successful CLI exit without a persisted answer as completed planning.

## Find and resume

Follow [conversation lifecycle](conversations.md) to discover the canonical task, inspect its seats, transfer ownership explicitly, and reconcile native history. The checkpoint stores the same canonical path and task ID. Missing/ambiguous records or history require resolution before dispatch, not a replacement pair.

Native history and picker visibility are separate. Claude intentionally omits `-p` and Agent SDK sessions from its picker and interactive `--continue`, even when named; exact-ID resume still opens them. Codex's terminal picker includes `exec` sessions with `codex resume --include-non-interactive`; this does not establish desktop sidebar visibility. Keep original source metadata and report what was tested. See [Claude session management](https://code.claude.com/docs/en/sessions).

Cache expiry affects reuse of computation rather than retained conversation history.

## Long-running terminal sessions

When available, tmux can keep the dispatcher alive across terminal disconnections. Name the session after the pair ID and reattach; keep manual peer invocations out of an active helper-managed pair. Tmux does not extend cache TTL or survive host shutdown. If unavailable, use normal provider session persistence and disclose that tmux is missing.

## Opus cache

Claude Code manages caching automatically. Keep model, effort, tools and shared prefix stable. Resume preserves history; cache hits additionally require a matching prefix within TTL. Review the current snapshot rather than assuming earlier code is current. Compaction rebuilds caching.

Default main-conversation TTL is one hour within Claude subscription usage and five minutes for API/usage-credit billing. Retain defaults unless an authorized change has demonstrated benefit; avoid paid keepalive calls. Check `cache_read_input_tokens` and `cache_creation_input_tokens` in usage metadata. Report unavailable telemetry rather than claiming a cache hit from session reuse alone.

Sources: [Claude caching](https://code.claude.com/docs/en/prompt-caching), [Claude CLI](https://code.claude.com/docs/en/cli-reference), [effort](https://platform.claude.com/docs/en/build-with-claude/effort). For Codex, check installed `codex exec --help` and `codex exec resume --help` before changing command flags.
