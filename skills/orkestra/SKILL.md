---
name: orkestra
description: Coordinates interacting coding slices with shared contracts, a Codex build and review per slice, and one integration decision. Use for "orkestra" or multi-part changes with dependencies. Use duo for one change.
---

# Orkestra

The active Codex or Claude agent coordinates. Honor the user's chosen workflow, team, models and efforts. Otherwise choose by ownership:

- **Duo** for one bounded outcome with one code owner, even across modules or for a consequential payment fix. Run independent backlog items as successive Duos.
- **Orkestra** when separately owned slices interact.

State the choice and reason once; revisit it only when dependencies actually change. Risk sets verification depth, not team size.

Orkestra needs [Duo](../duo/SKILL.md) installed beside it, under the same parent directory, for its setup, workspace and process helpers. The Niche Skills installer adds Duo when Orkestra is selected; with another skill manager, install both `duo` and `orkestra`. This release ships the normal profile only.

## Roles and models

| Responsibility | Route |
| --- | --- |
| Product decisions, secrets and external-action authority | User; preserve scoped decisions/approvals |
| Contract, briefs, integration, final review and authorized commits | Active coordinator |
| Slice builder | Normal profile's selected Codex model/effort |
| Initial implementation/integration review | Fresh read-only Codex context, same selected default |
| Paired Codex/Opus reviews | Saved Duo seats, configured together with normal setup |
| Consequential unresolved designs | Two Fable and two Astra designers, then coordinator synthesis |

On first use or after a model update, read [shared setup](../duo/references/setup.md) and run the installed Duo `setup_models.py --check --profile normal`; run the normal setup wizard if it is unconfigured. Use the saved role selections; the user's explicit choices override them. Apply them through actual host controls, since preferences never change the active coordinator or an existing native session. Report an unavailable or unsupported route instead of substituting another.

## Run

Read each reference before its step:

| Before | Read |
| --- | --- |
| Framing, building or integration | [shared workflow](references/workflow.md) |
| Creating, continuing or handing off a peer, or manual use | [task sessions](references/sessions.md) |
| Any review | [review protocol](references/reviews.md) |
| A consequential design choice that stays unresolved | [unresolved designs](references/workflow.md#unresolved-designs) |

Discover the existing task before creating peers, and keep exact peer IDs across caller chats. Workers report back without delegating further. The paired dispatcher runs only read-only Codex/Opus reviews at xhigh; other roles use supported host tools.

Finish the requested scope with actual checks, the applicable reviews and the integrated verdict from the workflow. Report implementation and live acceptance separately.
