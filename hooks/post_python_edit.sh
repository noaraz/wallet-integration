#!/usr/bin/env bash
# Runs ruff --fix on a just-edited .py file, via Docker.
# Silent if Docker isn't available or the image isn't built yet — the
# lint step in /ship is the authoritative check.

set -euo pipefail

path="${CLAUDE_TOOL_INPUT_FILE_PATH:-}"
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
[[ "$path" != *.py ]] && exit 0
[[ ! -f "$path" ]] && exit 0

# Need Docker + the dev image. Bail quietly otherwise.
command -v docker >/dev/null 2>&1 || exit 0
docker image inspect wallet-bot:dev >/dev/null 2>&1 || exit 0

# Relativize the path to the repo root (the compose project root).
repo_root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
rel=${path#"$repo_root/"}

docker compose run --rm --no-TTY bot ruff check --fix --exit-zero "/app/${rel}" >/dev/null 2>&1 || true
docker compose run --rm --no-TTY bot ruff format "/app/${rel}" >/dev/null 2>&1 || true

exit 0
