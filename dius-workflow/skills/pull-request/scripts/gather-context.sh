#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "ERROR: $1" >&2
  exit 1
}

gh auth status >/dev/null 2>&1 || fail "GitHub CLI is not authenticated. Run 'gh auth login'."
git fetch origin --quiet || fail "Could not fetch from origin."

BRANCH=$(git branch --show-current)
[[ -n "$BRANCH" ]] || fail "HEAD is detached. Check out a branch first."
DEFAULT_BRANCH=$(gh repo view --json defaultBranchRef --jq .defaultBranchRef.name)
PR_BASE=$(gh pr view --json baseRefName --jq .baseRefName 2>/dev/null || true)
BASE="${1:-${PR_BASE:-$DEFAULT_BRANCH}}"
git rev-parse --verify --quiet "origin/${BASE}" >/dev/null || fail "Base branch 'origin/${BASE}' does not exist."
MERGE_BASE=$(git merge-base "origin/${BASE}" HEAD)
DIFF_EXCLUDES=(-- ':/' ':(exclude,top)*.lock' ':(exclude,top)*package-lock.json' ':(exclude,top)*pnpm-lock.yaml')

echo "=== BRANCH ==="
echo "$BRANCH"

echo ""
echo "=== DEFAULT_BRANCH ==="
echo "$DEFAULT_BRANCH"

echo ""
echo "=== BASE ==="
echo "$BASE"

echo ""
echo "=== EXISTING_PR ==="
gh pr view --json number,title,body,baseRefName --jq '.' 2>/dev/null || echo "NONE"

echo ""
echo "=== STATUS ==="
git status --short

echo ""
echo "=== COMMITS ==="
git log "${MERGE_BASE}..HEAD" --format='%h %s%n%b'

echo ""
echo "=== DIFF_STAT ==="
git diff "$MERGE_BASE" --stat "${DIFF_EXCLUDES[@]}"

echo ""
echo "=== DIFF ==="
git diff "$MERGE_BASE" --irreversible-delete "${DIFF_EXCLUDES[@]}"
