# Let Chinese worker reference

Read the section you need. The normal path is in [SKILL.md](../SKILL.md).

## Model and setup

- Resolve the exact model ID as `model_id`: the one the user names, otherwise their existing OpenCode choice. Keep their startup defaults unchanged.
- No model configured: offer a free OpenCode Zen model such as `opencode/glm-5.3-flash-free`. It needs only OpenCode, with no account or key. `opencode models opencode` lists the current `-free` models; free availability can end.
- Paid route: the user opens `opencode` in their own terminal, connects a provider with `/connect` and selects a model with `/models`. The worker supports native API authentication for `openrouter/*` and `opencode-go/*`; custom provider configuration and OAuth are unsupported. No separate credential store is needed.
- The launcher checks OpenCode's native CLI flags and reads only the selected provider's native authentication entry, in memory.
- When installed help does not settle invocation or continuation syntax, consult the [OpenCode CLI reference](https://opencode.ai/docs/cli/).

## Isolation and its limits

The launcher gives the worker a clean home, config and runtime. It disables personal and project OpenCode config, external plugins and skills, the personal Claude fallback and MCP, and strips unrelated environment secrets.

It is not an OS sandbox. Bash and child tools keep the parent's OS access, the selected authentication is present in the worker environment, and the parent's per-command approval rules are not translated into OpenCode rules. The worker reports back to you and does not launch other agents.

## State directory

- State defaults to a private temporary directory outside the checkout. Preserve the returned `state_dir` for follow-ups; OS cleanup or a reboot can remove temporary state.
- For durable state, pass a new permitted private `--state-dir` outside the checkout.
- If the host's temporary directory is inside an enclosing checkout, the launcher refuses it before writing runtime files. Pass an explicit permitted `--state-dir` outside that checkout and keep the host's restrictions.

## Timeouts and held cleanup

The launcher disconnects worker stdin, captures output privately and bounds execution. Keep the outer host deadline longer than the worker timeout plus cleanup grace. A timeout, error or `held` result is not success. Inspect a held cleanup before any retry.

## Follow-up sessions

For a correction, rerun the launcher with the same model, checkout, approval mode and original `--state-dir`, add `--session` with the returned exact ID, and give a focused new brief. The launcher rejects mismatched, stale or concurrently used state. A failed provider session may need a fresh run after account repair; stop repeated attempts at the same blocker.

## Provider failures

On an authentication, balance or model-access failure, report the provider and the error. The user repairs the account through the provider's normal login flow; keys stay out of chat. Resume the requested route once it works.

## Displayed output

From the JSON output, show text, tool summaries and the error status and message fields you need. Omit authentication, cookies, response headers and full configuration dumps.

## Interactive terminal

Only when the user explicitly asks for a terminal they operate, open native `opencode --model "$model_id"` in the selected directory. It loads their native configuration and is separate from the isolated launcher. Opening it does not complete a delegated task.
