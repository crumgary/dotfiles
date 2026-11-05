#!/usr/bin/env bash
set -euo pipefail
trap 'echo "FAIL: $BASH_SOURCE:$LINENO" >&2; exit 1' ERR

echo "== Core tools present =="
for t in git bash fzf tmux vim; do
    command -v "$t" >/dev/null 2>&1 || { echo "MISSING: $t"; exit 1; }
done

echo "== Vim config loads without errors =="
test -r "$HOME/.vimrc"
vim -n -i NONE -es -u "$HOME/.vimrc" -c 'qa!'
echo "  ok"

echo "ALL SMOKE TESTS PASSED for profile=lab"
