#!/usr/bin/env bash
# Link instructions into local clients. Native tools and accounts stay user-owned.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
CHECK=false
NO_SETUP=false
SELECTED=""
MODEL_ARGS=()
# Bash 3.2 with nounset needs guarded expansion of an empty array below.
usage() {
  cat <<'USAGE'
Usage: bash install.sh [--skill NAME | --collection coding] [--check] [--no-setup]
                       [--model ROLE=MODEL:EFFORT]
  Default: install the five Coding skills into Claude Code and Codex.
  --skill NAME       Install one skill; Orkestra includes Duo.
  --collection coding  Install the Coding collection.
  --check            Read-only links/model status; no network or model calls.
  --no-setup         Link instructions without interactive Duo model/account setup.
  --model ROLE=MODEL:EFFORT  Select a Duo/Orkestra role; repeat for more roles.
USAGE
}
while [ "$#" -gt 0 ]; do
  case "$1" in
    --skill)
      [ "$#" -ge 2 ] || { usage >&2; exit 2; }
      SELECTED="$2"; shift 2;;
    --collection)
      [ "$#" -ge 2 ] && [ "$2" = coding ] || { usage >&2; exit 2; }
      shift 2;;
    --orkestra-profile)
      [ "$#" -ge 2 ] && [ "$2" = normal ] || { echo 'This release supports the normal Orkestra profile.' >&2; exit 2; }
      shift 2;;
    --model)
      [ "$#" -ge 2 ] || { usage >&2; exit 2; }
      MODEL_ARGS+=("$2"); shift 2;;
    --check) CHECK=true; shift;;
    --no-setup) NO_SETUP=true; shift;;
    --help|-h) usage; exit 0;;
    *) usage >&2; exit 2;;
  esac
done
case "$SELECTED" in
  ''|duo|orkestra|project-context|let-chinese|let-chinese-somehow) ;;
  *) echo 'Unknown skill. Use --help for installation options.' >&2; exit 2;;
esac
command -v python3 >/dev/null 2>&1 || { echo 'Install Python 3.9+ and rerun.' >&2; exit 1; }
python3 -c 'import sys; sys.exit(sys.version_info < (3,9))' || { echo 'Python 3.9+ is required.' >&2; exit 1; }
resolve_path() {
  python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve())' "$1"
}
INSTALL_HOME="$(resolve_path "${SKILLS_INSTALL_HOME:-${HOME:?Home directory is required}}")"
CLAUDE_INSTALL_HOME="$(resolve_path "${CLAUDE_CONFIG_DIR:-$INSTALL_HOME/.claude}")"
CODEX_INSTALL_HOME="$(resolve_path "${CODEX_HOME:-$INSTALL_HOME/.codex}")"
SETUP_STATE_DIR="$(resolve_path "${DUO_STATE_DIR:-${HOME:?}/.local/state/duo}")"
WITH_DUO=false
PROFILE=duo
if [ -z "$SELECTED" ] || [ "$SELECTED" = duo ] || [ "$SELECTED" = orkestra ]; then
  WITH_DUO=true
  [ "$SELECTED" = duo ] || PROFILE=normal
fi
if [ "${#MODEL_ARGS[@]}" -gt 0 ] && { ! $WITH_DUO || $NO_SETUP; }; then
  echo 'Model selections require Duo/Orkestra setup; omit --no-setup.' >&2; exit 2
fi
if $WITH_DUO; then
  CHECK_ARGS=(--check --profile "$PROFILE")
  for choice in ${MODEL_ARGS[@]+"${MODEL_ARGS[@]}"}; do CHECK_ARGS+=(--set "$choice"); done
  # Validate setup choices before moving any existing skill directories.
  env DUO_STATE_DIR="$SETUP_STATE_DIR" CODEX_HOME="$CODEX_INSTALL_HOME" CLAUDE_CONFIG_DIR="$CLAUDE_INSTALL_HOME" \
    PYTHONDONTWRITEBYTECODE=1 python3 "$ROOT/skills/duo/scripts/setup_models.py" "${CHECK_ARGS[@]}" >/dev/null
fi
for name in duo orkestra project-context let-chinese let-chinese-somehow; do
  [ -z "$SELECTED" ] || [ "$name" = "$SELECTED" ] || { [ "$SELECTED" = orkestra ] && [ "$name" = duo ]; } || continue
  source_dir="$ROOT/skills/$name"
  [ -f "$source_dir/SKILL.md" ] || { echo "Incomplete checkout: missing $name." >&2; exit 1; }
  for target in "$CLAUDE_INSTALL_HOME/skills" "$CODEX_INSTALL_HOME/skills"; do
    dest="$target/$name"
    if $CHECK; then
      printf '%s: %s -> %s\n' "$name" "$dest" "$(readlink "$dest" 2>/dev/null || echo 'not linked')"
      continue
    fi
    mkdir -p "$target"
    if [ -L "$dest" ]; then
      [ "$(readlink "$dest")" != "$source_dir" ] || continue
      rm "$dest"
    elif [ -e "$dest" ]; then
      backup="$dest.bak-$(date +%Y%m%d%H%M%S)"
      count=0
      while [ -e "$backup" ] || [ -L "$backup" ]; do
        count=$((count + 1)); backup="$dest.bak-$(date +%Y%m%d%H%M%S)-$count"
      done
      mv "$dest" "$backup"
      printf 'Preserved existing skill: %s\n' "$backup"
    fi
    ln -s "$source_dir" "$dest"
    printf 'Linked %s\n' "$dest"
  done
done
if $WITH_DUO; then
  SETUP_SCRIPT="$ROOT/skills/duo/scripts/setup.sh"
  printf -v SETUP_COMMAND 'env %q %q %q bash %q %q' "DUO_STATE_DIR=$SETUP_STATE_DIR" "CODEX_HOME=$CODEX_INSTALL_HOME" "CLAUDE_CONFIG_DIR=$CLAUDE_INSTALL_HOME" "$SETUP_SCRIPT" "$PROFILE"
  for choice in ${MODEL_ARGS[@]+"${MODEL_ARGS[@]}"}; do printf -v quoted ' %q' "$choice"; SETUP_COMMAND+="$quoted"; done
  if $CHECK; then
    env DUO_STATE_DIR="$SETUP_STATE_DIR" CODEX_HOME="$CODEX_INSTALL_HOME" CLAUDE_CONFIG_DIR="$CLAUDE_INSTALL_HOME" \
      PYTHONDONTWRITEBYTECODE=1 python3 "$ROOT/skills/duo/scripts/setup_models.py" "${CHECK_ARGS[@]}"
  elif ! $NO_SETUP; then
    if [ -t 0 ]; then
      if ! env DUO_STATE_DIR="$SETUP_STATE_DIR" CODEX_HOME="$CODEX_INSTALL_HOME" CLAUDE_CONFIG_DIR="$CLAUDE_INSTALL_HOME" \
        bash "$SETUP_SCRIPT" "$PROFILE" ${MODEL_ARGS[@]+"${MODEL_ARGS[@]}"}; then
        printf 'Skills are linked; model/account setup is incomplete. Run %s in your terminal.\n' "$SETUP_COMMAND" >&2
        exit 1
      fi
    else
      printf 'For model choices and native login, run %s in your own terminal.\n' "$SETUP_COMMAND"
    fi
  fi
fi
if ! $CHECK && ! $NO_SETUP; then
  case "$SELECTED" in
    ''|let-chinese|let-chinese-somehow)
      echo 'OpenCode/Zro are separate prerequisites. Follow the selected skill first-use instructions in your terminal; this installer does not install tools or start provider calls.';;
  esac
fi
