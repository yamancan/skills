# Install and choose models

Read on first use, missing Python/CLI/account prerequisites, profile selection or model updates. Python **3.9+**, macOS/Linux and standard library only. Preserve existing `CODEX_HOME`, `CLAUDE_CONFIG_DIR` and the same `DUO_STATE_DIR` across callers. Native CLIs own credentials and account login.

## Entry points

After Skills CLI installation, resolve this skill's actual installed directory as `skill_dir`; a repository clone is not required. Run the read-only check with `python3 "$skill_dir/scripts/setup_models.py" --check --profile duo` (or `normal` for Orkestra). For missing selections or account setup, give the user a shell-quoted command using `bash` followed by the resolved absolute path to `scripts/setup.sh` and the chosen profile, to run in their own interactive terminal. Preserve the active native config homes and shared state directory. Never leave `$skill_dir` or a placeholder in the command shown to the user. The script's noninteractive output prints a concrete continuation command if a host cannot supply terminal input.

Orkestra requires both `duo` and `orkestra` installed into the same scope and agents, with sibling skill directories. A global installation is recommended to keep a single version against the per-user task index. Install/update them together:

```bash
npx yamancan/skills --skill orkestra -a claude-code -a codex -g
npx skills@latest update duo orkestra -g
```

For project installations omit `-g` on installation and use `-p` on update; keep versions aligned across projects. Choose one scope per skill and agent. This release provides the normal Orkestra profile; Light is deferred.

Keep Skills CLI's recommended symlink method so agent directories share a canonical copy. With independent `--copy` installs, Skills CLI 1.7.2 updates run from inside an agent can leave the other agent's copy stale. Refresh both explicitly by rerunning the `add` command above with `--copy` and the same skill selection/scope. For project installs omit `-g`. Review local edits before replacement.

The repeatable `scripts/setup.sh [duo|normal] [ROLE=MODEL:EFFORT ...]` script has two stages: edit and confirm model/effort choices, then sign in through the native account flow if needed. Enter keeps a displayed choice; command-line overrides prefill those choices. Preferences go to the private shared `models.json`, outside the skill source. The script never asks for account secrets, installs system binaries, edits native model settings or creates provider review sessions. The two-stage flow was inspired by [Matt Pocock's Wizard skill](https://github.com/mattpocock/skills/tree/main/skills/engineering/wizard); the distributed script is purpose-built for native CLI setup.

If a CLI is missing, follow its [Codex installation](https://developers.openai.com/codex/cli/) or [Claude installation](https://code.claude.com/docs/en/setup) instructions. Installation, native login, model entitlement and live compatibility are distinct checks.

## Role defaults

[models.json](models.json) is the dated candidate roster, recorded **2026-10-08**. It is guidance for user selection, not an account-access guarantee or a promise that the same version remains latest. `setup_models.py --check --profile PROFILE` reports saved selections or candidates and local CLI presence without executing CLIs, writing state or contacting providers. Before using defaults for a new task, inspect this report. Run setup if the profile is unconfigured.

| Profile / role | Candidate model | Effort |
| --- | --- | --- |
| Duo code owner / Codex peer | `gpt-6.1-sol` | `xhigh` |
| Duo Opus peer | `claude-opus-5-5` | `xhigh` |
| Normal builder / reviewer | `gpt-6.1-sol` | `xhigh` |
| Normal unresolved-design Astra / Fable | `gpt-6-astra` / `claude-fable-5-1` | `xhigh` |
| Normal paired-review Opus | `claude-opus-5-5` | `xhigh` |

Saving normal also selects its Codex and Opus **model IDs** for future Duo tasks. Duo's transport requests **xhigh** on both seats even if another effort is selected for the normal build/design roles; the setup report states this before confirmation. Existing tasks retain their pinned models. An older saved normal profile gains the missing Opus candidate without changing its other choices; inspect and confirm it during setup.

Orkestra reads saved normal selections before dispatch and applies actual host/CLI controls. Explicit user choices override named rows. The pair helper supports read-only Codex/Opus at xhigh; builders and Astra/Fable roles use supported host tools. Model preferences never change an active owner or existing native session: apply an owner selection through its host.

## Explicit updates

Check current official model documentation and account/host availability first. Use a versioned model ID; mutable `opus`/`latest` aliases cannot pin future conversations. Preserve workload roles and spending limits. Update a future-task choice without editing existing tasks:

```bash
python3 /absolute/duo/scripts/setup_models.py --profile normal --save \
  --set codex=gpt-6.1-sol:xhigh --set opus=claude-opus-5-5:xhigh
```

`--set` with `--check` previews without saving. Setup reruns preserve existing selections and other profiles, apart from the explicit normal-to-Duo bridge above. A direct `init/fork` uses saved Duo defaults only when explicit peer-model flags are absent. Changes never rewrite pairs, native transcripts, task IDs or active models. Existing task initialization refuses a different peer model. An intentional model migration needs a separate context with parent/reason evidence and renewed review; a changed default alone is not a reason to fork.

Effort scales and CLI support differ by model and route. Record requested and observed model/provider/effort separately; unknown effective metadata stays unknown. Claude managed caps can clamp requested effort in JSON mode. Max/ultra are deliberate escalations within a supported route. Real start and exact-resume checks establish native compatibility only when performed within actual spending authority; the local setup report makes no live provider call.

Sources for model/route verification: [OpenAI models](https://developers.openai.com/api/docs/models), [Claude models](https://platform.claude.com/docs/en/about-claude/models/overview), [Claude effort and caps](https://code.claude.com/docs/en/model-config).
