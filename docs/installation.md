# Installation and setup

Install the [Coding collection](../README.md#coding), complete setup for the skills you choose, then start a fresh agent session.

## Install

Choose one installation method per agent to avoid duplicate skills. The **Coding** plugin includes the five current Coding skills, including Duo alongside Orkestra. Each skill is stored once in this repository; both plugin hosts load the same source.

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

While this repository is private, both plugin methods require GitHub repository access and working Git authentication. Use current Claude Code/Codex versions with plugin support. See [verification](verification.md) for tested versions.

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
<summary>npm shortcut and direct Skills CLI</summary>

The equivalent npm shortcut is:

```bash
npx niche-skills
```

Both shortcuts use the same launcher and source repository.

You can also use Skills CLI directly:

```bash
DISABLE_TELEMETRY=1 npx skills@latest add yamancan/skills
```

The direct CLI does not include Duo automatically: select both `duo` and `orkestra` when using Orkestra. Native plugins do not use the npm installer or its dependencies.

</details>

## Set up once

Skill installation adds instructions and helpers. Native coding tools, accounts and model access are separate prerequisites. The supported runtime is macOS/Linux with Python **3.9+** and Git. Keep account keys in the native tools' login flows.

| Selected skill | First-use setup |
| --- | --- |
| `project-context` | Use it in your agent; no extra provider account is needed. |
| `duo` | Install Claude Code and Codex CLI. Ask your agent: **“Set up the installed Duo skill: resolve its installed directory, check the duo profile and give me the exact setup command for my terminal.”** The bundled wizard lets you choose models and sign in through native accounts. |
| `orkestra` | Install Duo alongside it. Ask your agent to set up the **normal** profile using the installed Duo wizard; this also configures future Duo model IDs. |
| `let-chinese` | Install OpenCode, run `opencode` in your terminal, connect your provider with `/connect` and select a model with `/models`. This worker supports native API authentication for OpenRouter and OpenCode Go. |
| `let-chinese-somehow` | Install OpenCode and Zro, run `zro login` in your terminal, then check `zro models` for `dolly1-security` access. |

Use the official [OpenCode](https://opencode.ai/docs/), [Zro](https://zro.moonmath.ai/docs/cli), [Claude Code](https://code.claude.com/docs/en/setup) and [Codex](https://developers.openai.com/codex/cli/) installation instructions. The skills launch existing tools; they do not install coding agents or buy access. Duo's [setup reference](../skills/duo/references/setup.md) explains model choices and repeat setup.

For a new Zro account, this [referral signup link](https://zro.moonmath.ai/?ref=ZROSLWMI) is Yaman's referral; rewards depend on a qualifying paid subscription. Existing accounts can log in directly. Provider usage can incur charges. Login and a saved model choice do not prove model entitlement or available credit.

## Use

For the Claude Code plugin, use `/niche-coding:<skill>`. For the Codex plugin, use `$niche-coding:<skill>`. For a CLI-installed skill, use its unprefixed name from your agent's menu; in Codex, for example:

```text
$let-chinese Fix this test with my selected OpenRouter model; review the diff.
$let-chinese-somehow Fix this bug with Dolly; run the tests and report back.
$duo Implement this change with a peer review.
$orkestra Coordinate these independent implementation slices.
$project-context Audit the instructions loaded for this checkout.
```

The Let Chinese skills normally run a separate worker process and return a result to the calling agent. The calling agent checks the artifact and tests. They open an interactive terminal only when explicitly requested. Exact-session follow-ups reuse the returned state directory and session ID; they do not resume an arbitrary last session.

## Update

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

Before automatic execution, read the [security boundaries](../SECURITY.md). For tested versions and live provider limits, see [verification](verification.md).
