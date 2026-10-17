# Fixed-source review and acceptance

Read before design, implementation or integration review. The entrypoint selects the team; this reference defines its evidence and completion.

## Freeze and inspect

Give required reviewers the same goal, acceptance conditions, settled decisions, scope and immutable source. For committed code record the base and exact commit/tree; reuse a verified immutable checkout or the selected-file packet from the [workspace lifecycle](../../duo/references/workspaces.md). For uncommitted code freeze relevant tracked and untracked bytes with a content manifest; a patch hash does not pin live source reads. Pause writers if an immutable copy is unavailable. Recheck identity at collection; drift invalidates affected coverage. For design documents record content identity and proposal status. Use hashes when source can drift or a gate requires them; a stable immutable commit needs no second digest system.

Review behavior paths, branches, removed behavior, callers and invariants before opening the author's summary and test claims. Then assess two axes: intended behavior and repository standards. A well-tested helper can still be absent from the real entrypoint; verify through the actual user path where acceptance depends on CLI, browser, time or an external system. Synthetic success alone does not establish real acceptance. Reviewers can use existing test evidence; builders/coordinator execute checks unless another run resolves a concrete uncertainty.

Fresh initial reviews use independent contexts, can share unchanged frozen source files, and are separate from builder context and other reviewers' reports. Follow-ups may resume the relevant reviewer with changed evidence. Ask for location, concrete failure scenario, source/caller evidence, proposed correction and readiness verdict. Distinguish draft critique from source-backed findings. A zero-findings report is valid when it states actual coverage; neither a defect quota nor model agreement is proof.

Dispatch independent initial reviews concurrently when their source and decisions are frozen; collect and verify each result as it finishes using the [session procedure](sessions.md). A slow or timed-out reviewer does not hold completed peers' evidence. The coordinator may adjudicate finished reports and continue unaffected work while required missing coverage stays open. If one reviewer needs a focused follow-up, resume only its recorded session; do not restart the entire team or create a duplicate context.

Keep each selected transport's configured tool and data-access boundary. If an attachment/packet cannot be read under those permissions, report missing coverage and repair the supported delivery path; broadening tools cannot conceal a failed transfer. A user-selected provider does not authorize secrets or broader repository context in its packet.

## Adjudicate and verify

Check findings against code, callers, specification and reproduction. A caller may guarantee an invariant that makes a suggested guard unnecessary. Group duplicate findings by root cause while retaining distinct failure cases. Record accepted, rejected with evidence, or nonblocking deferred with owner/trigger. An accepted blocker remains blocking until fixed and verified, disproved, or explicitly risk-accepted by an authorized user for that action/snapshot.

Fix in the owning builder session, run affected checks and request focused follow-up for changed claims. Shared-contract or integration changes refresh all affected coverage. Reuse accepted reviews only for unchanged applicable material and identify what they still cover. Stop when required behavior, checks and reviews are satisfied; optional suggestions do not expand agreed scope. Keep tests and guards meaningful rather than weakening them for green output.

The session record includes actual route/model/effort when reported, source identity, peer ID, completion and result; missing metadata remains unknown. Empty, timed-out or unfinished output and an unavailable required reviewer are missing coverage. Preserve completed coverage, finish unaffected work and identify the repair or explicit per-slice waiver needed. Budget exhaustion prevents new paid calls even if the account has credit. Source changes invalidate affected acceptance, not already granted commit/push authorization; preserve its action/scope and enforce actual host gates at the final action.

## Integration and finish

The coordinator owns an explicit integrated verdict. Inspect shared types, migrations, generated artifacts and cross-slice behavior, then verify the assembled snapshot. Record whether slice evidence still covers the combination; refresh review when contracts or combined behavior changed. Rebuild generated outputs after their sources merge and verify drift where relevant. Inspect consequential authority, persistence, billing and release changes directly.

Distinguish implemented, checked, reviewed, committed, merged, deployed and live-accepted status. Design-only work finishes as reviewed documents. Implementation finishes with the requested working outcome and its required checks/reviews. A commit or launched worker alone cannot satisfy it. Link evidence and remaining dependencies from the existing private task ledger.
