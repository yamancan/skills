# Shared Orkestra workflow

This procedure uses the roles and review requirements selected in [SKILL.md](../SKILL.md). The active coordinator owns shared contracts, dispatch, findings, integration and final acceptance. Preserve user/repository requirements, scope exclusions, spending limits, settled decisions and existing commit/push/release authority.

## Frame

Inspect instructions, domain terms, architecture decisions, dirty files, owners, callers and tests. Classify design-only, implementation or review and stay within that request. Extend an adequate existing brief or one private ledger with why, capabilities, constraints, exclusions and observable acceptance. New decisions identify what they supersede. Ask only for missing consequential choices unavailable from the environment/session; continue independent work while waiting.

Apply domain-modeling when terms/invariants are unclear, codebase-design when interfaces/ownership change, and architecture methods for demonstrated friction. Resolve optional skills from the active catalog; disclose absent methods and inspect source/callers/tests directly. An explicitly requested BMAD review uses the available method or records missing coverage. Start with a working vertical slice. New abstractions/rewrites need a real caller/variation and a deletion-test rationale. Architecture work follows evidence rather than every commit.

Keep scope, ownership, authorization, decisions, exact sessions, snapshots/results, review dispositions, checks and publication state in the same durable private ledger outside disposable worktrees/published artifacts. Link its canonical path from the checkpoint; chat context is not its only copy. Session transport and recovery follow [task sessions](sessions.md).

Before creating a checkout, another dependency installation, a review packet, handoff or completion, follow the shared [workspace lifecycle](../../duo/references/workspaces.md). Reuse its canonical state across Duo/Orkestra and coordinator changes.

## Unresolved designs

Use the four-designer team from the roles table only for a consequential interface or ownership choice that stays unresolved, unless the user chose another team. Freeze the question, constraints and source. Compare minimal interface, future seam, common caller and safety, and flexibility. Initial designs are independent; cross-critique follows through the recorded sessions. Synthesize caller burden, locality, evidence and tradeoffs; agreement between designers is not correctness. Ask the user only about unresolved product choices and record the selected direction. A paper review does not prove measured product quality.

## Partition and build

Brief each independently verifiable slice: goal/baseline, allowed files/side effects, consumed/produced contracts and invariants, decisions, acceptance/check commands, done criteria, workdir/branch, selected route/model/effort, result path and git/release authority. Preserve user/repository owner-only gates on money caps, golden snapshots and approval/upload files. A worker sandbox grants no release rights. Integration/publication remains with the coordinator unless explicitly delegated within existing authority.

Reuse the canonical checkout; inspect suitable attachments before creating a host-managed worktree for a separately owned builder. Record each added worktree and its closure obligation in the existing ledger. Resolve permission failures through supported host access/handoff. Uncommitted work is not copied automatically. Assign one editor per path set, including generated files; parallelize disjoint ownership and serialize contracts, migrations and overlapping writes. Preserve unrelated dirty files.

Build meaningful behavior coverage using actual repository commands and required TDD. Builders own mechanical checks and report diff, files, checks, limitations and source identity. Inspect their completion claims.

## Review, fix and integrate

1. Freeze actual relevant tracked/untracked source. Run the applicable initial reviewers in separate fresh contexts, using the [review protocol](reviews.md). Reviewers trace behavior, callers and removed behavior before reading the author's summary. Intended behavior and repository standards remain separate axes. Cross-critique follows independent initial results.
2. Validate findings against source, caller guarantees and reproduction. Combine duplicate root causes; record accepted, rejected with evidence, or nonblocking deferrals with owner/trigger. Fix blockers in the owning builder session, rerun affected checks and request focused follow-up through the recorded reviewer. Shared-contract changes refresh affected coverage. A blocker stays blocking until verified, disproved or explicitly risk-accepted by an authorized user for that action/snapshot. Empty findings are valid; suggestions do not expand scope.
3. Coordinator directly inspects consequential authority, persistence, billing and release paths. Commit coherent verified slices within existing authority. Revisit architecture only when new evidence exposes friction; reuse accepted unchanged evidence.
4. Integrate in dependency order; resolve shared-type/migration collisions and rebuild generated outputs. Verify the assembled snapshot and record an explicit integrated verdict, including when unchanged slice evidence is reused. Refresh reviews for changed contracts/cross-slice behavior. Fix integration defects with verified checks and affected review. Preserve published history unless rewriting was authorized. Push/merge/deploy only within actual action/scope authority and host gates.

## Finish

Close helper-owned disposable checks, inspect outstanding reservations, and archive completed builder worktrees after verifying recoverable source/evidence. Report the canonical checkout and remaining active areas using the workspace lifecycle.

Missing or unfinished review, wrong sessions, timeout, unavailable routes and rejected transfers do not establish coverage. Record the missing prerequisite and repair/waiver trigger; finish unaffected work while required gates remain incomplete. Repeated identical investigations/timeouts supply no new evidence. Native history is not proof of a cache hit. Account credit does not enlarge spending authorization.

Complete agreed scope before optional improvements. Verify the real CLI/browser/time/provider surface when acceptance depends on it; synthetic success does not prove external acceptance. Distinguish implemented, checked, reviewed, committed, merged, deployed and live-accepted status. Design-only work ends in reviewed documents with implementation status explicit. Report outcome, observed verification and material dependencies in the user's language.
