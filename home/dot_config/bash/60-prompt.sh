# ~/.config/bash/60-prompt.sh
# Initialize starship if installed.

if command -v starship >/dev/null 2>&1; then
    eval "$(starship init bash)"
fi
