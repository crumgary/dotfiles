# ~/.config/blesh/init.sh — ble.sh user config. Sourced automatically by ble.sh on startup.
#
# We keep ble.sh's syntax highlighting but make completion behave like stock bash:
#   - no fish-style gray "ghost text" auto-suggestions while typing
#   - Tab fills the common prefix and lists candidates (no cycling menu)

# Turn off the predictive gray auto-suggestion text.
bleopt complete_auto_complete=

# Make Tab behave like plain readline instead of ble.sh's cycling menu-complete.
bleopt complete_menu_complete=

# Execute pasted multiline commands with Enter. Herdr uses this for managed launches.
ble-bind -m emacs -f 'C-m' 'accept-line'
ble-bind -m emacs -f 'RET' 'accept-line'

# To bring the fish-style suggestions back, comment out the two lines above.
# When ghost text is shown, Right-arrow / End / Ctrl-E accept it (Alt-F = one word).
