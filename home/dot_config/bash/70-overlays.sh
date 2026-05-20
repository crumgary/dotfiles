# ~/.config/bash/70-overlays.sh
# Source per-overlay init.sh scripts if their overlay is installed.
# Personal first, work second — work entries can override personal if desired.

[ -r "$HOME/.config/dotfiles-priv/init.sh" ] && . "$HOME/.config/dotfiles-priv/init.sh"
[ -r "$HOME/.config/dotfiles-work/init.sh" ] && . "$HOME/.config/dotfiles-work/init.sh"
