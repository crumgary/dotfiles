# Cheat Sheet

## Bootstrap

```bash
sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply crumgary/dotfiles
```

Re-apply after pulling: `chezmoi update`
Edit a managed file: `chezmoi edit ~/path` then `chezmoi apply`
Change a per-machine answer: `chezmoi edit-config && chezmoi apply`

## Profiles

| Profile | Where | What's enabled |
|---|---|---|
| `wsl` | This WSL2 box and similar | Full shell + LazyVim + LSPs + tmux plugins + WSL bits |
| `devbox` | Powerful remote dev/build servers | Same as wsl minus WSL-specific bits |
| `lab` | Thinner SSH targets | Lighter LazyVim (no LSPs/DAP), modern CLI swaps still on |
| `embedded` | busybox / minimal | Minimal `.bashrc` + `.vimrc.minimal` only |

## Shell

- **Modern swaps** (apply when binary is present): `ls`→eza, `bat` (replacement for `cat`), `rg`, `fd`/`fdfind`, `cd`→zoxide (`cdi` for interactive), `delta` in `git diff`/`log -p`.
- **ble.sh autosuggestions:** type a command, see the ghost-text suggestion from history.
  - **Right-arrow / End / Ctrl-E** — accept the full suggestion
  - **Alt-F** — accept one word
  - **Tab** — normal tab-completion (not bound to autosuggest accept by default)
  - Customize in `~/.config/blesh/init.sh` (e.g., add `ble-bind -m auto_complete -f 'TAB' auto_complete/insert` to make Tab accept too).
- **Local-only tweaks:** edit `~/.bashrc.local` (not managed).

## fzf keybinds

| Key | Action |
|---|---|
| `Ctrl-R` | Fuzzy history (replaces reverse-i-search) |
| `Ctrl-T` | Insert fuzzy file path into the command line |
| `Alt-C`  | Fuzzy `cd` into a subdirectory |
| `**<Tab>` | Fuzzy-complete a path inline |

## Git aliases & helpers

| Alias / func | Effect |
|---|---|
| `git st` | short status |
| `git lg` / `git ll` | one-line graph log / last 20 |
| `git sw <br>` / `git swc <br>` | switch / create+switch |
| `git fa` | fetch --all --prune |
| `git wip` | quick checkpoint commit |
| `git undo` | undo last commit (keep changes staged) |
| `gco` | fuzzy branch checkout (local+remote) |
| `gcoh` | fuzzy commit checkout |
| `gshow` | fuzzy commit show with delta |
| `gfiles` | fuzzy-pick a changed file → `$EDITOR` |
| `gkill` | fuzzy-pick branches → delete |

## Tmux (prefix = `Ctrl-a`)

| Key | Effect |
|---|---|
| `prefix \|` / `prefix -` | split vertical / horizontal |
| `prefix h/j/k/l` | move pane |
| `prefix H/J/K/L` | resize pane |
| `prefix r` | reload tmux.conf |
| `prefix R` | rename session |
| `prefix g` | toggle synchronize-panes |
| `prefix Ctrl-s` / `prefix Ctrl-r` | save / restore session |
| `prefix [` then `v` then `y` | enter copy-mode, select, yank |

## Neovim (LazyVim, leader = `<Space>`)

Press `<Space>` and wait — which-key shows the menu.

| Sequence | Effect |
|---|---|
| `<Space>ff` | Find files (project) |
| `<Space>fg` | Live grep |
| `<Space>fb` | Buffers |
| `<Space>fr` | Resume last picker |
| `<Space>e`  | File explorer (oil/neo-tree) |
| `<Space>gs` | Stage hunk (gitsigns) |
| `<Space>gb` | Blame line |
| `<Space>ca` | Code action (LSP) |
| `<Space>cr` | Rename (LSP) |
| `gd`        | Go to definition (LSP) |
| `K`         | Hover (LSP) |
| `<C-h/j/k/l>` | Window navigation (and across tmux panes) |

Enable AI in nvim later: `chezmoi edit-config`, flip `enable_ai_assistant = true`, `chezmoi apply`, restart nvim.

## Troubleshooting

- **Boxes/icons render wrong:** font isn't a Nerd Font. Windows Terminal/VSCode: set font to "JetBrainsMono Nerd Font Mono", restart terminal.
- **`ssh-add` says agent not running:** open new shell (keychain re-runs); or `keychain --eval --agents ssh ~/.ssh/id_voyager`.
- **`chezmoi diff` shows expected files as new:** you probably edited `$HOME` directly. `chezmoi add ~/file` to sync, or `chezmoi apply --force` to overwrite.
- **SELinux denial on RHEL/Alma:** unlikely to affect dotfile content; check `ausearch -m AVC -ts recent`.
- **`fd: command not found` on Ubuntu:** binary is `fdfind`; an alias in `15-modern.sh` maps `fd → fdfind`.
- **nvim 0.6 keeps getting used on Ubuntu 22.04:** the release-binary installer puts current nvim at `~/.local/bin/nvim`. Confirm `~/.local/bin` is first in `$PATH`.
