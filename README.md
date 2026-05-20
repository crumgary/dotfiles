# dotfiles

My personal dotfiles, managed by [chezmoi](https://www.chezmoi.io/). Public — meant to be forkable, with zero hardcoded usernames or identities.

## One-line bootstrap

```bash
sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply crumgary/dotfiles
```

You'll be prompted for: GitHub username, git name/email, profile (`wsl`/`devbox`/`lab`/`embedded`), work flag, AI-assistant flag, and (on WSL only) Windows username. Answers persist at `~/.config/chezmoi/chezmoi.toml` — re-runs of `chezmoi apply` are silent.

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
cp ~/.local/share/dotfiles-src/home/dot_vimrc.minimal  ~/.vimrc
```

## Work overlay

A separate private repo (`crumgary/dotfiles-work`) provides work-specific bits (bastion SSH config, internal registries) via a hook at `~/.config/dotfiles-work/`. The public repo is fully usable without it.

## Pull updates

```bash
chezmoi update     # git pull + apply
chezmoi diff       # preview before applying
chezmoi edit-config # change profile / work flag / etc.
```

## License

MIT.
