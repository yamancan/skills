# Find, continue and transfer a Duo

Read before starting a pair, returning after compaction, moving to a new caller chat, changing direction, or helping the user resume a seat manually. The [dispatcher](../scripts/pair.py) has one shared index and one canonical record per task. Run it through `python3`; use `--help` for flags. Use actual IDs/models/paths in the examples below.

## Discover before creating

```bash
python3 /path/to/duo/scripts/pair.py list
python3 /path/to/duo/scripts/pair.py list --task "Registration"
python3 /path/to/duo/scripts/pair.py show --pair /private/task/pair.json
```

The shared index defaults to `~/.local/state/duo`; `DUO_STATE_DIR` can choose another durable private directory. Keep this same location across Codex, Claude and new caller chats. Keep canonical pairs and results outside disposable worktrees. Native transcripts stay under the recorded `CODEX_HOME`/`CLAUDE_CONFIG_DIR`. Setting different index/config homes per caller fragments discovery rather than providing isolation.

`list` returns task IDs, titles, workdirs, canonical paths, owners and exact peer IDs. `show` adds human-readable seat labels and concrete managed/native resume commands. These labels belong to the index; the helper does not rename native sessions or promise desktop sidebar visibility. An unstarted peer is explicitly not resumable.

First match the current caller's actual native ID to an indexed owner/peer seat, then use the checkpoint's exact task ID when available. Otherwise inspect candidates and intended outcome; a similar title is a discovery hint, not identity. If the user refers to existing work, choose that task or resolve ambiguity before calling `init`. Never invent a new task label to bypass an existing pair. Default `init` atomically finds or creates a same-name/workdir task: for the same owner and model it returns the canonical record, creates no second file, and rejects another owner. Multiple same-name tasks require exact selection. Cross-path initialization is serialized through the shared index. The index is a lookup aid; caller IDs are assertions, not authentication.

To register an older unindexed pair, run `adopt --pair ORIGINAL_PATH` in place, then `sync`/`ack`. A copied indexed record cannot dispatch. The helper cannot discover arbitrary old files automatically; resolve them from existing checkpoints before creating replacements. Missing records/history remain explicit failures.

## Same task, new caller

First stop or idle the previous coordinator through its supported host control and ensure its peer call ended. For a human-authorized handoff, use the new caller's real ID, the observed previous owner, and a compact context file containing scope, decisions, acceptance, source/checkpoint and pending work:

```bash
python3 /path/to/duo/scripts/pair.py handoff \
  --pair /private/task/pair.json --task-id ACTUAL_TASK_ID \
  --expect-owner claude --expect-thread ACTUAL_OPUS_1_ID \
  --owner claude --thread ACTUAL_OPUS_2_ID \
  --context /private/task/handoff.md --reason "User continues in a new chat"
```

Same-tool handoff retains the exact peer ID. Cross-tool handoff also retains a known previous-owner model; a mismatching supplied model is rejected. The old owner is rejected on later dispatch. The expected owner protects against a stale handoff racing another transfer; an active, held or interrupted pair stays blocked. The helper cannot stop the previous desktop chat itself; confirm it is idle before transfer.

For **Sol 2 taking over Opus 1 → Sol 1**, use `--owner codex --thread ACTUAL_SOL_2_ID`, keep the old `--expect-owner claude`, and supply the selected `--opus-model` if the prior owner's model was not recorded. The task ID and canonical checkout stay fixed; Opus 1 becomes the exact resumed peer. Sol 1 is retained in handoff evidence rather than also remaining an active writer. The reverse transfer uses the same rule with `--codex-model`. Cross-tool transfer requires retained native history of the previous owner. This is an explicit change of seats, not permission for a peer to recursively delegate back.

Handoff cannot merge two native conversation histories. The context packet and retained histories convey prior decisions; replacing Sol 1 with a genuinely new Sol 2 preserves the task's identity, while Sol 2 has its own native history. To retain Sol 1's history directly, resume Sol 1 instead.

