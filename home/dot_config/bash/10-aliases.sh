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

# Cheat-sheet opener — populated by chezmoi at apply-time.
alias cheat='${EDITOR:-less} ~/.config/dotfiles/cheatsheet.md'
