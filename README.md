# Niche Skills

**By Yaman Can.** Coding skills for Claude Code and Codex.

Delegate work, review the result, and keep project context under control. Each user brings their own tools, account and model access.

| Skill | Use it for |
| --- | --- |
| [let-chinese](skills/let-chinese/SKILL.md) | Give a bounded coding task to OpenCode using your selected model. |
| [let-chinese-somehow](skills/let-chinese-somehow/SKILL.md) | Give the task to Dolly 1 Security through Zro and OpenCode, with automatic OpenCode approvals. |
| [duo](skills/duo/SKILL.md) | One implementation owner and one persistent Codex/Opus peer reviewer. |
| [orkestra](skills/orkestra/SKILL.md) | Coordinate separately owned slices and their integration. Includes the Duo dependency. |
| [project-context](skills/project-context/SKILL.md) | Audit and improve the instructions and context loaded for a selected project. |

## 1. Install

Choose one installation method per agent to avoid duplicate skills. The **Coding** plugin includes all five skills above, including Duo alongside Orkestra. Each skill is stored once in this repository; both plugin hosts load the same source.

### Claude Code

In your terminal:

```bash
claude plugin marketplace add yamancan/skills
claude plugin install niche-coding@yamancan
```

This installs for your user across projects. In Claude Code, invoke a skill with its plugin namespace, for example `/niche-coding:duo`. For automatic updates, open `/plugin`, select **Marketplaces → yamancan → Enable auto-update**; third-party marketplaces do not enable it by default.

### Codex

In your terminal:

```bash
codex plugin marketplace add yamancan/skills
codex plugin add niche-coding@yamancan
```

Start a fresh session and select the installed skill, for example `$niche-coding:duo`. The plugin adds instructions and helpers; it does not install or configure provider accounts.

While this repository is private, both plugin methods require GitHub repository access and working Git authentication. Use current Claude Code/Codex versions with plugin support. See [verification](docs/verification.md) for tested versions.

### Individual skills and other agents

You need Node.js **22.20+**, npm/npx and Git for this route. Run from the project where you want the skills:

```bash
npx yamancan/skills
```

Choose skills, then your agent. The shortcut includes Duo when you choose Orkestra. Keep the recommended **Symlink** method so clients share installed files. Installation defaults to the current project; add `-g` for all your projects. Private repository access is required until public release.

For a specific skill in both clients:

```bash
npx yamancan/skills --skill let-chinese-somehow -a claude-code -a codex
```

For Orkestra and its Duo companion, a global installation is recommended. Duo keeps a per-user task index, so use the same Duo/Orkestra version across projects:

```bash
npx yamancan/skills --skill orkestra -a claude-code -a codex -g
```

Scripts and agent calls must specify both skills and agents. Use `--list` to browse and `--help` for supported options. The shortcut uses Skills CLI **1.7.2** and disables its telemetry, including its optional remote audit-card lookup. This is not a security scan.

<details>
<summary>npm alias and direct Skills CLI</summary>

The equivalent npm shortcut is prepared but **not published yet**:

```bash
npx niche-skills
```

Until publication, use `npx yamancan/skills`. Both use the same launcher and source repository.

You can also use Skills CLI directly:

```bash
DISABLE_TELEMETRY=1 npx skills@latest add yamancan/skills
```

The direct CLI does not include Duo automatically: select both `duo` and `orkestra` when using Orkestra. Native plugins do not use the npm installer or its dependencies.

</details>

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

For the Claude Code plugin, use `/niche-coding:<skill>`. For the Codex plugin, use `$niche-coding:<skill>`. For a CLI-installed skill, use its unprefixed name from your agent's menu; in Codex, for example:

```text
$let-chinese Fix this test with my selected OpenRouter model; review the diff.
$let-chinese-somehow Fix this bug with Dolly; run the tests and report back.
$duo Implement this change with a peer review.
$orkestra Coordinate these independent implementation slices.
$project-context Audit the instructions loaded for this checkout.
```

The Let Chinese skills normally run a separate worker process and return a result to the calling agent. The calling agent checks the artifact and tests. They open an interactive terminal only when explicitly requested. Exact-session follow-ups reuse the returned state directory and session ID; they do not resume an arbitrary last session.

## 4. Update

### Plugin installations

For Claude Code:

```bash
claude plugin marketplace update yamancan
claude plugin update niche-coding@yamancan
```

For Codex, refresh the marketplace and start a fresh session:

```bash
codex plugin marketplace upgrade yamancan
```

Follow the plugin manager's update controls. Do not install a CLI copy alongside a plugin in the same agent. To switch methods, remove the existing installation first. Native tool updates and account login remain separate from skill updates.

### CLI installations

Run project updates from the project where you installed the skills; global updates can run from any directory. Update Duo and Orkestra together:

```bash
DISABLE_TELEMETRY=1 npx skills@latest update duo orkestra -g
```

Use `-p` instead of `-g` for project installations. Select other skills by name, for example `DISABLE_TELEMETRY=1 npx skills@latest update let-chinese -p`.

If you chose **Copy** or one client keeps old files, re-run the shortcut with the same skills, agents and scope. Keep `--copy` only if you originally chose Copy:

```bash
npx yamancan/skills --skill orkestra -a claude-code -a codex -g --copy
```

Re-run installation to select newly added skills. Keep the CLI-generated `skills-lock.json` for project installs and review local edits before updating. Existing links from a Git-clone installation follow their checkout; update that checkout with `git pull --ff-only`. Credentials and saved Duo model choices live outside the skill package. Existing native sessions retain their pinned models; start a fresh agent session to load updated instructions.

## Security and verification

Read [the security boundaries](SECURITY.md) before automatic execution. The isolated Let Chinese worker excludes personal config, plugins and MCP by default; it is **not an OS sandbox**. `--auto` approves native permissions not explicitly denied. Use trusted checkouts and preserve the calling client's execution restrictions.

The Let Chinese workers require OpenCode/Zro binaries outside the task checkout and exclude checkout-contained PATH entries.

No account keys, personal profiles, native sessions or real task transcripts are included. Runtime state is private and stays outside the task checkout. Model/provider routing still sends the selected task context to that provider.

See [verification](docs/verification.md) for the tested versions, checks and limits. This release contains five Coding skills.

## License

[MIT](LICENSE). External tools are installed separately and retain their own licenses and terms. Duo setup was inspired by Matt Pocock’s Wizard approach; its generic template is not bundled.
