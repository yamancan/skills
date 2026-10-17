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

## Install what you need

List skills, then select one for either or both clients:

```bash
npx skills add yamancan/niche-skills --list
npx skills add yamancan/niche-skills --skill let-chinese-somehow -a claude-code -a codex
```

For the team workflow, select the companion skills together:

```bash
npx skills add yamancan/niche-skills --skill duo --skill orkestra --skill project-context -a claude-code -a codex
```

The default scope is the current project. Add `-g` for global installation. The [Skills CLI](https://github.com/vercel-labs/skills) handles skill installation; it does not create your provider account. While this repository is private, GitHub access is required.

Or clone the repository and install the Coding collection into both local clients:

```bash
git clone https://github.com/yamancan/niche-skills.git
cd niche-skills
bash install.sh --collection coding
```

`--skill NAME` selects one skill and includes Duo for Orkestra. `--no-setup` links instructions only. `--check` reports links and saved model choices without writes, network or inference. Native homes honor `CLAUDE_CONFIG_DIR` and `CODEX_HOME`; existing directories are backed up before replacement. Keep a cloned checkout in place while its symlinks are installed.

## Use

```text
$let-chinese Fix this test with my selected OpenRouter model; review the diff.
$let-chinese-somehow Fix this bug with Dolly; run the tests and report back.
$duo Implement this change with a peer review.
$orkestra Coordinate these independent implementation slices.
$project-context Audit the instructions loaded for this checkout.
```

The Let Chinese skills normally run a separate worker process and return a result to the calling agent. The calling agent checks the artifact and tests. They open an interactive terminal only when explicitly requested. Exact-session follow-ups reuse the returned state directory and session ID; they do not resume an arbitrary last session.

## Tools and accounts

Python 3.9+, Git, and macOS or Linux are the initial supported environments. Install native tools yourself using their official instructions. The bounded workers require OpenCode/Zro binaries outside the task checkout; checkout-contained PATH entries are excluded. These skills never automatically install a coding agent or buy access.

- Let Chinese: OpenCode; this release's isolated worker supports native API authentication for OpenRouter and OpenCode Go. Select your own `provider/model` ID. Custom provider configuration and OAuth are outside this first worker's support.
- Let Chinese Somehow: OpenCode and Zro; run `zro login` in your own terminal and check Dolly access with `zro models`. A [referral signup link](https://zro.moonmath.ai/?ref=ZROSLWMI) is offered for new accounts; rewards depend on a qualifying paid subscription.
- Duo/Orkestra: Claude Code and Codex CLI with your own accounts and model access. After Skills CLI installation, ask the agent to run the installed Duo setup script in your terminal to choose models and sign in. The clone installer provides the exact setup command. Existing sessions retain their original model choices.

Provider usage can incur charges on your account. A configured model name does not prove account entitlement.

The completed Dolly task tests used Zro 0.2.1. Zro 0.3.0 task attempts stalled in the preparation environment; its task completion remains unverified. See the [test record](docs/verification.md) before choosing versions or repeating a blocked run.

## Security and verification

Read [the security boundaries](SECURITY.md) before automatic execution. The isolated Let Chinese worker excludes personal config, plugins and MCP by default; it is **not an OS sandbox**. `--auto` approves native permissions not explicitly denied. Use trusted checkouts and preserve the calling client's execution restrictions.

No account keys, personal profiles, native sessions or real task transcripts are included. Runtime state is private and stays outside the task checkout. Model/provider routing still sends the selected task context to that provider.

See [verification](docs/verification.md) for the tested versions, checks and limits. This release contains five Coding skills.

## License

[MIT](LICENSE). External tools are installed separately and retain their own licenses and terms. Duo setup was inspired by Matt Pocock’s Wizard approach; its generic template is not bundled.
