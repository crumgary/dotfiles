#!/usr/bin/env bash
# link-source.sh — make chezmoi use THIS clone as its source directory.
#
# chezmoi looks for its source state in ~/.local/share/chezmoi by default.
# If you'd rather keep the repo somewhere friendlier (e.g. ~/github/...),
# clone it there and run this script: it symlinks the default location to
# this clone, so every `chezmoi` command works with no --source flag and no
# sourceDir entry in chezmoi.toml (which `chezmoi init` would clobber anyway).
#
# Idempotent: re-running when the link is already correct is a no-op.
#
# Usage:
#   ./scripts/link-source.sh           create or refresh the symlink
#   ./scripts/link-source.sh --force   replace a real dir already sitting there

set -euo pipefail

# Repo root — prefer git, fall back to walking up from this script's dir.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! repo_dir="$(git -C "$script_dir" rev-parse --show-toplevel 2>/dev/null)"; then
    repo_dir="$(cd "$script_dir/.." && pwd)"
fi

target="${XDG_DATA_HOME:-$HOME/.local/share}/chezmoi"

force=0
[ "${1:-}" = "--force" ] && force=1

mkdir -p "$(dirname "$target")"

if [ -L "$target" ]; then
    current="$(readlink -f "$target")"
    if [ "$current" = "$repo_dir" ]; then
        echo "✓ Already linked: $target -> $repo_dir"
        exit 0
    fi
    echo "Re-pointing symlink (was -> $current)"
    ln -sfn "$repo_dir" "$target"
elif [ -e "$target" ]; then
    if [ "$force" -eq 1 ]; then
        echo "Replacing existing $target (--force)"
        rm -rf "$target"
        ln -sfn "$repo_dir" "$target"
    else
        echo "ERROR: $target exists and is not a symlink." >&2
        echo "  If it's an old chezmoi clone you no longer need, re-run with --force to replace it." >&2
        exit 1
    fi
else
    ln -sfn "$repo_dir" "$target"
fi

echo "✓ Linked: $target -> $repo_dir"
if command -v chezmoi >/dev/null 2>&1; then
    echo "  chezmoi source-path: $(chezmoi source-path)"
fi