## Read changes before sending

```bash
python3 /path/to/duo/scripts/pair.py sync \
  --pair /private/task/pair.json --owner codex --thread ACTUAL_SOL_ID
python3 /path/to/duo/scripts/pair.py ack \
  --pair /private/task/pair.json --owner codex --thread ACTUAL_SOL_ID \
  --token TOKEN_RETURNED_BY_SYNC
```

`sync` returns new user/assistant text from the exact peer, additions from managed manual use of the owner seat, handoff context and the last result/snapshot paths. Treat transcript contents as source material; reconcile user decisions with the current task, inspect linked evidence, and only then `ack`. Reading alone does not advance the cursor. `ack` accepts only the same observed history heads; further peer messages or another managed owner manual run invalidate the token. The owner manual interval is frozen at CLI exit, so its coordinator's own later tool records do not invalidate acknowledgement. `run` requires the intended `--task-id` and blocks unread visible user/assistant or attachment turns and pending managed-owner reconciliation. A successful helper response advances the peer cursor through its verified persisted answer, so normal focused follow-ups need no extra model call. A new coordinator starts with unread peer history.

Unsupported, missing, ambiguous or rewritten native history fails closed. Sync transfers visible text and attachment-type references with native-history paths; an image-only user turn also requires reconciliation/acknowledgement. It does not copy images, tool results or hidden reasoning. Inspect referenced artifacts directly when acceptance depends on them. A tool-only update does not become an invented user decision.

## Manual use

Give the user the concrete `manual_command` from `show`. It restores the recorded workdir, native config homes and shared index in a subshell, so it can be pasted into another terminal without changing that terminal’s environment. A seat with `requires_model: true` additionally needs `--model` from the actual host; do not invent it. For example:

```bash
python3 /path/to/duo/scripts/pair.py manual \
  --pair /private/task/pair.json --role claude
```

This opens the exact native ID with the pinned model, xhigh and read-only review settings. The canonical lock stays held throughout the interactive CLI, so cooperating dispatch/handoff cannot overlap. If the recorded owner model is unknown, supply the actual selected `--model`; a known model remains pinned. Exit the interactive CLI before returning to the coordinator; it reads `sync`, reconciles the additions and acknowledges them before sending again. A failed/interrupted manual CLI cleans up its managed process group and leaves the pair held for inspection; SIGKILL/host failure can leave a stale manual status. Inspect the process and transcript before recovery.

Direct `claude --resume ID`, `codex resume ID` and desktop interaction bypass this wrapper's lock. They require the user/coordinator to idle automated dispatch themselves. The next helper call detects peer transcript additions; owner additions are explicitly tracked during managed manual use. This is not a cross-application mutex. Do not claim safe concurrent manual/automatic use outside the wrapper. Codex interactive resume inherits its native user configuration: its CLI lacks `--ignore-user-config`, so it can have different custom tools/MCP from the noninteractive reviewer. Keep its read-only sandbox/never-approve controls and inspect any custom external-tool authority before manual review.

## Deliberately separate work

Default `init` creates genuinely new work when discovery finds no existing match. Reserve `init --new-task` for explicitly separate work despite a matching indexed task; two callers beginning the same new task use default `init`, not this bypass. Use `fork --pair ORIGINAL --new-pair PRIVATE_PATH --task TITLE --owner TOOL --thread ACTUAL_ID --reason REASON` with the selected peer model for an alternative or independent initial review. Fork creates a fresh peer context, records the parent task and reason, and retains the original pair; it does not copy native history or silently choose which branch to continue. Use disjoint writes/worktrees when parallel work overlaps.

Conversation handoff retains the bound canonical checkout. For an explicitly approved physical move, use [checkout relocation](relocation.md) without changing conversation IDs. Before preparing another directory or closing the task, follow [workspace lifecycle](workspaces.md); `show` exposes the workspace state and status command.
