#!/usr/bin/env bash
# Choose future-task models, then use each CLI's own account login.
set -euo pipefail

DUO_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ "${1:-}" = "--help" ]]; then
  printf '%s\n' "Usage: bash setup.sh [duo|normal] [ROLE=MODEL:EFFORT ...]"
  exit 0
fi
SETUP_PROFILE="${1:-duo}"
[[ $# -eq 0 ]] || shift
MODEL_ARGS=(--profile "$SETUP_PROFILE")
for choice in "$@"; do MODEL_ARGS+=(--set "$choice"); done
python3 "$DUO_SCRIPT_DIR/setup_models.py" --check "${MODEL_ARGS[@]}"
if [[ ! -t 0 ]]; then
  printf 'Run setup in your own interactive terminal:\n' >&2
  python3 - "$DUO_SCRIPT_DIR/setup.sh" "$SETUP_PROFILE" "$@" >&2 <<'PY'
import os
from pathlib import Path
import shlex
import sys
homes = [('DUO_STATE_DIR', '.local/state/duo'), ('CODEX_HOME', '.codex'), ('CLAUDE_CONFIG_DIR', '.claude')]
settings = [name + '=' + str(Path(os.environ.get(name) or Path.home()/default).expanduser().resolve())
            for name, default in homes]
print(shlex.join(['env', *settings, 'bash', *sys.argv[1:]]))
PY
  exit 1
fi

printf '\n1/2 Choose models and efforts\n'
printf '%s\n' "Edit each model and effort; Enter keeps the displayed choice."
MODEL_ROWS="$(python3 "$DUO_SCRIPT_DIR/setup_models.py" --rows "${MODEL_ARGS[@]}")"
MODEL_ARGS=(--profile "$SETUP_PROFILE")
while IFS=$'\t' read -r -u 3 role model effort allowed; do
  read -r -p "  $role model [$model]: " chosen_model
  read -r -p "  $role effort [$effort] ($allowed): " chosen_effort
  MODEL_ARGS+=(--set "$role=${chosen_model:-$model}:${chosen_effort:-$effort}")
done 3<<< "$MODEL_ROWS"
python3 "$DUO_SCRIPT_DIR/setup_models.py" --check "${MODEL_ARGS[@]}"
if [[ "$SETUP_PROFILE" = "normal" ]]; then
  printf '%s\n' "Saving normal also sets future Duo Codex/Opus model IDs at Duo's required xhigh effort."
fi
printf '%s\n' "Preferences are saved privately; existing pairs keep their pinned models."
read -r -p "Save these choices? [y/N] " reply
[[ "$reply" = [Yy] || "$reply" = [Yy][Ee][Ss] ]] || exit 1
python3 "$DUO_SCRIPT_DIR/setup_models.py" --save "${MODEL_ARGS[@]}"

printf '\n2/2 Sign in through native accounts\n'
printf '%s\n' "Use your intended accounts. Credentials stay in each CLI's native store."
for cli in codex claude; do
  command -v "$cli" >/dev/null 2>&1 || {
    printf 'Missing CLI: %s. Use the official setup link in references/setup.md, then rerun.\n' "$cli" >&2
    exit 1
  }
  case "$cli" in
    codex)
      if ! codex login status >/dev/null 2>&1; then
        codex login
        codex login status >/dev/null 2>&1 || exit 1
      fi;;
    claude)
      if ! claude auth status >/dev/null 2>&1; then
        claude auth login
        claude auth status >/dev/null 2>&1 || exit 1
      fi;;
  esac
done
printf '\n%s\n' "Model preferences saved. Account login does not prove model entitlement or effective effort."
printf '%s\n' "Before first review, inspect installed help and model availability; no paid review was run here."
