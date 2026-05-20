#!/usr/bin/env bash
set -euo pipefail
trap 'echo "FAIL: $BASH_SOURCE:$LINENO" >&2; exit 1' ERR

echo "== Tools present =="
for t in git curl bash eza rg zoxide fzf tmux delta starship nvim keychain; do
    command -v "$t" >/dev/null 2>&1 || { echo "MISSING: $t"; exit 1; }
done
# WSL-only tools should be absent
if command -v wslview >/dev/null 2>&1; then
    echo "ERROR: wslview should not be present on devbox"; exit 1
fi
echo "  ok"

echo "== ~/.bashrc sources modular files =="
grep -q '/.config/bash/' "$HOME/.bashrc"

echo "== LazyVim launches with LSP support =="
nvim --headless "+Lazy! sync" "+qa" 2>/dev/null

echo "== tmux config OK =="
tmux -f "$HOME/.tmux.conf" -L smoke new -d -s smoke "exit"
tmux -L smoke kill-server 2>/dev/null || true

echo "ALL SMOKE TESTS PASSED for profile=devbox"
