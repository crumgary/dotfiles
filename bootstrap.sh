#!/usr/bin/env bash
# bootstrap.sh — install prereqs, then run chezmoi.
# This is a CONVENIENCE wrapper; the primary install line in the README uses chezmoi's hosted installer directly.

set -euo pipefail

# Prereqs (best-effort; skip if no sudo).
need_install=()
for cmd in git curl unzip; do
    command -v "$cmd" >/dev/null 2>&1 || need_install+=("$cmd")
done

if [ ${#need_install[@]} -gt 0 ]; then
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update -qq && sudo apt-get install -y "${need_install[@]}"
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y "${need_install[@]}"
    else
        echo "Please install: ${need_install[*]}" >&2
        exit 1
    fi
fi

# Install chezmoi (idempotent) and bootstrap.
sh -c "$(curl -fsLS get.chezmoi.io)" -- -b "$HOME/.local/bin" init --apply crumgary/dotfiles

# Final reminder.
cat <<'EOF'

────────────────────────────────────────────────────────────
Dotfiles applied. Quick next steps:
  • Log out + back in (or `exec bash -l`) to pick up the new shell.
  • Open Windows Terminal/VSCode settings and set the font to
    "JetBrainsMono Nerd Font Mono" (WSL only).
  • Read the cheat sheet:  cheat
  • Pull future updates with:  chezmoi update
────────────────────────────────────────────────────────────
EOF
