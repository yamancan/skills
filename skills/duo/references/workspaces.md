# Checkout, temporary storage and review evidence

Read before creating a checkout, installing dependencies in a second directory, using disposable checks, handing off a task, or closing it. Ordinary selected-file review capture follows the Duo normal path below; this reference covers its storage and recovery details. Duo and Orkestra share this lifecycle. Conversation identity, canonical source, temporary checks and provider prompt caching are separate resources.

## Keep the source discoverable

A task has one canonical writable checkout. Record its absolute path and branch/HEAD in the existing task ledger; handoffs retain it. Duo `init` binds its physical directory, and dispatch/manual/handoff reject a replacement at the same path. `show` supplies the workspace record and status command. Existing pairs bind on their next managed use. Keep the shared `DUO_STATE_DIR` stable.

For Orkestra, reuse that Duo workspace when continuing its task. Otherwise bind once with the installed Duo helper and keep the returned state path in the existing ledger:

```bash
python3 /path/to/duo/scripts/workspace.py --state /private/task/workspace.json \
  bind --workdir /actual/project
python3 /path/to/duo/scripts/workspace.py --state /private/task/workspace.json status
```

Before creating another workspace, inspect this record and suitable host attachments. Resolve missing write access with supported host handoff/attachment or scoped access. Permission denial is not authorization to bypass a boundary, copy the repository, change provider, or create replacement state. A deliberate move uses the journaled [checkout relocation helper](relocation.md); ordinary bind/handoff never infer a new physical identity.

For truly parallel builders, use necessary host-managed worktrees and record each path, owner, purpose, base, branch/commit, active process and closure state in the same ledger. Reviewers use the frozen source below and separate conversation contexts. New reviewer context, caller or model does not itself need a new clone or dependency installation. Allocate ordinary directories only when required by the host; preserve the same ownership/closure evidence. Keep task records, native transcripts and final evidence outside disposable areas.

## Disposable checks

Use `workspace.py run` for reproducible tests, package-consumer fixtures or temporary review runtimes that need their own files. It starts from an empty helper-owned directory, or copies only a selected packet's source files. It never clones the repository or installs dependencies itself. Choose the smallest reservation covering the command's expected dependencies and outputs; use the project's existing environment when an isolated install adds no test value.

```bash
python3 /path/to/duo/scripts/workspace.py --state /private/task/workspace.json \
  run --name consumer-check --reserve-mib 1024 --timeout 600 \
  --packet /private/task/workspace.data/packets/ACTUAL_HASH/manifest.json \
  -- bash /absolute/path/to/existing-disposable-check.sh
```

This runner is for disposable checks. Keep implementation commits, human changes and irreplaceable outputs in the canonical checkout or a recorded builder worktree. Put final assertions/results on stdout/stderr, or save a necessary artifact to its declared durable destination before the command ends. The receipt records the input packet and rechecks its source at completion; source drift returns exit 3. The receipt and logs survive success, failure and timeout; scratch is removed after the process group stops. A signal/host crash may leave an unresolved reservation: inspect `status`, stop remaining processes through their host, then use `recover --name NAME --id EXACT_RUN_ID`. Recovery refuses a live runner/process group, replaced directory or changed ownership marker. A crash during launch before the child ID is saved has an unknown process outcome and requires host inspection; automatic recovery stays blocked. It never adopts or deletes arbitrary old folders.

The default managed-storage budget is 2048 MiB per task. Admission reserves capacity atomically across concurrent runs; usage monitoring stops over-budget commands and checks fast completions too. `status` reports actual logical bytes and outstanding reservations. This is cooperative monitoring, not an OS disk quota or security sandbox: a command can exceed the limit between checks and can write elsewhere if its host permits. Keep host permissions and spending controls. For a justified larger job, record the estimate and use `budget --mib AMOUNT --reason REASON`; changing tasks/paths to escape the limit is invalid. Logs and packets also consume the budget. Preserve required evidence and explicitly retire obsolete evidence before extending it without need.

Reuse the package manager's normal download cache when compatible; isolated installs can still require separate writable `node_modules`. Sharing one writable dependency tree between incompatible concurrent jobs is unsafe. Keep native provider configuration/history stable for resume. Tool cache, installed dependencies and provider prompt-cache hits are distinct; measure the relevant one.

## Freeze only required source

Select the changed source plus the diff, necessary callers/contracts/tests and written acceptance. Prepare any diff/spec file under a declared source-relative path before capture; leave credentials, customer data and unrelated artifacts out. The helper only accepts explicit regular files and rejects dependency/cache/Git directories and symlink traversal. Each packet is capped at 64 MiB as well as the task storage budget. Required generated artifacts can be explicitly selected; directories are never copied implicitly.

```bash
python3 /path/to/duo/scripts/review_packet.py make \
  --state /private/task/workspace.json \
  --file src/example.py --file tests/test_example.py --file review-inputs/change.diff
python3 /path/to/duo/scripts/review_packet.py check \
  --manifest /path/returned/by/make/manifest.json
```

Unchanged files produce the same content-addressed packet. Independent reviewers may read the same packet while retaining separate contexts and withholding each other's reports. Give the actual manifest/source paths through the selected transport's supported read/attachment boundary. A minimal packet must still include every dependency required by the review; missing material is incomplete coverage, not permission for a full repository clone. Read-only reviews reuse builder test evidence unless another execution resolves a concrete uncertainty.

For Duo source review, pass the manifest as `pair.py run --packet MANIFEST` alongside its existing flags. The helper checks packet integrity and current source before/after dispatch. Source drift returns exit 3 and unverified evidence while preserving the completed native conversation for focused follow-up. Legacy `--snapshot` alone is only a label and reports unverified source. For other Orkestra routes, run `check` before dispatch and after collecting results; store the manifest hash, actual reviewer/model/session, coverage and verdict together. Hash verification establishes source identity, not that the model read every required file or that a claimed PASS is correct. Require substantive coverage and adjudication.

After fixes, rebuild the packet and refresh affected review. Deleted files must appear in the frozen diff; a changed file omitted from the manifest has no source-validity coverage. Final acceptance identifies the actual integrated commit/tree and links the reviews that still apply. A previous PASS cannot close changed requirements.

## Close or resume

At handoff or completion, report the canonical checkout, exact source version, workspace-state path, active runs/worktrees and remaining temporary bytes. Read `status`; every open reservation has an active purpose or explicit recovery step. Successful closure includes cleaned disposable checks.

For each completed builder worktree, preserve the needed commits, dirty and untracked changes, and evidence first; confirm no active process or unfinished owner. Archive host-managed worktrees with the host's recoverable archive API. For ordinary checkouts, verify a restorable commit/bundle or explicit preservation before removing them through the normal authorized filesystem workflow. A branch/commit ID alone does not prove a different repository has its objects. Preserve needed ignored files separately. Leave the canonical checkout available while the task continues.

For legacy accumulation, inventory paths and sizes read-only, distinguish source/unique work from reproducible installations, then establish ownership and preservation before cleanup. Folder age, a PASS file or a name such as `snapshot` is insufficient evidence to delete it. The helper's automatic cleanup covers only directories it created for a recorded disposable run; migration does not silently clean historical repositories or conversations.
