# Niche Skills

Coding skills for Claude Code and Codex. By Yaman Can.

Delegate work, review the result, and keep project context under control. Each user brings their own tools, account and model access.

| Skill | Use it for |
| --- | --- |
| [let-chinese](skills/let-chinese/SKILL.md) | Give a bounded coding task to OpenCode using your selected model. |
| [let-chinese-somehow](skills/let-chinese-somehow/SKILL.md) | Give the task to Dolly 1 Security through Zro and OpenCode, with automatic OpenCode approvals. |
| [duo](skills/duo/SKILL.md) | One implementation owner and one persistent Codex/Opus peer reviewer. |
| [orkestra](skills/orkestra/SKILL.md) | Coordinate separately owned slices and their integration. Includes the Duo dependency. |
| [project-context](skills/project-context/SKILL.md) | Audit and improve the instructions and context loaded for a selected project. |

## 1. Install

You need Node.js **22.20+** with npm/npx and Git for the [Skills CLI](https://github.com/vercel-labs/skills) (tested with **1.7.2**; check its requirements when using a newer version). Run this from the project where you want to use the skills:

```bash
npx skills@latest add yamancan/niche-skills
```

Choose the skills and your agent in the installer. This installs into the current project; add `-g` to make them available across your projects. While this repository is private, your GitHub account needs repository access and working Git, GitHub CLI or SSH authentication.

For a specific skill in both Claude Code and Codex:

```bash
npx skills@latest add yamancan/niche-skills --skill let-chinese-somehow -a claude-code -a codex
```

For Orkestra, install its required Duo companion in the same scope and agents. A global installation is recommended for this pair: Duo keeps a per-user task index, so keep the same Duo/Orkestra version across your projects. Use one scope per skill and agent.

```bash
npx skills@latest add yamancan/niche-skills --skill duo --skill orkestra -a claude-code -a codex -g
```

`project-context` is optional. Add `--skill project-context` if you also want to audit your project's instructions. To inspect the catalog first, run `npx skills@latest add yamancan/niche-skills --list`.

## 2. Set up once

Skill installation adds instructions and helpers. Native coding tools, accounts and model access are separate prerequisites. The supported runtime is macOS/Linux with Python **3.9+** and Git. Keep account keys in the native tools' login flows.

| Selected skill | First-use setup |
| --- | --- |
| `project-context` | Use it in your agent; no extra provider account is needed. |
| `duo` | Install Claude Code and Codex CLI. Ask your agent: **“Set up the installed Duo skill: resolve its installed directory, check the duo profile and give me the exact setup command for my terminal.”** The bundled wizard lets you choose models and sign in through native accounts. |
| `orkestra` | Install Duo alongside it. Ask your agent to set up the **normal** profile using the installed Duo wizard; this also configures future Duo model IDs. |
| `let-chinese` | Install OpenCode, run `opencode` in your terminal, connect your provider with `/connect` and select a model with `/models`. This worker supports native API authentication for OpenRouter and OpenCode Go. |
| `let-chinese-somehow` | Install OpenCode and Zro, run `zro login` in your terminal, then check `zro models` for `dolly1-security` access. |

Use the official [OpenCode](https://opencode.ai/docs/), [Zro](https://zro.moonmath.ai/docs/cli), [Claude Code](https://code.claude.com/docs/en/setup) and [Codex](https://developers.openai.com/codex/cli/) installation instructions. The skills launch existing tools; they do not install coding agents or buy access. Duo's [setup reference](skills/duo/references/setup.md) explains model choices and repeat setup.

For a new Zro account, this [referral signup link](https://zro.moonmath.ai/?ref=ZROSLWMI) is Yaman's referral; rewards depend on a qualifying paid subscription. Existing accounts can log in directly. Provider usage can incur charges. Login and a saved model choice do not prove model entitlement or available credit.

## 3. Use

```text
$let-chinese Fix this test with my selected OpenRouter model; review the diff.
$let-chinese-somehow Fix this bug with Dolly; run the tests and report back.
$duo Implement this change with a peer review.
$orkestra Coordinate these independent implementation slices.
$project-context Audit the instructions loaded for this checkout.
```

The Let Chinese skills normally run a separate worker process and return a result to the calling agent. The calling agent checks the artifact and tests. They open an interactive terminal only when explicitly requested. Exact-session follow-ups reuse the returned state directory and session ID; they do not resume an arbitrary last session.

## 4. Update

Updates are manual with this installation method. Run project updates from the project where you installed the skills; global updates can run from any directory. For the global Duo/Orkestra pair installed above:

```bash
npx skills@latest update duo orkestra -g
```

Update any other skill by its name, for example `npx skills@latest update let-chinese -p`. For a global installation use `-g` instead of `-p`. Updating Orkestra and Duo together keeps their shared helpers aligned.

To update every installed skill in this project, including skills from other repositories:

```bash
npx skills@latest update -p
```

Re-run the install command to select newly added skills. Keep the CLI-generated `skills-lock.json` for project installations. Review or back up local edits to installed skill files before updating. Your native account credentials and saved Duo model choices live outside the skill package; existing sessions retain their pinned models. Update native CLIs separately. Start a fresh agent session after updating so it loads the new instructions.

<details>
<summary>Advanced: install from a Git clone</summary>

Use this route when you want local links to a checkout you maintain. Use one installation method and scope per skill and agent to avoid conflicting copies.

```bash
git clone https://github.com/yamancan/niche-skills.git
cd niche-skills
bash install.sh --collection coding
```

This installer links the five Coding skills globally into Claude Code and Codex and starts Duo/Orkestra model/account setup in an interactive terminal. Add `--no-setup` to link only. Keep the cloned checkout in place. Update from that checkout with:

```bash
git pull --ff-only
```

Changes to linked files are then available to new agent sessions. If an updated installer adds skills to the collection, rerun `bash install.sh --collection coding --no-setup` to create their links. If the pull fails, resolve local edits or history divergence before retrying; the installer does not manage Git updates. Use Skills CLI updates only for Skills CLI installations.

`--skill NAME` selects one skill and includes Duo for Orkestra. `--no-setup` links instructions only. `--check` reports links and saved model choices without writes, network or inference. Native homes honor `CLAUDE_CONFIG_DIR` and `CODEX_HOME`; existing directories are backed up before replacement.

</details>

## Security and verification

Read [the security boundaries](SECURITY.md) before automatic execution. The isolated Let Chinese worker excludes personal config, plugins and MCP by default; it is **not an OS sandbox**. `--auto` approves native permissions not explicitly denied. Use trusted checkouts and preserve the calling client's execution restrictions.

The Let Chinese workers require OpenCode/Zro binaries outside the task checkout and exclude checkout-contained PATH entries.

No account keys, personal profiles, native sessions or real task transcripts are included. Runtime state is private and stays outside the task checkout. Model/provider routing still sends the selected task context to that provider.

See [verification](docs/verification.md) for the tested versions, checks and limits. This release contains five Coding skills.

## License

[MIT](LICENSE). External tools are installed separately and retain their own licenses and terms. Duo setup was inspired by Matt Pocock’s Wizard approach; its generic template is not bundled.
