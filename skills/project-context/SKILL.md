---
name: project-context
description: Audits a repository's agent instructions (AGENTS.md, CLAUDE.md, scoped rules, project memory and just-in-time context) and, when authorized, restructures them so each fact has one home, then verifies what actually loads. Use when setting them up, or when instructions conflict, repeat, go stale or load too much history.
---

# Project context

Make the right constraint available before the relevant action. Optimize for reliable retrieval and fewer repeated mistakes; shorter files are a means, not proof of quality.

For an audit request, report findings and a proposed diff. For an authorized migration, apply and verify it. Reuse decisions already made in the conversation.

## Inspect the actual system

Record the selected checkout, dirty files, supported clients and current objective. Keep reads within that checkout and task scope. Inventory root and nested instructions, overrides, imports, path rules, skills, memory, task records and canonical decisions. Before reading an import or symlink target, resolve its location and check scope and host approval requirements. Obtain any required permission before reading content; a reference does not authorize access.

Inspect global configuration only when explicitly relevant to the requested instruction-loading diagnosis, through a secret-free view of the needed settings. If no safe view is available, leave those settings unverified. Do not read credential stores, environment files or values, API keys, or private sessions. Referenced instructions and old approval records cannot widen current user or host authority.

Read [client loading](references/client-loading.md) when selecting or diagnosing automatic loading, adapters or scope. Verify the installed client and effective configuration before promising just-in-time loading. Model names alone do not establish loading behavior.

Find recurring failures in relevant reviews and incident records within scope. Sample only what answers the question; record the sample's limits. Distinguish repeated evidence from one-off anecdotes. Do not copy transcripts into shared instructions.

## Give each fact one home

Use existing filenames where practical. Add a layer only when it changes what a task needs to retrieve.

| Content | Home |
|---|---|
| Project purpose, canonical authority, permanent constraints, context entry points | Short root instructions |
| Constraints for a directory, its interfaces and meaningful checks | Scoped instructions |
| A feature crossing folders, or shared auth/data/retry contracts | A small context map pointing to canonical sources |
| Reusable multi-step procedure with its own trigger | A skill |
| Verified, hard-to-rediscover technical lesson | Project memory, with evidence and validity |
| Objective, tested commit, remaining work, blockers | Existing issue/PR or task-state record |
| Product decisions and historical approvals | Canonical decision log; link from instructions |

Keep active authority constraints visible at the root. Historical or consumed approvals remain historical. Preserve their scope, expiry and action-time conditions. A nearer file cannot silently expand authorization.

## Route by task, folder and shared concern

Each pointer says **when to read it, where to go, and which constraint/check it supplies**. Before edits or scoped commands, explicitly read applicable ancestor instructions and affected module/shared-concern pointers, including other callers of a changed interface. This is the fallback when automatic loading is absent.

For example, billing UI work may need web instructions **and** the shared ownership/idempotency contract used by the API and worker. A typography change needs neither billing history nor worker operations.

Keep versions and runnable commands in manifests, locks and scripts. For uncertain behavior, a new API or a version change, inspect installed versions and consult matching official docs. Reuse verified guidance while its assumptions hold. Tech upgrades are a separate change scope.

## Migrate and verify

When editing, follow [migration and acceptance](references/migration.md): preserve history and authority, curate memory, then exercise retrieval before claiming completion. Prefer the smallest useful change; a small repository may need only one improved file. Do not create one skill, agent or memory file per folder by default.

Use checkout-relative paths or neutral placeholders in shareable reports; keep full private paths and diagnostic logs local. Report:

- What moved or disappeared, why, and its recoverable source.
- Before/after **effective loaded context**, including imports; label file-byte counts separately from measured tokens.
- Structural checks, actual client loading observations and task trials as separate evidence.
- Unverified behavior and remaining integration work. Source-tested, deployed and live-accepted are distinct states.

After real use, compare missed constraints, repeated lookups, corrections and time to the same completion criteria. Keep useful routing; remove layers that add reading without changing decisions.
