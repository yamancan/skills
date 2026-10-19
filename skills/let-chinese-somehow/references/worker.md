# Let Chinese Somehow worker reference

Read the section you need. The normal path is in [SKILL.md](../SKILL.md).

## Setup and account

- The user signs in through `zro login` in their own terminal. Native login stores the credential outside the repo. Existing accounts use native login directly.
- For a new account, offer [Yaman's referral signup link](https://zro.moonmath.ai/?ref=ZROSLWMI), disclosed as a referral; credit depends on a qualifying paid subscription.
- `zro models` in the user's terminal shows whether `dolly1-security` is available.

## Release limitation

Completed native task tests used Zro 0.2.1. Zro 0.3.0 resolved the correct model and profile, but coding attempts stalled in the preparation environment; a later retry returned an explicit credits-exhausted error. Successful task completion after final hardening remains unverified. Report this when relevant, stop repeated attempts at the same blocker, and do not downgrade or switch routes automatically.

## What the launcher runs

The launcher runs native `zro launch opencode --model dolly1-security -- run … --auto --model zro/dolly1-security` in the selected checkout, checks CLI flags and verifies the actual assistant model against the native session export. It never substitutes another model or installs tools. Zro's `--json` means dry run, so it is not used for worker output.

## Isolation and its limits

The launcher reads the user's native Zro authentication in memory, then uses a clean home and XDG profile. It disables personal and project config, external plugins and skills, the personal Claude fallback, nested agent tasks and Zro MCP, and strips unrelated environment secrets.

The selected provider key is still in the worker environment and can be inherited by its tools. Native permissions and worktrees are not OS sandboxes.

## State directory

- Runtime state defaults to a private temporary directory outside the task checkout. Preserve its returned path; OS cleanup or a reboot can remove it.
- For durable state, pass a new permitted `--state-dir` outside the checkout.
- If the host's temporary directory is inside an enclosing checkout, the launcher refuses it before writing runtime files. Pass an explicit permitted `--state-dir` outside that checkout and keep the host's restrictions.
- Logs and session text are private task data, never release files.

## Timeouts and held cleanup

The launcher disconnects worker stdin, uses private files and a timeout, and stops inspected owned processes on timeout or cancellation. Keep the outer host deadline longer than the worker timeout plus cleanup grace. Inspect an interrupted or held cleanup before any retry. A sandbox may prevent inspection of separate native shell groups; cleanup is then held. Already orphaned daemons are outside the cleanup guarantee.

## Follow-up sessions

For a correction, rerun the launcher with `--zro`, the same checkout, the original `--state-dir`, the returned exact `--session` and a focused new brief. It rejects route, model or state mismatches and concurrent use. A failed provider session may need a fresh run after account repair; stop repeated attempts at the same blocker.

## User-operated terminal

For a terminal the user operates, launch in the intended project directory:

```bash
zro launch opencode --model dolly1-security -- --auto --model zro/dolly1-security
```

The first model flag selects Zro's model. After `--`, the flags belong to OpenCode: the second model flag pins the actual worker model even when project configuration has another default, and `--auto` belongs on that side. This UI uses the upstream adapter's native config and MCP behaviour. Opening it is not a completed delegated task; for the agent-to-worker path, use the bundled launcher.

## Links

[Zro CLI](https://zro.moonmath.ai/docs/cli), [Dolly 1 Security](https://zro.moonmath.ai/docs/models/dolly1-security), [OpenCode CLI](https://opencode.ai/docs/cli/).
