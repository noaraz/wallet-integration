#!/usr/bin/env bash
# Blocks Edit/Write on secrets. Wired from .claude/settings.json PreToolUse.
# The target path arrives via $CLAUDE_TOOL_INPUT_FILE_PATH (or stdin JSON).

set -euo pipefail

path="${CLAUDE_TOOL_INPUT_FILE_PATH:-}"

# Fall back to reading the tool payload from stdin when the env var is empty.
if [[ -z "$path" ]] && [[ ! -t 0 ]]; then
  payload=$(cat)
  path=$(printf '%s' "$payload" | python3 -c 'import json,sys;
try:
    d=json.load(sys.stdin)
    print(d.get("tool_input",{}).get("file_path","") or d.get("file_path",""))
except Exception:
    pass' 2>/dev/null || true)
fi

[[ -z "$path" ]] && exit 0

base=$(basename "$path")
case "$base" in
  .env|.env.*|*-service-account*.json|*credentials*.json|*.pem|*.key)
    echo "pre_edit_guard: refusing to edit secret file: $path" >&2
    exit 2
    ;;
esac

# Also block anything under a .secrets/ path.
case "$path" in
  *"/.secrets/"*)
    echo "pre_edit_guard: refusing to edit file under .secrets/: $path" >&2
    exit 2
    ;;
esac

exit 0
