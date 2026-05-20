#!/usr/bin/env bash
set -euo pipefail
trap 'echo "FAIL: $BASH_SOURCE:$LINENO" >&2; exit 1' ERR

echo "== Core tools present =="
for t in git bash fzf tmux nvim; do
    command -v "$t" >/dev/null 2>&1 || { echo "MISSING: $t"; exit 1; }
done

echo "== Lab nvim has NO LSP machinery active =="
nvim --headless -c 'lua local ok = pcall(require, "lspconfig"); if ok then vim.cmd("cq") else vim.cmd("q") end' 2>/dev/null
echo "  ok (lspconfig disabled or not installed)"

echo "ALL SMOKE TESTS PASSED for profile=lab"
