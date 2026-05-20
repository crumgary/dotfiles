# ~/.config/bash/40-ssh-agent.sh
# Manage ssh-agent. Prefer keychain (idempotent across shells). Fall back to hand-rolled logic.

# Identity files to load when the agent starts.
SSH_KEYS=()
for k in "$HOME/.ssh/id_ed25519" "$HOME/.ssh/id_rsa" "$HOME/.ssh/id_voyager"; do
    [ -r "$k" ] && SSH_KEYS+=("$k")
done

if command -v keychain >/dev/null 2>&1 && [ ${#SSH_KEYS[@]} -gt 0 ]; then
    # keychain handles agent lifecycle, key adding, and prints env vars to source.
    # NOTE: --agents was deprecated in keychain 2.9; the binary auto-detects ssh now.
    eval "$(keychain --eval --quiet "${SSH_KEYS[@]}")"
else
    # Fallback: minimal ssh-agent management.
    if [ -z "$SSH_AUTH_SOCK" ] && [ -r "$HOME/.ssh_agent_env" ]; then
        . "$HOME/.ssh_agent_env" >/dev/null
    fi
    if ! ssh-add -l >/dev/null 2>&1; then
        if ! pgrep -u "$USER" ssh-agent >/dev/null 2>&1; then
            ssh-agent -s > "$HOME/.ssh_agent_env"
        fi
        [ -r "$HOME/.ssh_agent_env" ] && . "$HOME/.ssh_agent_env" >/dev/null
        for k in "${SSH_KEYS[@]}"; do
            ssh-add "$k" >/dev/null 2>&1 || true
        done
    fi
fi
unset SSH_KEYS k
