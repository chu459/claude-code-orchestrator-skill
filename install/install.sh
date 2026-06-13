#!/usr/bin/env bash
set -euo pipefail

CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_ROOT="$CODEX_HOME/skills"
TARGET="$TARGET_ROOT/claude-code-orchestrator"
BACKUP="$TARGET.backup.$(date +%Y%m%d-%H%M%S)"

mkdir -p "$TARGET_ROOT"

if [ -e "$TARGET" ]; then
  mv "$TARGET" "$BACKUP"
  echo "Backed up existing skill to $BACKUP"
fi

mkdir -p "$TARGET"
rsync -a \
  --exclude '.git' \
  --exclude 'runs' \
  --exclude 'reports' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  "$REPO_ROOT/" "$TARGET/"

TOOL_HOME="$TARGET/scripts/cc-orchestrator"

cat <<EOF

Claude Code Orchestrator Skill installed.
Skill path: $TARGET

Run:
  export CC_ORCHESTRATOR_HOME="$TOOL_HOME"
  python "\$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" selftest
  python "\$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" healthcheck

For Codex MCP, add docs/mcp.codex.example.toml to your Codex config.toml.
EOF
