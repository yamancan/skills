# Verification

Supported hosts: macOS/Linux with Python 3.9+. Each independently installed skill includes its own license.

## Run the checks

```bash
python3 -m unittest discover -s tests -v
bash -n skills/duo/scripts/setup.sh
npm ci --ignore-scripts
npm test
```

The Python suite passed on Linux/Python 3.9 and macOS/Python 3.13 during release preparation. Tests live in the repository's `tests/` directory and are excluded from installed skill folders. They cover setup, authentication isolation, session/model verification, private state, deadlines, process cleanup, source capture and workspace lifecycle. The Telegram Context suite uses synthetic conversations only and passed on macOS with Python 3.9.6 and 3.14. It covers lossless chunk round trips, spoofed message lines, pinned version 2/3 chunk bytes, summary dependencies and package file guards.

Skills CLI **1.7.2** discovered and copied all five Coding skills into disposable Claude Code and Codex homes. Both installed collections contained their licenses and no development tests or bytecode. It also discovered all eight skills from the checkout with the Team plugin. A copy install of `tg-summarize` with `telegram-context` into a disposable project for both clients contained licenses and no tests or bytecode; the installed engine prepared and validated a synthetic export through the sibling path on Python 3.9.6.

## Native plugin distribution

The `niche-coding` plugin exposes the same five skill directories through a portable root manifest and a Claude Code compatibility manifest. The shared marketplace uses the repository root; no hooks, MCP servers or automatic setup commands are declared.

Claude Code **2.1.302** and Codex **0.163.0** installed the package in disposable configuration homes. Claude's component inventory reported exactly five skills and zero hooks, agents, MCP or LSP servers. Codex's app-server `skills/list` reported exactly five enabled plugin skills. Both clients namespace plugin skills: `/niche-coding:duo` in Claude Code and `$niche-coding:duo` in Codex; standalone CLI installations retain bare skill names.

Git-backed fixture tests installed version 0.1.0, advanced the source to synthetic version 0.1.1, verified the updated files and sibling Duo/Orkestra helpers, then uninstalled the plugin in both clients. Claude requires refreshing the marketplace before a manual plugin update; Codex refreshed the installed version through marketplace upgrade and a fresh client command. These distribution checks do not run a model task or establish provider entitlement.

The `niche-team` plugin lives in `plugins/team` with the same two manifests. In disposable configuration homes, Claude Code **2.1.304** reported exactly three skills and zero hooks, agents, MCP or LSP servers for `niche-team`, and still five skills for `niche-coding`. Codex **0.163.0**'s app-server `skills/list` reported exactly three `niche-team:` and five `niche-coding:` skills. The Coding plugin's cached repository copy includes `plugins/team`, but Codex does not load those skills under `niche-coding`.

## Install shortcuts

The Node launcher checks skill selection before calling Skills CLI, includes Duo for Orkestra and `telegram-context` for `tg-cleanup` or `tg-summarize`, and rejects unsupported commands and unattended installs without an explicit selection. Its process tests also cover literal arguments without shell execution and preservation of installer failure status. Its only npm runtime dependency is Skills CLI **1.7.2**. The launcher disables installer telemetry by default, including the optional remote audit-card lookup; direct Skills CLI calls need their own `DISABLE_TELEMETRY=1`. A process regression test verifies the child receives the privacy default even when the parent has no opt-out environment variables. The npm package contains the install launcher. The tarball allowlist contains only the launcher, README, license and package metadata; the skills are installed from GitHub by Skills CLI. A real local-tarball invocation discovered all five skills from the renamed repository without installing them in list-only mode.

## Native integration

Tested tools: OpenCode **1.19.3**, Zro **0.2.1**, Claude Code **2.1.302**, and Codex **0.163.0**.

Six synthetic worker calls completed: OpenCode Go and Zro/Dolly tasks from a Codex parent, both exact-session follow-ups, and both routes from fresh Claude Code parents. Parent checks confirmed the intended calculator fix and passing tests. These calls preceded final security hardening; a fresh successful inference after those changes is not claimed.

## Known limits

- **Zro 0.3.0:** launch syntax and the isolated Dolly profile were verified, but coding attempts stalled in the preparation environment. A later Zro 0.3.0 task retry failed in 5.79 seconds with an explicit included-credits-exhausted error. That establishes the blocker for that retry, not the cause of the earlier stalls; successful task completion after final hardening is not verified. No automatic downgrade or model fallback is performed.
- **OpenRouter:** authentication selection is tested offline. The available test account was rejected, so successful live inference is not claimed. Users supply their own valid account and model access.
- Exact-export secret/private-identity scans and reachable-history secret scans found no leaks. Scans and synthetic tests do not prove absence of every vulnerability or compatibility with arbitrary codebases.

Native sessions, raw provider output and private review evidence stay outside the distribution. Read [SECURITY.md](../SECURITY.md) for execution permissions, credential inheritance and cleanup limits.
