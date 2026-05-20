# dotfiles

My personal dotfiles, managed by [chezmoi](https://www.chezmoi.io/).

## Bootstrap

```bash
sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply crumgary/dotfiles
```

Tested on Ubuntu 22.04 (WSL2 + bare), AlmaLinux 9, and busybox embedded targets.

## Profiles

| Profile | Use for |
|---|---|
| `wsl` | WSL2 Ubuntu daily-driver |
| `devbox` | Powerful remote dev/build servers |
| `lab` | Thinner SSH-only Linux hosts |
| `embedded` | busybox / minimal targets |

See `docs/cheatsheet.md` for keybinds, aliases, and troubleshooting.
