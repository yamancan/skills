---
name: let-chinese-somehow
description: Use when the user says "let chinese somehow" or explicitly asks to delegate through Zro/Moonmath with Dolly 1 Security and OpenCode auto approvals. Regular "let chinese" uses the separate OpenCode skill.
---

# Let Chinese Somehow

Delegate a bounded task through **Zro → installed OpenCode → `dolly1-security`**. OpenCode does the work; the current agent inspects and verifies it.

This route uses OpenCode's `--auto`: permissions not explicitly denied are automatically approved. Respect the user's task scope and launch only within the host's authority. An active OS sandbox is inherited, but the parent's per-command approvals and permission rules are not translated into OpenCode rules. Approving this launcher can allow many downstream commands; a different model or approval mode does not authorize actions outside the user's task.

## First use

- Check that `zro` and `opencode` are installed and inspect their local help. This skill launches existing tools. If either is missing, report the prerequisite and link the [Zro CLI](https://zro.moonmath.ai/docs/cli) or [OpenCode installation](https://opencode.ai/docs/) instructions. Stop before launching; do not run an installer or add `--install` automatically.
- The user signs in through `zro login` in their own terminal. For a new account, offer [Yaman's referral signup link](https://zro.moonmath.ai/?ref=ZROSLWMI), disclosed as a referral; credit depends on a qualifying paid subscription. Existing accounts can use native login directly.
- Let the user check access through `zro models` in their terminal. Require `dolly1-security`; report unavailable access, authentication or balance instead of substituting a model. Native login stores the user's credential outside the repo. Keep keys out of chat, command arguments, briefs and logs; never copy the author's credentials.

Release limitation: completed native task tests used Zro 0.2.1. Zro 0.3.0 resolved the correct model/profile but coding attempts stalled in the preparation environment; its task completion remains unverified. Report this when relevant, stop repeated attempts at the same blocker, and do not downgrade or switch routes automatically.

## Launch

For a user-operated terminal, launch in the intended project directory:

```bash
zro launch opencode --model dolly1-security -- --auto --model zro/dolly1-security
```

The first model flag selects Zro's model. After `--`, the flags belong to OpenCode: the second model flag pins the actual worker model even when project configuration has another default. `--auto` belongs on that OpenCode side.

The command above opens a user-operated UI with the upstream adapter's native config/MCP behavior. Opening it is not a completed delegated task. For the normal agent-to-worker path below, use the bundled isolated launcher.

Inspect the working tree and applicable instructions, then write a brief in a permitted private local file containing only the necessary context, goal, allowed edits and side effects, constraints and acceptance checks. Preserve existing edits; use a separate worktree for conflicting concurrent work. The worker intentionally does not auto-load project/global agent instructions; include the applicable instructions in this reviewed brief.

Resolve this skill's installed directory as `skill_dir`, then launch:

```bash
python3 "$skill_dir/scripts/worker.py" --zro \
  --dir "$task_dir" --brief "$brief_path" --timeout 1800
```

The helper launches native `zro launch opencode --model dolly1-security -- run … --auto --model zro/dolly1-security` in the selected checkout, checks CLI flags and verifies the actual assistant model against the native session export. It never substitutes another model or installs tools. Zro's `--json` means dry run and is not used for worker output.

Choose the deadline for the task; the default is 30 minutes and `--timeout` can be raised deliberately for longer work. Keep the outer host deadline longer than the worker timeout plus cleanup grace. When the host's synchronous wait limit is shorter, use background/native-session execution, retain the process handle and poll until completion. Surface concise progress. The helper disconnects worker stdin, uses private files and a timeout, and stops inspected owned processes on timeout/cancellation. It returns JSON containing status, model, exact session, state directory, artifacts and final response. `finished` is a completed native response; `accepted: false` leaves artifact/test acceptance to the parent. A failure, `running` or `held` state is not success. Inspect an interrupted/held cleanup before any retry. Sandboxes may prevent inspection of separate native shell groups; cleanup is then held. Already orphaned daemons remain outside the cleanup guarantee.

The helper reads the user's native Zro authentication in memory, then uses a clean home/XDG profile, disables personal/project config, external plugins/skills, personal Claude fallback, nested agent tasks and Zro MCP, and strips unrelated environment secrets. The selected provider key is still in the worker environment and can be inherited by its tools. Native permissions and worktrees are not OS sandboxes. Use a trusted checkout and a user-owned key with suitable quota/scope; preserve stronger host restrictions and report incompatibility rather than retrying elevated.

Runtime state defaults to a private temporary directory outside the task checkout. Preserve its returned path; OS cleanup/reboot can remove it. For durable state pass a new permitted `--state-dir` outside the checkout. Logs/session text are private task data, never release files.

If the host's temporary directory is inside an enclosing checkout, the helper refuses it before writing runtime files. Choose an explicit permitted `--state-dir` outside that checkout; keep the host's restrictions.

## Receive and verify

Inspect the actual diff or artifact against the brief and pre-existing changes. Run the relevant acceptance checks yourself. A launched UI or exit code alone is not task completion.

For corrections, rerun this helper with `--zro`, the same checkout, the original `--state-dir`, the returned exact `--session` and a focused new brief. It rejects route/model/state mismatches and concurrent use. Failed provider sessions may require a fresh run after account repair; stop repeated attempts at the same blocker. Report the verified result and remaining limitations. Model mismatch is a failure, never a fallback.

References: [Zro CLI](https://zro.moonmath.ai/docs/cli), [Dolly 1 Security](https://zro.moonmath.ai/docs/models/dolly1-security), [OpenCode CLI](https://opencode.ai/docs/cli/).
