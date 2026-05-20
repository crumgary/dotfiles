#!/usr/bin/env bash
set -eu
trap 'echo "FAIL"; exit 1' ERR

echo "== Minimal bash + vim present =="
command -v bash
command -v vi || command -v vim

echo "== ~/.vimrc present =="
test -r "$HOME/.vimrc"
echo "  ok"

echo "== /.bashrc not requiring nonexistent tools =="
bash -i -c "ls >/dev/null && exit" </dev/null
echo "  ok"

echo "ALL SMOKE TESTS PASSED for profile=embedded"
