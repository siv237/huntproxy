#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Install git hooks from the tracked hooks/ directory.
mkdir -p .git/hooks
cp hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

echo "Git hooks installed."
