# dotfiles

My personal dotfiles, managed by [chezmoi](https://www.chezmoi.io/). Public — meant to be forkable, with zero hardcoded usernames or identities.

## One-line bootstrap

```bash
sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply crumgary/dotfiles
```

You'll be prompted for: GitHub username, git name/email, profile (`wsl`/`devbox`/`lab`/`embedded`), work flag, AI-assistant flag, whether to clone the personal overlay (and/or the work overlay), whether to create convenience shortcuts to your repos (and where), and (on WSL only) Windows username. Answers persist at `~/.config/chezmoi/chezmoi.toml` — re-runs of `chezmoi apply` are silent.

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

## Shared agent instructions

One canonical instruction file, `~/.config/agents/AGENTS.md`, is symlinked into
the global location each AI coding agent reads, so all of them share the same
rules and you edit them in one place:

| Tool | Reads | Managed as |
|---|---|---|
| Claude Code | `~/.claude/CLAUDE.md` | symlink → `~/.config/agents/AGENTS.md` |
| Codex | `~/.codex/AGENTS.md` | symlink → same |
| Antigravity (`agy`) | `~/.gemini/AGENTS.md` | symlink → same |
| Pi | `~/.pi/agent/AGENTS.md` | symlink → same |

Claude Code reads `CLAUDE.md` (not `AGENTS.md`), so its symlink is named
accordingly; the others use the cross-tool `AGENTS.md` name. The symlinks are
created by chezmoi even when a tool isn't installed yet, so a fresh machine is
ready the moment you add one. Not deployed on the `embedded` profile.

## Convenience shortcuts

The repos live at their standard locations (`~/.local/share/chezmoi` and
`~/.config/dotfiles-{priv,work}`). If you'd rather reach them from one memorable
place, answer yes to the convenience-shortcuts prompt at init. chezmoi then
symlinks that directory at the real locations (default `~/github/<username>/dotfiles-src`):

```
~/github/<username>/dotfiles-src/dotfiles      -> ~/.local/share/chezmoi
~/github/<username>/dotfiles-src/dotfiles-priv -> ~/.config/dotfiles-priv
~/github/<username>/dotfiles-src/dotfiles-work -> ~/.config/dotfiles-work
```

These are pure navigation aids - editing through a shortcut is identical to
editing the real repo. Only overlays you actually installed are linked. Change
the directory (or turn it off) any time with `chezmoi edit-config`.

## Pull updates

```bash
chezmoi update     # git pull + apply
chezmoi diff       # preview before applying
chezmoi edit-config # change profile / work flag / etc.
```

## License

MIT.
