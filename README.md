# dotfiles

My personal dotfiles, managed by [chezmoi](https://www.chezmoi.io/). Public — meant to be forkable, with zero hardcoded usernames or identities.

## One-line bootstrap

```bash
sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply crumgary/dotfiles
```

You'll be prompted for: GitHub username, git name/email, profile (`wsl`/`devbox`/`lab`/`embedded`), work flag, AI-assistant flag, whether to clone the personal overlay (and/or the work overlay), and (on WSL only) Windows username. Answers persist at `~/.config/chezmoi/chezmoi.toml` — re-runs of `chezmoi apply` are silent.

## What this installs

- **bash** + ble.sh (autosuggestions, syntax highlighting) + starship (two-line prompt)
- **modern CLI:** eza, bat, ripgrep, fd, zoxide, delta
- **fzf** with Ctrl-R / Ctrl-T / Alt-C bindings and helper git functions
- **LazyVim** (gated per profile)
- **tmux** with `Ctrl-a` prefix, TPM plugins on full profiles
- **git** with sensible defaults, delta pager, curated aliases
- **JetBrainsMono Nerd Font** (Linux + Windows on WSL)

See [`docs/cheatsheet.md`](docs/cheatsheet.md) for the keybind/alias reference.

## Profiles

| Profile | For | Notes |
|---|---|---|
| `wsl` | WSL2 Ubuntu daily-driver | Full shell + LazyVim + WSL extras |
| `devbox` | Powerful remote dev/build servers | Full shell + LazyVim, no WSL bits |
| `lab` | Thinner SSH targets, lab hardware | Light LazyVim (no LSPs), still has CLI swaps |
| `embedded` | busybox / minimal | Tiny `.bashrc` + `.vimrc.minimal` only |

## Embedded fallback

If chezmoi can't run on a target:

```bash
git clone https://github.com/crumgary/dotfiles ~/.local/share/dotfiles-src
cp ~/.local/share/dotfiles-src/home/dot_bashrc.minimal ~/.bashrc
cp ~/.local/share/dotfiles-src/home/dot_vimrc           ~/.vimrc
```

## Overlay repos (private)

The public repo manages everything generic. Two separate private repos hold
identity-specific content; each is opt-in at init time.

| Repo | Cloned to | Purpose |
|---|---|---|
| `crumgary/dotfiles-priv` | `~/.config/dotfiles-priv/` | Personal hosts/aliases that aren't work but shouldn't be public — home network, personal cloud, GitHub IdentityFile pins, etc. |
| `crumgary/dotfiles-work` | `~/.config/dotfiles-work/` | Voyager-specific bits (bastions, internal hostnames, internal package registries). Only available when `work=true` at init. |

Each overlay has the same shape:
- `ssh/<name>.conf` → symlinked into `~/.ssh/config.d/` by the overlay's `install.sh`
- `init.sh` → sourced at every interactive shell start via `~/.config/bash/70-overlays.sh`
- `install.sh` → idempotent installer that creates the symlinks; re-runs automatically when chezmoi sees the overlay change

`~/.ssh/config` itself (managed by this public repo) does just `Include config.d/*` so both overlays compose cleanly without conflicting. The public repo is fully usable without either overlay.

## Pull updates

```bash
chezmoi update     # git pull + apply
chezmoi diff       # preview before applying
chezmoi edit-config # change profile / work flag / etc.
```

## License

MIT.
