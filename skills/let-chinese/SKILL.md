---
name: let-chinese
description: Use when the user says "let chinese", "let the Chinese one handle this", or asks OpenCode to do a bounded task while the current agent reviews it. Uses the user's chosen provider and model; "let chinese somehow" selects the separate Zro skill.
---

# Let Chinese

Package the job. Let OpenCode cook. Inspect what comes back.

You remain responsible for the result. OpenCode is the worker, not a way to expand the user's task or your execution permissions.

## Route

Route: **Claude Code or Codex → a bounded OpenCode worker → the user's chosen provider/model**.

Use an explicitly requested model, otherwise resolve the user's existing choice. If none is configured, offer a free OpenCode Zen model such as `opencode/glm-5.3-flash-free`, which needs no account or key; `opencode models opencode` lists the current `-free` models, and free availability can end. Otherwise have the user open `opencode` in their own terminal, connect a provider through `/connect`, and select a model through `/models`. This release's isolated worker supports native API authentication for `openrouter/*` and `opencode-go/*`, and free `opencode/*-free` models without authentication. Resolve the exact ID as `model_id`; custom provider configuration and OAuth are unsupported. No separate credential store is needed.

This skill launches OpenCode; it does not install it. If missing, report the prerequisite with the [official installation instructions](https://opencode.ai/docs/). If the selected route is unavailable, report the blocker. Keep startup defaults unchanged and use the separate `let-chinese-somehow` skill only when the user selects that route.

## Package and dispatch

1. Inspect the working tree and applicable repository instructions. Decide which files and checks belong to the delegated task. For conflicting concurrent edits, use a separate worktree when permitted.
2. Write a brief in an allowed local path with the goal, necessary context, working directory, allowed edits and side effects, constraints, acceptance criteria, and required verification. Give the worker only the context needed for this job.
3. Resolve this skill's installed directory as `skill_dir`; use its bundled standalone launcher. It checks native CLI flags and uses only the selected provider's native authentication entry in memory. Keep credentials out of the brief, arguments, repository and displayed output.
4. Launch one worker in the intended checkout:

   ```bash
   python3 "$skill_dir/scripts/worker.py" \
     --model "$model_id" --dir "$task_dir" --brief "$brief_path" --timeout 1800
   ```

   Substitute actual paths and the selected model. Choose the deadline for the task; the default is 30 minutes and `--timeout` can be raised deliberately for longer work. Keep the outer host deadline longer than the worker timeout plus cleanup grace. Use the host's background/native-session execution with a retained handle when its synchronous wait limit is shorter; poll until the worker completes and keep the user informed. The launcher disconnects worker stdin, captures private output, bounds execution and returns JSON with `status`, `model`, exact `session`, `state_dir`, artifacts and `final_response`. `finished` means a completed native response with session/model proof; `accepted: false` means parent inspection is still required.

The launcher uses a clean home/config/runtime, disables personal/project OpenCode config, external plugins/skills, personal Claude fallback and MCP, and strips unrelated environment secrets. Native permissions are not an OS sandbox: bash and child tools retain the parent's OS access and the selected authentication is present in the worker environment. The parent's per-command approval rules are not translated into OpenCode rules. Review the delegated scope before approving the launcher, use a trusted checkout and stop on a policy incompatibility. Add launcher `--auto` only when explicitly requested.

State defaults to a private temporary directory outside the checkout. Preserve the returned directory for follow-up; an OS cleanup/reboot can remove temporary state. For durable state choose a new permitted private `--state-dir` outside the checkout. A timeout, error or `held` result is not success. Inspect a held cleanup before any retry; do not use an elevated retry to escape the calling client's restrictions.

If the host's temporary directory is inside an enclosing checkout, the helper refuses it before writing runtime files. Choose an explicit permitted `--state-dir` outside that checkout; keep the host's restrictions.

Keep model sessions under the parent's control: the worker reports back rather than recursively launching other agents. Share progress while the worker runs. In JSON output, show text, tool summaries, and necessary error status/message fields; omit authentication, cookies, response headers, and full configuration dumps.

## Receive and inspect

- Inspect the resulting diff or artifact against the brief and pre-existing changes. Check the reported verification and run the checks needed to establish completion yourself.
- For a correction, rerun the launcher with the same model, checkout, approval mode and original `--state-dir`, adding `--session` with the returned exact ID and a focused new brief. The launcher rejects mismatched, stale or concurrently used state. Failed provider sessions may require a fresh run after account repair; stop repeated attempts at the same blocker.
- On authentication, balance, or model-access failure, report the provider and error. Request account repair through the provider's normal login flow; keep keys out of chat. Resume the requested route after it becomes usable.
- Report what changed, what you verified, and anything still blocked. A launched process, prepared file, or successful exit alone does not prove the task is complete.

Current CLI reference: [OpenCode CLI](https://opencode.ai/docs/cli/). Consult it when installed help does not resolve invocation or continuation syntax.

For an explicitly requested user-operated terminal, open native `opencode --model "$model_id"` in the selected directory. This interactive mode loads native user configuration and is separate from the isolated launcher; opening the UI is not a completed delegated task.
