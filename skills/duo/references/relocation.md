# Move a checkout binding without losing the conversation

Use only when the user intends to continue the same Duo task from a different physical checkout. A native desktop chat handoff and a Duo checkout relocation are separate operations. This helper does not move desktop chats, source files, branches, installed dependencies or native transcripts. Keep the old checkout and ignored evidence until their owner confirms preservation and closure. Do not create a replacement peer.

## Prepare and apply

Confirm both seats are idle for migration (no automated/manual peer call and no competing owner mutation); direct native use bypasses Duo's cooperative lock. The coordinator may run the relocation itself. Preserve unique files and resolve dirty or untracked source first. Use an existing clean destination with the same Git common repository and tracked tree/content. Different HEADs with identical trees are recorded explicitly. First version supports Git roots. Initialized submodules must be clean at their recorded commit; empty uninitialized submodules may remain unopened. Their states are recorded, never initialized or moved by the helper. Arbitrary folders are unsupported.

Keep pair, shared index and workspace records outside both checkouts. Keep the same native configuration homes. Discover the exact canonical pair/task/owner with `pair.py list/show`; never infer identity from a title. Run from any existing directory:

```bash
python3 /path/to/duo/scripts/relocate.py plan \
  --pair /private/task/pair.json --task-id ACTUAL_TASK_ID \
  --owner codex --thread ACTUAL_CURRENT_OWNER_ID \
  --to /actual/new/project --reason 'Owner requested stable project directory' \
  --native-idle-confirmed --output /private/task/relocation-plan.json
python3 /path/to/duo/scripts/relocate.py apply \
  --plan /private/task/relocation-plan.json --expect SHA256_PRINTED_BY_PLAN
```

Planning changes no binding. The private plan freezes source identities, tree/content, pair/workspace/index entry and native peer history. Apply rechecks them under pair → workspace → index locks, persists a journal and updates only the workdir bindings. Task, owner, peer, model, native homes, cursors, review evidence and storage reservations remain intact. A stale plan needs inspection and a new plan; it is not permission to force the move. Concurrent unrelated index entries survive. Prior checkout paths remain discoverable in `moved_from`; default initialization from an old path cannot silently replace the task. Pending relocations are listed explicitly without blocking discovery of other tasks.

If the original folder is already missing, or was reconstructed at the same path with a different physical identity, additionally pass `--source-commit FULL_COMMIT --source-bundle /private/verified.bundle`. The bundle must be standalone and advertise that exact commit; its recovered tree must equal the destination. A reconstructed folder must also be clean, in the same repository, at that exact commit and match destination tracked content. This verifies **committed source recovery only**. Independently verify prior dirty/untracked/ignored preservation; the helper cannot reconstruct or prove bytes already lost before planning. It never deletes either checkout.

## Interrupted operation

A pending journal blocks managed dispatch, handoff, manual use, adoption/initialization of that task and workspace mutations. Inspect the returned journal and current files. Roll back only that exact pending operation:

```bash
python3 /path/to/duo/scripts/relocate.py rollback \
  --pair /private/task/pair.json --task-id ACTUAL_TASK_ID \
  --owner codex --thread ACTUAL_CURRENT_OWNER_ID --transaction-id EXACT_PENDING_ID
```

Rollback accepts only the recorded before/after states and restores only this task's index entry. Unknown edits remain blocked and preserved for inspection. An interrupted rollback can be retried. A completed relocation is not silently undone: continuing elsewhere requires another explicit validated plan. If the old folder was missing, rollback restores the original missing binding; it does not make that folder usable.

## Resume and evidence

Use `show` to obtain commands with the new cwd. Continue exact session IDs through managed `sync/ack/run`; relocation does not acknowledge unread decisions. Claude Code 2.1.223+ finds an exact `--resume UUID` across project directories; do not copy transcripts to make a picker entry. Current helper validation still requires unique retained history and a newly persisted response. [Claude sessions](https://code.claude.com/docs/en/sessions)

Report metadata relocation separately from a real new-directory resume test. Offline fake-provider tests prove helper routing/guards, not native provider acceptance. Retain old review packets unchanged: their path/inode bindings are historical; capture new inputs before a subsequent source review. Do not repeat unchanged product reviews merely to move a checkout.
