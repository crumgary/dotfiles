# ~/.config/bash/20-tools.sh
# Language toolchains: mise, nvm, cargo, bun, pnpm. All guarded.

# mise — runtime version manager. Owns everything it can.
if command -v mise >/dev/null 2>&1; then
    eval "$(mise activate bash)"
fi

# nvm — Node Version Manager (lazy-loaded to avoid 1-second shell startup hit).
export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
    # Lazy shim: nvm/node/npm/npx commands trigger the actual load on first use.
    nvm() {
        unset -f nvm node npm npx 2>/dev/null
        . "$NVM_DIR/nvm.sh"
        [ -s "$NVM_DIR/bash_completion" ] && . "$NVM_DIR/bash_completion"
        nvm "$@"
    }
    node() { unset -f nvm node npm npx 2>/dev/null; . "$NVM_DIR/nvm.sh"; node "$@"; }
    npm()  { unset -f nvm node npm npx 2>/dev/null; . "$NVM_DIR/nvm.sh"; npm "$@";  }
    npx()  { unset -f nvm node npm npx 2>/dev/null; . "$NVM_DIR/nvm.sh"; npx "$@";  }
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
