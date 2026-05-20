# ~/.config/bash/00-env.sh
# Environment variables, PATH, EDITOR, history settings.

# Prepend ~/.local/bin and ~/bin if they exist and aren't already in PATH.
for d in "$HOME/.local/bin" "$HOME/bin"; do
    case ":$PATH:" in
        *":$d:"*) ;;
        *) [ -d "$d" ] && PATH="$d:$PATH" ;;
    esac
done
export PATH

# Editor / pager preferences (fall back gracefully).
if command -v nvim >/dev/null 2>&1; then
    export EDITOR=nvim VISUAL=nvim
elif command -v vim >/dev/null 2>&1; then
    export EDITOR=vim VISUAL=vim
else
    export EDITOR=vi VISUAL=vi
fi
export PAGER=less
export LESS='-RFX --mouse'

# Locale (UTF-8 everywhere; matters for nvim, eza, etc.).
export LANG=${LANG:-en_US.UTF-8}
export LC_ALL=${LC_ALL:-en_US.UTF-8}

# History settings — append immediately, dedup, ignore lines starting with space.
HISTSIZE=100000
HISTFILESIZE=200000
HISTCONTROL=ignoreboth:erasedups
HISTTIMEFORMAT="%F %T "
shopt -s histappend
# Append to history immediately so other terminals see new entries via fzf Ctrl-R.
case "$PROMPT_COMMAND" in
    *"history -a"*) ;;
    *) PROMPT_COMMAND="history -a;${PROMPT_COMMAND:-}" ;;
esac
