# ~/.config/bash/50-blesh.sh
# Source ble.sh for autosuggestions, syntax highlighting, better completion.
# Installed by run_onchange_install-blesh.sh.tmpl.

if [ -r "$HOME/.local/share/blesh/ble.sh" ]; then
    # Attach mode: source ble.sh AFTER all other plugins (recommended layout).
    source "$HOME/.local/share/blesh/ble.sh" --attach=none
fi
