# Migration and acceptance

Use this when implementing a context migration. Reuse the repository's existing planning and verification mechanisms.

## Preserve meaning before shortening

1. Capture a baseline commit and dirty/untracked inventory. Preserve relevant uncommitted material separately; Git history cannot recover it. Keep unrelated work untouched.
2. For each removed rule or history block, record its destination or evidenced reason for retirement. Preserve canonical decisions, identifiers, overrides and authority conditions. An unresolved policy conflict is a finding, not permission to choose the easier rule.
3. Keep archived content retrievable within the authorized read scope: a retained file, or an immutable commit and checkout-relative path with a working retrieval command. Test retrieval from the intended checkout/clone. If that history is unavailable, retain an accessible archive. Temporary files and moving branch names are not durable archives. A retrieval command still requires the applicable host permission before it runs.
4. Update callers and links in the same change. Renaming a context/glossary file is appropriate only when its meaning and consumers match; do not impose a naming migration on unrelated material.

Root guidance should retain a concise live-action boundary and point to exact authority; detailed old deployment attempts belong in history. Preserve existing approvals for their authorized scope without inventing new approval ceremonies. Documentation cleanup does not renew expired permissions or authorize deployments, dependency upgrades or global configuration changes.

## Curate lessons

Use this entry shape; do not create an empty memory system just to fill it:

```text
Status: draft | verified | superseded
Trigger/scope: when this lesson applies
Lesson: the non-obvious decision it changes
Evidence: source location, executed regression or canonical incident
Validity: versions/protocol/environment assumptions
Invalidate when: the relevant assumption changes
```

For an imported lesson, use `Status: draft` while its evidence is uninspected, even if the old note says "verified". Record that old claim as provenance. After checking supporting evidence, set `Status: verified`. A historical incident proves the trap existed, not that today's code fails. Keep unverified ideas separate from instructions. Supersede lessons with a reason when contradicted. Preserve secrets and private session content outside shared files. Task progress goes in the existing task record with source, check and remaining gate; avoid a second task tracker.

## Acceptance

Choose context budgets from the observed task mix and client limits; document the effective starting load and representative task loads. A byte budget is a maintenance guard, not a universal quality score.

Use existing linters where possible: validate changed links/imports, meaningful anchors, scope targets and adapter content. Compare preserved rules with the baseline. If adding a checker, prove it rejects a broken pointer or lost required invariant as well as accepting the valid tree.

Exercise representative tasks:

| Task | Evidence to look for |
|---|---|
| Small local edit | Relevant scope found; unrelated domain/runbook history stays unloaded |
| Feature across UI/API/worker | Shared contract and all affected scope instructions found |
| Auth/data, money or retry change | Applicable invariant and behavioral checks identified before edits |
| Resume after interruption | Exact source/check status and next unresolved gate; no inferred deployment |
| Release-related request | Current authority resolved; consumed/expired permission is not reused |

Use root and nested launch paths for the actual supported clients. When independent agents are available and authorized, give one a realistic task and minimal raw artifacts without revealing the expected answer. Otherwise record a manual routing trace and its limits. If an automatic loader or real task trial was not run, say so explicitly.

Structural success proves that references resolve. Routing success proves discoverability for the tested task. Neither proves future obedience. Keep critical invariants in code/tests, and compare real task outcomes after adoption before claiming reliability gains.
