# Verification

Supported hosts: macOS/Linux with Python 3.9+. Each independently installed skill includes its own license.

## Run the checks

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh skills/duo/scripts/setup.sh
```

All **185 tests passed** on Linux/Python 3.9 and macOS/Python 3.13 during release preparation. Tests live in the repository's `tests/` directory and are excluded from installed skill folders. They cover setup, authentication isolation, session/model verification, private state, deadlines, process cleanup, source capture and workspace lifecycle.

Skills CLI **1.7.2** discovered and copied all five skills into disposable Claude Code and Codex homes. Both installed collections contained their licenses and no development tests or bytecode.

## Native integration

Tested tools: OpenCode **1.19.3**, Zro **0.2.1**, Claude Code **2.1.302**, and Codex **0.163.0**.

Six synthetic worker calls completed: OpenCode Go and Zro/Dolly tasks from a Codex parent, both exact-session follow-ups, and both routes from fresh Claude Code parents. Parent checks confirmed the intended calculator fix and passing tests. These calls preceded final security hardening; a fresh successful inference after those changes is not claimed.

## Known limits

- **Zro 0.3.0:** launch syntax and the isolated Dolly profile were verified, but coding attempts stalled in the preparation environment. A later Zro 0.3.0 task retry failed in 5.79 seconds with an explicit included-credits-exhausted error. That establishes the blocker for that retry, not the cause of the earlier stalls; successful task completion after final hardening is not verified. No automatic downgrade or model fallback is performed.
- **OpenRouter:** authentication selection is tested offline. The available test account was rejected, so successful live inference is not claimed. Users supply their own valid account and model access.
- Exact-export secret/private-identity scans and reachable-history secret scans found no leaks. Scans and synthetic tests do not prove absence of every vulnerability or compatibility with arbitrary codebases.

Native sessions, raw provider output and private review evidence stay outside the distribution. Read [SECURITY.md](../SECURITY.md) for execution permissions, credential inheritance and cleanup limits.
