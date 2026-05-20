# ~/.config/bash/30-fzf.sh
# fzf keybindings + completion. Apt installs the keybinding scripts to /usr/share/doc/fzf/examples/.

if command -v fzf >/dev/null 2>&1; then
    # Default options — clean, half-screen, with preview where useful.
    export FZF_DEFAULT_OPTS="--height=40% --layout=reverse --border --info=inline"
    export FZF_CTRL_T_OPTS="--preview 'batcat --color=always --style=numbers --line-range=:200 {} 2>/dev/null || cat {}'"
    export FZF_ALT_C_OPTS="--preview 'eza --tree --level=2 --color=always {} 2>/dev/null || ls -la {}'"

    # Use fd for file listing if present — respects .gitignore.
    if command -v fdfind >/dev/null 2>&1; then
        export FZF_DEFAULT_COMMAND='fdfind --type f --hidden --follow --exclude .git'
        export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
        export FZF_ALT_C_COMMAND='fdfind --type d --hidden --follow --exclude .git'
    elif command -v fd >/dev/null 2>&1; then
        export FZF_DEFAULT_COMMAND='fd --type f --hidden --follow --exclude .git'
        export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
        export FZF_ALT_C_COMMAND='fd --type d --hidden --follow --exclude .git'
    fi

    # Source the keybindings / completion provided by the apt/dnf package.
    for f in \
        /usr/share/doc/fzf/examples/key-bindings.bash \
        /usr/share/doc/fzf/examples/completion.bash \
        /usr/share/fzf/key-bindings.bash \
        /usr/share/fzf/completion.bash; do
        [ -r "$f" ] && . "$f"
    done
    unset f
fi
