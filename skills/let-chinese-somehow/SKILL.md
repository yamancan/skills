---
name: let-chinese-somehow
description: Hands a bounded task through Zro to OpenCode on Dolly 1 Security with automatic approvals, then reviews the result. Use only for "let chinese somehow" or an explicit Zro or Dolly 1 Security request.
---

# Let Chinese Somehow

Delegate a bounded task through **Zro → installed OpenCode → `dolly1-security`**. OpenCode does the work; you inspect and verify it.

This route always runs OpenCode with `--auto`: anything not explicitly denied is approved, and your per-command approval rules are not translated, so one launcher approval can allow many commands. An active OS sandbox is inherited. Launch only within the user's task scope and your host's authority.

## First use

- `zro` and `opencode` must already be installed; check their local help. If either is missing, report it with the [Zro CLI](https://zro.moonmath.ai/docs/cli) or [OpenCode installation](https://opencode.ai/docs/) instructions and stop before launching. Never run an installer or add `--install`.
- The user signs in with `zro login` and checks access with `zro models` in their own terminal ([setup and account](references/worker.md#setup-and-account)). `dolly1-security` is required: report missing access, authentication or balance instead of substituting a model. Mention the [release limitation](references/worker.md#release-limitation) when relevant.

## Normal path

1. **Package.** Inspect the working tree and applicable instructions. Write a brief in a permitted private local file: needed context, goal, allowed edits and side effects, constraints and acceptance checks. The worker loads no project or global agent instructions, so put the applicable ones in the brief. Preserve existing edits; use a separate worktree for conflicting concurrent work.
2. **Launch** with `skill_dir` set to this skill's installed directory:

   ```bash
   python3 "$skill_dir/scripts/worker.py" --zro \
     --dir "$task_dir" --brief "$brief_path" --timeout 1800
   ```

   Set `--timeout` for the task (default 30 minutes) and keep your command deadline longer, or run it in the background with a retained handle and poll. Share concise progress. The launcher returns JSON with status, model, exact session, state directory, artifacts and final response.
3. **Inspect.** `finished` is a completed native response; `accepted: false` leaves acceptance to you. Check the actual diff or artifact against the brief and pre-existing changes, and run the acceptance checks yourself. A failure, `running` or `held` state, launched UI or bare exit code is not success; a model mismatch is a failure, never a fallback.
4. **Report** the verified result and remaining limitations.

For a correction, continue the same session: see [follow-up sessions](references/worker.md#follow-up-sessions).

## Hard rules

- Keep keys out of chat, command arguments, briefs and logs; never copy the author's credentials.
- The provider key is in the worker environment, where its tools can read it; native permissions and worktrees are not OS sandboxes. Use a trusted checkout and a user-owned key with suitable quota and scope.
- Preserve stronger host restrictions; report an incompatibility instead of retrying with elevated permissions.
- Stop repeated attempts at the same blocker; never downgrade or switch routes automatically.

## Read when needed

[references/worker.md](references/worker.md): account, release limitation, launcher internals, isolation, state, held cleanup, follow-ups, user-operated terminal.
