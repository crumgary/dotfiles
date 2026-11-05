#!/usr/bin/env bash
# Verify that live-only shell, agent, and Git customizations survive reconciliation.
# Fixture HOME changes intentionally live in isolated subshells.
# shellcheck disable=SC2030,SC2031,SC1091
set -uo pipefail

PUBLIC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PRIV_ROOT="${DOTFILES_PRIV_DIR:-$HOME/.config/dotfiles-priv}"
WORK_ROOT="${DOTFILES_WORK_DIR:-$HOME/.config/dotfiles-work}"
TEST_TMP="$(mktemp -d /tmp/opencode-dotfiles-reconciliation.XXXXXX)"
trap 'rm -rf "$TEST_TMP"' EXIT

failures=0
pass=0
check() {
    local name="$1"
    shift
    if "$@"; then
        printf 'ok %d - %s\n' "$((++pass))" "$name"
    else
        printf 'not ok - %s\n' "$name" >&2
        failures=$((failures + 1))
    fi
}

shell_tools_behavior() (
    export HOME="$TEST_TMP/shell-home"
    export PATH="/usr/bin:/bin"
    mkdir -p "$HOME/.local/share/pnpm/bin" "$HOME/.bash_completion.d"
    printf 'HERDR_COMPLETION_SOURCED=1\n' > "$HOME/.bash_completion.d/herdr"
    printf 'OPENCODE_COMPLETION_SOURCED=1\n' > "$HOME/.bash_completion.d/opencode"

    . "$PUBLIC_ROOT/home/dot_config/bash/20-tools.sh"

    case ":$PATH:" in *":$HOME/.local/share/pnpm/bin:"*) ;; *) return 1 ;; esac
    case ":$PATH:" in *":$HOME/.local/share/pnpm:"*) ;; *) return 1 ;; esac
    [ "${HERDR_COMPLETION_SOURCED:-}" = 1 ] || return 1
    [ "${OPENCODE_COMPLETION_SOURCED:-}" = 1 ] || return 1
)

personal_alias_behavior() (
    export HOME="$TEST_TMP/personal-home"
    mkdir -p "$HOME"
    . "$PRIV_ROOT/init.sh"
    alias awh 2>/dev/null | grep -F 'agent-work-hub/current/bin/agent-work-hub' >/dev/null
)

rendered_agent_overlays() {
    local rendered
    rendered="$(chezmoi --source "$PUBLIC_ROOT" cat --no-pager "$HOME/.config/agents/AGENTS.md")" || return 1
    grep -F "@$HOME/.config/dotfiles-priv/agents/AGENTS.md" <<< "$rendered" >/dev/null || return 1
    grep -F "@$HOME/.config/dotfiles-work/agents/AGENTS.md" <<< "$rendered" >/dev/null || return 1
    [ -r "$PRIV_ROOT/agents/AGENTS.md" ] || return 1
    [ -r "$WORK_ROOT/agents/AGENTS.md" ] || return 1
}

rendered_git_overlay() {
    local rendered
    rendered="$(chezmoi --source "$PUBLIC_ROOT" cat --no-pager "$HOME/.gitconfig")" || return 1
    grep -F 'path = ~/.config/dotfiles-work/git/work.conf' <<< "$rendered" >/dev/null || return 1
    [ -r "$WORK_ROOT/git/work.conf" ] || return 1
}

check 'shell startup preserves pnpm paths and agent completions' shell_tools_behavior
check 'personal overlay defines the awh alias' personal_alias_behavior
check 'chezmoi renders readable personal and work agent overlays' rendered_agent_overlays
check 'chezmoi renders the work Git overlay' rendered_git_overlay

if [ "$failures" -ne 0 ]; then
    printf '%d reconciliation check(s) failed\n' "$failures" >&2
    exit 1
fi
printf 'All reconciliation checks passed\n'
