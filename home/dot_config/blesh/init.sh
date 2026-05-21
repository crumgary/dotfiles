# ~/.config/blesh/init.sh — ble.sh user config. Sourced automatically by ble.sh on startup.

# Tab accepts the auto-complete ghost-text suggestion when one is showing.
# When no suggestion is showing, Tab falls through to normal tab-completion.
# Right-arrow / End / Ctrl-E also still accept (ble.sh defaults).
ble-bind -m auto_complete -f 'TAB' auto_complete/insert

# Shift-Tab inserts one WORD of the suggestion (handy when the rest of the
# suggested line is wrong).
ble-bind -m auto_complete -f 'S-TAB' auto_complete/insert-on-end-or-cancel
