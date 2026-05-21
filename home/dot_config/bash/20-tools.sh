# ~/.config/bash/20-tools.sh
# Language toolchains: mise, nvm, cargo, bun, pnpm. All guarded.

# mise — runtime version manager. Owns everything it can.
if command -v mise >/dev/null 2>&1; then
    eval "$(mise activate bash)"
fi

# nvm — Node Version Manager. nvm.sh is ~1s to source, so we don't do it eagerly,
# but bash-function shims like node()/npm() are only visible in this shell — child
# processes (Claude Code hooks, systemd units, GUI launchers) bypass them and fall
# back to /usr/bin/node. Instead: resolve nvm's default version once and prepend
# its bin/ to PATH so non-bash consumers get the right node. Keep the `nvm` shim
# so `nvm use <other>` still works interactively.
export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
    if [ -r "$NVM_DIR/alias/default" ]; then
        _nvm_alias="$(cat "$NVM_DIR/alias/default")"
        # Walk indirect aliases (e.g. lts/iron → v20.11.0).
        while [ -r "$NVM_DIR/alias/$_nvm_alias" ]; do
            _nvm_alias="$(cat "$NVM_DIR/alias/$_nvm_alias")"
        done
        _nvm_default_bin="$NVM_DIR/versions/node/v${_nvm_alias#v}/bin"
        # If alias is a major (e.g. "24"), pick the highest installed v24.x.
        if [ ! -d "$_nvm_default_bin" ]; then
            _nvm_default_bin="$(ls -1d "$NVM_DIR/versions/node/v${_nvm_alias#v}".* 2>/dev/null | sort -V | tail -n1)/bin"
        fi
        if [ -d "$_nvm_default_bin" ]; then
            case ":$PATH:" in *":$_nvm_default_bin:"*) ;; *) PATH="$_nvm_default_bin:$PATH" ;; esac
        fi
        unset _nvm_alias _nvm_default_bin
    fi
    # Lazy shim: typing `nvm` triggers the full load (for `nvm use`, `nvm install`, etc).
    nvm() {
        unset -f nvm 2>/dev/null
        . "$NVM_DIR/nvm.sh"
        [ -s "$NVM_DIR/bash_completion" ] && . "$NVM_DIR/bash_completion"
        nvm "$@"
    }
fi

# Cargo / Rust.
[ -f "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"

# Bun.
if [ -d "$HOME/.bun" ]; then
    export BUN_INSTALL="$HOME/.bun"
    case ":$PATH:" in *":$BUN_INSTALL/bin:"*) ;; *) PATH="$BUN_INSTALL/bin:$PATH" ;; esac
fi

# pnpm.
if [ -d "$HOME/.local/share/pnpm" ]; then
    export PNPM_HOME="$HOME/.local/share/pnpm"
    case ":$PATH:" in *":$PNPM_HOME:"*) ;; *) PATH="$PNPM_HOME:$PATH" ;; esac
fi

# opencode.
if [ -d "$HOME/.opencode" ]; then
    case ":$PATH:" in *":$HOME/.opencode/bin:"*) ;; *) PATH="$HOME/.opencode/bin:$PATH" ;; esac
fi

export PATH
