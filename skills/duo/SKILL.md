---
name: duo
description: Pairs Codex and Claude Opus on one bounded coding change; one model writes and tests it, the other reviews the diff. Use for "duo", a second-model review, or an existing Duo task. Use orkestra for interacting slices.
---

# Duo

Deliver one bounded, verified change with one code owner and one peer reviewer. Codex calls Opus; Claude/Opus calls Codex, both at **xhigh** through actual host/CLI controls. Use the active or user-selected owner and the recorded peer model; new tasks use explicit choices or saved Duo selections. Report unavailable models and unknown effective effort. The peer returns findings without delegating further.

Preserve user and repository requirements, exclusions, spending limits and release authority, and honor explicit workflow choices. Use Orkestra when separately owned slices need shared contracts or dependency ordering.

## Normal path

Run the installed Python helpers from the project's canonical checkout; `--help` lists their flags. On first use or a setup request, read [setup](references/setup.md) and finish setup before dispatch.

1. **Identify.** Run `scripts/pair.py list/show` before creating a pair. Bind to the real owner thread from trusted host metadata and the exact task, pair and peer IDs; a matching title is not identity. Keep the recorded checkout, Duo state and native config homes. With no task, run `init` from the project directory; check saved defaults with `scripts/setup_models.py --check --profile duo`.
2. **Prepare.** Reuse agreed acceptance and decisions. Make the smallest complete change, run the relevant checks and write a bounded brief carrying the repository instructions and user constraints the reviewer needs; automated reviewers run without customizations. Keep one writer per product file.
3. **Freeze.** From the workspace state in `show`, run `scripts/review_packet.py make --state STATE --file SOURCE --file TEST --file DIFF_OR_SPEC` with every required file, including callers and evidence. Exclude secrets and unrelated data. The manifest binds the selected bytes; a snapshot label does not.
4. **Review.** Run `scripts/pair.py run` with the canonical pair, actual owner/thread, exact task ID, brief, snapshot label and `--packet MANIFEST`, keeping the pinned model, session and read-only route. Set the outer deadline above the helper's 300-second default. Accept only a completed answer verified against native persistence with unchanged packet source; progress or a successful exit is not a review. Inspect a held call before recovery.
5. **Resolve.** Check actual reviewer coverage, fix concrete findings and rerun affected checks. Reuse unchanged accepted evidence; refresh changed source and follow up in the same peer session. Commit within authority. Report implemented, reviewed, merged and live-accepted status separately, with remaining limits; keep one compact private checkpoint for long work.

## Read when needed

- **Missing prerequisites, unconfigured defaults or model changes:** [setup](references/setup.md).
- **Unread native changes (`sync`/`ack`), a new coordinator, manual use, handoff, legacy adoption or a fresh context:** [conversation lifecycle](references/conversations.md).
- **First native route use, CLI incompatibility, timeout or held-call recovery:** [transport](references/opus-session.md).
- **Another checkout, disposable checks, storage recovery, handoff or completion:** [workspace lifecycle](references/workspaces.md).
- **Physical checkout move:** [relocation](references/relocation.md).
