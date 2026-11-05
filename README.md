# dotfiles

My personal dotfiles, managed by [chezmoi](https://www.chezmoi.io/). Public — meant to be forkable, with zero hardcoded usernames or identities.

## One-line bootstrap

```bash
sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply crumgary/dotfiles
```

You'll be prompted for: GitHub username, git name/email, profile (`wsl`/`devbox`/`lab`/`embedded`), work flag, selected AI apps and developer tools, whether to clone the personal overlay (and/or the work overlay), whether to create convenience shortcuts to your repos (and where), and (on WSL only) Windows username. Answers persist at `~/.config/chezmoi/chezmoi.toml` — re-runs of `chezmoi apply` are silent.

## What this installs

- **bash** + ble.sh (autosuggestions, syntax highlighting) + starship (two-line prompt)
- **modern CLI:** eza, bat, ripgrep, fd, zoxide, delta
- **fzf** with Ctrl-R / Ctrl-T / Alt-C bindings and helper git functions
- **Vim** with a small shared `.vimrc`
- **tmux** with `Ctrl-a` prefix, TPM plugins on full profiles
- **git** with sensible defaults, delta pager, curated aliases
- **JetBrainsMono Nerd Font** (Linux + Windows on WSL)

See [`docs/cheatsheet.md`](docs/cheatsheet.md) for the keybind/alias reference.

## Profiles

| Profile | For | Notes |
|---|---|---|
| `wsl` | WSL2 Ubuntu daily-driver | Full shell + Vim + WSL extras |
| `devbox` | Powerful remote dev/build servers | Full shell + Vim, no WSL bits |
| `lab` | Thinner SSH targets, lab hardware | Vim and modern CLI tools |
| `embedded` | busybox / minimal | Tiny `.bashrc` + `.vimrc` only |

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

One canonical instruction file, `~/.config/agents/AGENTS.md`, supplies the global
rules for each AI coding agent. Edit the shared rules in one place:

| Tool | Reads | Managed as |
|---|---|---|
| Claude Code | `~/.claude/CLAUDE.md` | symlink → `~/.config/agents/AGENTS.md` |
| Codex | `~/.codex/AGENTS.md` | generated shared rules plus its RTK reference |
| OpenCode | `~/.config/opencode/AGENTS.md` | symlink to shared rules when selected |
| Antigravity (`agy`) | `~/.gemini/AGENTS.md` | symlink → same |
| Pi | `~/.pi/agent/AGENTS.md` | symlink → same |

Claude Code reads `CLAUDE.md` (not `AGENTS.md`), so its symlink is named
accordingly. Codex gets a generated file so its RTK setup cannot modify the
shared source. OpenCode's adapter is installed with the selected-app setup.
The other instruction links are created by chezmoi on full profiles.
These instructions are not deployed on the `embedded` profile.

When the personal and work overlays are enabled, their `agents/AGENTS.md` files
are included conditionally by the shared template. This keeps machine-specific
and work-specific instructions out of the public base configuration.

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

## First sign-ins

After installation, follow the [one-time authentication checklist](docs/provisioning/setup.md#one-time-authentication-checklist)
for Claude Code, Codex, GitHub, Atlassian, OpenCode and Antigravity. Run the login
commands on the target machine as your normal user. Sign into GitHub before using
`dotfiles-update` to avoid the small anonymous API quota.

## Configuration and tool updates

```bash
chezmoi update     # git pull + apply
chezmoi diff       # preview before applying
chezmoi edit-config # change profile / work flag / etc.
```

With the developer bundle enabled, update tools separately:

```console
dotfiles-update --check                  # discover newer stable releases
dotfiles-update --apply                  # install, validate, then save the catalog
dotfiles-update --apply --only opencode  # advance one tool
dotfiles-update --apply --commit --push  # also publish the tested catalog
```

Ubuntu packages follow their configured apt repositories and normal security
updates. Node stays on the chosen LTS major. Other tool versions, artifact hashes
and skill revisions are refreshed automatically. Selected AI apps use this
updater as their update owner. Failed updates retain a frozen candidate: rerun
the same selection to resume. Use `--apply --refresh` to explicitly replace a
failed candidate; unavailable npm releases are deferred. See [version and update policy](docs/provisioning/tool-updates.md).

## Machine inventory and read-only doctor

[Doctor reference](docs/provisioning/doctor.md): declare machine selections in
a local record or enabled overlay and inspect configuration drift without applying changes.
Requires Python 3.9+; templates and unaudited checks are reported as unverified.

```console
python3 -B scripts/dotfiles-doctor --machine ~/.config/dotfiles/machines/primary-wsl.toml
```

On Ubuntu 26.04, core CLI tools and Vim use distro packages.

## License

MIT.

## Optional developer tools

The managed tool installer targets Ubuntu 22.04/24.04/26.04 and AlmaLinux 9
on x86_64, using native apt/dnf recipes and shared portable tool pins.

Enable `install_developer_tools` to add the [tools and integrations](docs/provisioning/tools.md)
including shared skills. Select Claude Code, Codex, OpenCode and/or Antigravity
at init to include them in the same installation workflow.
Provider logins remain separate from installation.
