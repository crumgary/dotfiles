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

# Locale: prefer en_US.UTF-8 if generated, else C.UTF-8 (always present on glibc).
# Fresh Ubuntu/Debian minimal images often don't have en_US.UTF-8 generated; forcing it
# produces the noisy "setlocale: cannot change locale" warning on every shell startup.
# Don't force LC_ALL — it overrides every per-category LC_* and masks real settings.
unset LC_ALL 2>/dev/null
if [ -z "${LANG:-}" ] || [ "$LANG" = "C" ] || [ "$LANG" = "POSIX" ]; then
    if locale -a 2>/dev/null | grep -qix 'en_US\.utf-\?8'; then
        export LANG=en_US.UTF-8
    else
        export LANG=C.UTF-8
    fi
fi

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
