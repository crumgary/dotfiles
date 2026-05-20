# ~/.config/bash/70-work-hook.sh
# Source the work-overlay init script if the overlay is installed.

[ -r "$HOME/.config/dotfiles-work/init.sh" ] && . "$HOME/.config/dotfiles-work/init.sh"
