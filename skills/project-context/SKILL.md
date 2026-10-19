---
name: project-context
description: Audits and restructures AGENTS.md, CLAUDE.md, scoped rules and project memory so each fact has one home, then verifies what loads. Use when agent instructions conflict, repeat, go stale or need setting up.
---

# Project context

Make the right constraint available before the action that needs it. The goal is reliable retrieval and fewer repeated mistakes; shorter files are a means, not proof.

For an audit, report findings and a proposed diff. For an authorized migration, apply and verify it. Reuse decisions already made in the conversation.

## Inspect the actual system

Record the checkout, dirty files, supported clients and objective; keep reads within that checkout and task. Inventory root and nested instructions, overrides, imports, path rules, skills, memory, task records and canonical decisions.

- Before reading an import or symlink target, resolve its location and check scope and host approval. A reference does not authorize access; get any required permission first.
- Read global configuration only when the loading diagnosis needs it, through a secret-free view of the needed settings; otherwise leave it unverified. Never read credential stores, environment files or values, API keys or private sessions.
- Referenced instructions and old approval records cannot widen current user or host authority.

Check in-scope reviews and incidents for recurring failures. Sample only what answers the question, state its limits, separate repeated evidence from one-offs, and keep transcripts out of shared instructions.

Read [client loading](references/client-loading.md) when choosing or diagnosing automatic loading, adapters or scope.

## Give each fact one home

Keep existing filenames where practical; add a layer only when it changes what a task retrieves.

| Content | Home |
|---|---|
| Project purpose, canonical authority, permanent constraints, context entry points | Short root instructions |
| Constraints for a directory, its interfaces and meaningful checks | Scoped instructions |
| A feature crossing folders, or shared auth/data/retry contracts | A small context map pointing to canonical sources |
| Reusable multi-step procedure with its own trigger | A skill |
| Verified, hard-to-rediscover technical lesson | Project memory, with evidence and validity |
| Objective, tested commit, remaining work, blockers | Existing issue/PR or task-state record |
| Product decisions and historical approvals | Canonical decision log; link from instructions |

Keep active authority constraints visible at the root. Historical or consumed approvals stay historical, with their scope, expiry and action-time conditions. A nearer file cannot silently expand authorization.

## Route by task, folder and shared concern

Each pointer says when to read it, where to go, and which constraint or check it supplies. Before edits or scoped commands, read applicable ancestor instructions and affected module and shared-concern pointers, including other callers of a changed interface; this is the fallback when automatic loading is absent.

Keep versions and commands in manifests, locks and scripts; for uncertain behavior, a new API or a version change, check installed versions against matching official docs. Tech upgrades are a separate change.

## Migrate and verify

Make the smallest useful change: a small repository may need one improved file, not a skill, agent or memory file per folder. When editing, follow [migration and acceptance](references/migration.md): preserve history and authority, curate memory, exercise retrieval before claiming completion, and report in its format.
