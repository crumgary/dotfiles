# ~/.config/bash/10-aliases.sh
# Aliases loaded unconditionally (no tool checks). Modern-CLI swaps are in 15-modern.sh.

# Color output for grep family (Ubuntu default behavior, harmless elsewhere).
alias grep='grep --color=auto'
alias fgrep='fgrep --color=auto'
alias egrep='egrep --color=auto'

# ls fallbacks (overridden by 15-modern.sh if eza is installed).
alias ll='ls -alF --color=auto'
alias la='ls -A --color=auto'
alias l='ls -CF --color=auto'
alias ls='ls --color=auto'

# Safety nets — never silent.
alias cp='cp -i'
alias mv='mv -i'
alias rm='rm -i'

# Common everyday shortcuts.
alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'
alias h='history'
alias j='jobs -l'

# Cheat-sheet opener. Render markdown with bat (syntax highlight + paging); fall back to less.
# Defined as a function so we can pick the best available renderer at call time.
cheat() {
    local f="$HOME/.config/dotfiles/cheatsheet.md"
    if   command -v glow    >/dev/null 2>&1; then glow "$f"
    elif command -v bat     >/dev/null 2>&1; then bat --paging=always --language=markdown --style=plain "$f"
    elif command -v batcat  >/dev/null 2>&1; then batcat --paging=always --language=markdown --style=plain "$f"
    else "${PAGER:-less}" "$f"
    fi
}
