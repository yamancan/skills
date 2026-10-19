---
name: let-chinese
description: Hands a bounded coding task to an OpenCode worker on the user's chosen model or a free OpenCode model, then reviews the diff. Use for "let chinese" or OpenCode delegation. Use let-chinese-somehow for "let chinese somehow".
---

# Let Chinese

Package the job. Let OpenCode cook. Inspect what comes back.

You stay responsible for the result. The worker does not widen the user's task or your permissions.

## Route

**Claude Code or Codex → one isolated OpenCode worker → the user's model.**

- Use the model the user names, otherwise their existing choice. Supported: `openrouter/*` and `opencode-go/*` (native API key) and free `opencode/*-free` (no key). With nothing configured, offer `opencode/glm-5.3-flash-free` or have the user connect a provider in their own `opencode` terminal; see [model and setup](references/worker.md#model-and-setup).
- OpenCode must already be installed; this skill never installs it. If it is missing or the route is unavailable, report the blocker with the [installation instructions](https://opencode.ai/docs/).
- Use `let-chinese-somehow` only when the user selects that route.

## Normal path

1. **Package.** Inspect the working tree and repository instructions, and decide which files and checks the task covers. For conflicting concurrent edits, use a separate worktree when permitted. Write a brief in an allowed local path: goal, needed context, working directory, allowed edits and side effects, constraints, acceptance criteria and required verification.
2. **Launch** one worker in the intended checkout, with `skill_dir` set to this skill's installed directory:

   ```bash
   python3 "$skill_dir/scripts/worker.py" \
     --model "$model_id" --dir "$task_dir" --brief "$brief_path" --timeout 1800
   ```

   Set `--timeout` for the task (default 30 minutes) and keep your command deadline longer, or run it in the background with a retained handle and poll. Share progress. The launcher returns JSON with `status`, `model`, `session`, `state_dir`, artifacts and `final_response`.
3. **Inspect.** `finished` means a completed native response with session and model proof; `accepted: false` means acceptance is yours. Check the diff or artifact against the brief and pre-existing changes, and run the checks that prove completion yourself. A timeout, error, `held` result or bare successful exit is not success.
4. **Report** what changed, what you verified and what is still blocked.

For a correction, continue the same session: see [follow-up sessions](references/worker.md#follow-up-sessions).

## Hard rules

- Keep credentials out of the brief, arguments, repository, chat and displayed output.
- The worker is not an OS sandbox: its shell and tools keep your OS access and the selected key. Review the delegated scope before approving the launch, use a trusted checkout, and stop on a policy incompatibility. Add `--auto` only when the user explicitly asks.
- Never retry with elevated permissions to escape your host's restrictions.

## Read when needed

[references/worker.md](references/worker.md): setup, isolation, state, held cleanup, follow-ups, provider failures, displayed output, interactive terminal.
