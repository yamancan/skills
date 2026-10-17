---
name: duo
description: Coordinate one bounded coding slice or continue its Codex/Opus conversations. Use Orkestra when separately owned slices need shared contracts, dependency ordering or integrated acceptance.
---

# Duo

Deliver one bounded, verified slice with one code owner and one peer reviewer. Preserve user/repository requirements, exclusions, spending limits and release authority. Honor explicit workflow choices; use Orkestra when separately owned slices need shared contracts or dependency ordering.

Codex calls Opus; Claude/Opus calls Codex. Both request **xhigh** through actual host/CLI controls. Use the active/user-selected owner and the recorded peer model. New tasks use explicit choices or saved Duo selections. Report unavailable models and unknown effective effort. The peer returns findings without further delegation.

## Normal path

Run the installed Python helpers from the project's canonical checkout. Use their `--help` for flags.

1. **Identify.** Discover existing work with `scripts/pair.py list/show` before creating a pair. Use the actual owner thread from trusted host metadata and the exact task/pair/peer IDs; a matching title alone is insufficient. Keep the recorded checkout, shared Duo state and native config homes. If no task exists, use `init` from the current project directory. Check saved defaults with `scripts/setup_models.py --check --profile duo` before selecting them.
2. **Prepare.** Reuse acceptance and decisions. Implement the smallest complete change, run the relevant checks and write a bounded review brief carrying applicable repository instructions and user constraints; the automated reviewer disables customizations as described in the transport reference. Keep one writer per product file.
3. **Freeze.** For source review, get the workspace state from `show`. Use `scripts/review_packet.py make --state STATE --file SOURCE --file TEST --file DIFF_OR_SPEC` with explicit required files, including necessary callers and evidence. Exclude secrets and unrelated data. The returned manifest binds the selected bytes; a snapshot label alone does not.
4. **Review.** Call `scripts/pair.py run` with the canonical pair, actual owner/thread, exact task ID, brief, snapshot label and `--packet MANIFEST`. Retain the pinned model/session and read-only route. Keep the outer command deadline longer than the helper's default 300 seconds. Accept only a completed answer verified against native persistence and unchanged packet source. Progress and a successful exit alone are insufficient.
5. **Resolve.** Inspect actual reviewer coverage, fix concrete findings and rerun affected checks. Reuse unchanged accepted evidence; refresh changed source and follow up in the same peer session. Commit within authority. Report implemented, reviewed, merged and live-accepted status separately, with remaining limits. Keep one compact private checkpoint for long work.

If the helper blocks for unread native changes, read and reconcile `sync`, then `ack` its exact token. An unresolved/held call requires inspection before recovery.

## Load when needed

- **Missing prerequisites, unconfigured defaults or model changes:** [setup](references/setup.md).
- **First use of a native route, CLI compatibility issues, timeout or held-call recovery:** [transport](references/opus-session.md). Verify native progress, processes and retained history; preserve the exact session during recovery.
- **New coordinator, manual use, handoff, legacy adoption or deliberate fresh context:** [conversation lifecycle](references/conversations.md). Idle the previous coordinator before transfer; use an explicit fork with parent/reason for independent context.
- **Another checkout, disposable execution, storage recovery, handoff or completion:** [workspace lifecycle](references/workspaces.md). Preserve unique work and close disposable checks; canonical source stays discoverable.
- **Physical checkout move:** [relocation](references/relocation.md).
