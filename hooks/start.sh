#!/usr/bin/env bash
# Session-start greeter. Prints current focus + branch + phase status
# so Claude picks up the right context immediately.

set -euo pipefail

here=$(cd "$(dirname "$0")/.." && pwd)
cd "$here"

echo "=== wallet-integration ==="

if [[ -f STATUS.md ]]; then
  # Print "Last updated" + "Current Focus" lines if present
  grep -E '^(Last updated|## Current Focus|\*\*Phase [0-9]+)' STATUS.md | head -5 || true
fi

branch=$(git branch --show-current 2>/dev/null || echo "")
if [[ -n "$branch" ]]; then
  echo "branch: $branch"
fi

echo ""
echo "workflow reminders:"
echo "  * main is protected — work on a feature branch"
echo "  * start every phase with /superpowers:brainstorming"
echo "  * implement via /superpowers:test-driven-development (TDD is required)"
echo "  * ship via /ship  |  release via /release"

exit 0
