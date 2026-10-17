# Install and choose models

Read on first use, missing Python/CLI/account prerequisites, profile selection or model updates. Python **3.9+**, macOS/Linux and standard library only. Preserve existing `CODEX_HOME`, `CLAUDE_CONFIG_DIR` and the same `DUO_STATE_DIR` across callers. Native CLIs own credentials and account login.

## Entry points

From the cloned niche-skills repository:

```bash
bash install.sh --skill duo
bash install.sh --skill orkestra
bash install.sh --skill duo --check
```

The installer links both clients and includes Duo when installing Orkestra. Both installed skill directories must share the same parent: Orkestra imports Duo helpers and links to its references. With another skill manager, install both `duo` and `orkestra`. This release provides the normal Orkestra profile; Light is deferred.

Native config homes select install destinations, with `SKILLS_INSTALL_HOME` as the fallback for default homes. `--no-setup` only links skills. A noninteractive install prints a shell-quoted setup command for the user's terminal.

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
