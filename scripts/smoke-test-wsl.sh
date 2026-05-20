#!/usr/bin/env bash
# Smoke test for the wsl profile. Exit 0 on success, non-zero on first failure.
set -euo pipefail
trap 'echo "FAIL: $BASH_SOURCE:$LINENO" >&2; exit 1' ERR

echo "== Tools present =="
for t in git curl bash eza batcat fdfind rg zoxide fzf tmux delta starship nvim keychain; do
    command -v "$t" >/dev/null 2>&1 || { echo "MISSING: $t"; exit 1; }
done
echo "  ok"

echo "== ~/.bashrc sources modular files =="
grep -q '/.config/bash/' "$HOME/.bashrc"
echo "  ok"

echo "== ble.sh installed =="
test -r "$HOME/.local/share/blesh/ble.sh"
echo "  ok"

echo "== Nerd Font installed (Linux) =="
fc-list 2>/dev/null | grep -qi 'jetbrainsmono.*nerd'
echo "  ok"

echo "== starship config exists =="
test -r "$HOME/.config/starship.toml"
echo "  ok"

echo "== LazyVim launches and exits cleanly =="
nvim --headless "+Lazy! sync" "+qa" 2>/dev/null
echo "  ok"

echo "== tmux config loads without error =="
tmux -f "$HOME/.tmux.conf" -L smoke kill-server 2>/dev/null || true
tmux -f "$HOME/.tmux.conf" -L smoke new -d -s smoke "exit"
tmux -L smoke kill-server 2>/dev/null || true
echo "  ok"

echo "== Git delta wired =="
git config --get core.pager | grep -q delta
echo "  ok"

echo "ALL SMOKE TESTS PASSED for profile=wsl"
