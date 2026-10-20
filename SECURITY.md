# Security boundaries

These are local agent instructions and launch helpers. A worker inherits an active OS-level sandbox from its parent process. The calling client's per-command approvals and permission rules are not translated into the worker's own rules. Approving the launcher can therefore allow many downstream tool actions; review the task scope and automatic execution mode before launch. The helpers do not perform automatic elevated retries, install system tools, or authorize publication/deployment of a user's project.

## Accounts and data

Every user supplies their own native account. Authenticate in your own terminal; never paste keys into an agent conversation. No author account, key, private profile, session database or raw review transcript belongs in this repository.

The selected task, brief and files actually read by a worker are sent to its provider. Provider data handling and billing remain subject to the user's account and that provider's terms. A short brief does not technically limit filesystem access.

## Let Chinese workers

The bounded launcher uses a private runtime outside the task checkout, a clean child home/config, a restricted environment, and the selected native authentication entry in memory. It disables external plugins, project OpenCode configuration, personal Claude fallback, external skill discovery, LSP downloads, nested agent tasks and Zro's automatic MCP connection. It pins the route/model and verifies the observed assistant against the exact native session export. It retains private result files for follow-up and inspection.

Default and explicit state paths are checked against the task directory and enclosing Git checkouts, including worktrees. If a host-selected temporary directory falls inside a checkout, the launcher refuses it; select a permitted new `--state-dir` outside the checkout. Native OpenCode/Zro binaries must resolve outside the checkout. Executable and PATH locations are fixed relative to the launcher's original directory before changing the worker directory, and checkout-contained PATH entries are removed. Help and local session exports receive no selected provider authentication. Necessary configuration/inference operations still do. Process inspection uses the filtered PATH with no current-directory fallback; the remaining host tool locations are trusted.

Automatic execution is explicit: the Zro/Dolly skill uses OpenCode `--auto`, and the generic route uses it only when requested. Native read/external-directory rules are defense in depth. Bash, tools and their descendants still have the parent's OS permissions and can inherit the selected provider credential through their environment. Treat this as trusted local code execution, not as a sandbox for hostile repositories or prompts. Do not run untrusted package scripts with production credentials present. Preserve any stronger host or managed policy; report an incompatible policy rather than weakening it.

The launcher bounds execution time and holds a per-state lock. On cancellation/timeout it stops its owned POSIX process group and inspected descendant groups. Native shell commands can use separate groups. If the host blocks descendant inspection, cleanup is marked held; it is not declared complete. Already orphaned or deliberately daemonized processes, and groups created after the inspection snapshot, remain outside the cleanup guarantee. A running/held state requires inspection before another attempt, including after an uncatchable launcher kill. There is no automatic recovery command for these states: after inspecting the old attempt, use a fresh state directory and session. A completed worker response is not parent acceptance: inspect the actual diff and independently check the result.

Long tasks use the host's background/native-session facility with a retained handle and polling. The worker deadline is configurable (30 minutes by default); the outer host deadline must leave time for cleanup. No timer can guarantee progress from a stalled provider, and an elapsed deadline is never reported as successful completion.

The optional interactive `zro launch opencode` command is a separate, user-operated native session. It uses native user configuration and has the upstream adapter's normal MCP/environment behavior; it does not use the isolated bounded launcher profile.

## Duo and Orkestra

Duo's automatic reviewer uses a constrained native tool configuration and a hashed source packet. The packet binds bytes for review; it does not enforce packet-only filesystem reads. A worktree separates edits and is not an OS sandbox. Manual native reopening has different configuration exposure; follow the installed workflow and preserve the recorded session/model.

Packet capture opens path components without following symlinks and reads from the same descriptor it checks. This prevents a concurrent symlink replacement from redirecting the capture to another file; it does not make concurrently edited source an atomic repository snapshot. Pause conflicting writers while preparing a review.

## Telegram Context

The Team skills process one Telegram Desktop JSON export locally. The engine makes no network or model calls; the agent running the skill reads the selected chunks and summaries under its provider's data handling. Packages are lossless and not anonymized: they keep names, IDs and message text. They default to `~/.local/share/telegram-context/packages/`, outside any repository; keep real exports out of this one.

Message text, names and links are untrusted data. Chunks fence them, and rendered Markdown summaries escape HTML and authored links. Version 4 parent inputs (`summaries/*.txt`) hold unescaped model text: read them as plain text and never render them. Package paths reject traversal, symlinks and special files, and file sizes are bounded. See the [workflow reference](plugins/team/skills/telegram-context/references/workflow.md) for limits. Mechanical validation checks preservation and citations, not whether a summary is factually right.

## Local state and publishing

Keep runtime state, credentials, provider output and native sessions outside the repository. Private logs can contain task information even after known-key redaction. Review the exact Git export and its history before making the repository public. Ignore rules are a convenience, not a secret-removal mechanism.

For a suspected leak, revoke the affected credential through its provider and remove sensitive artifacts from the distribution path. Report a vulnerability through GitHub private vulnerability reporting when available. Otherwise contact the maintainer privately; do not open a public issue containing secrets.
