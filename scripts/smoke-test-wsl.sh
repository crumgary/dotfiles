#!/usr/bin/env bash
# Smoke test for the wsl profile. Exit 0 on success, non-zero on first failure.
set -euo pipefail
trap 'echo "FAIL: $BASH_SOURCE:$LINENO" >&2; exit 1' ERR

echo "== Tools present =="
for t in git curl bash eza rg zoxide fzf tmux delta starship vim keychain; do
    command -v "$t" >/dev/null 2>&1 || { echo "MISSING: $t"; exit 1; }
done
command -v bat >/dev/null 2>&1 || command -v batcat >/dev/null 2>&1 || { echo "MISSING: bat or batcat"; exit 1; }
command -v fd >/dev/null 2>&1 || command -v fdfind >/dev/null 2>&1 || { echo "MISSING: fd or fdfind"; exit 1; }
echo "  ok"

echo "== ~/.bashrc sources modular files =="
grep -q '/.config/bash/' "$HOME/.bashrc"
echo "  ok"

echo "== ble.sh installed =="
test -r "$HOME/.local/share/blesh/ble.sh"
echo "  ok"

echo "== Nerd Font installed (Linux) =="
# pipefail + grep -q on large output races against SIGPIPE; count first then check.
nerd_count=$(fc-list 2>/dev/null | grep -ic 'jetbrainsmono.*nerd' || true)
[ "${nerd_count:-0}" -gt 0 ] || { echo "  no JetBrainsMono Nerd Font in fc-list"; exit 1; }
echo "  ok ($nerd_count font faces)"

echo "== starship config exists =="
test -r "$HOME/.config/starship.toml"
echo "  ok"

echo "== Vim config loads without errors =="
test -r "$HOME/.vimrc"
vim -n -i NONE -es -u "$HOME/.vimrc" -c 'qa!'
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
