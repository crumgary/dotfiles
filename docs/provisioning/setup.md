# Developer environment setup

User guide for the optional developer tools, AI apps and shared skills. The
[main README](../../README.md) covers the baseline bootstrap and profiles;
`config/tools.lock.json` records the supported platform, runtime policy and
approved versions. This guide does not prescribe a particular machine name.

## Select tools and apps

Choose the developer bundle and the apps you want during `chezmoi init`, or
use `chezmoi edit-config` to change the local selections before `chezmoi apply`.
See [tools and integrations](tools.md) for selection fields and installer behavior. Disabling a selection does not
uninstall existing tools or delete their data.

The developer bundle includes shell/development utilities, GitHub and Atlassian
CLIs, browser/media tools and shared skill sources. Selected AI apps receive
app-specific rules, skill/plugin registrations and RTK integration. The catalog
is the complete inventory; these guides do not maintain a second version list.

## One-time authentication checklist

Run these as your normal user on the target machine. Sign in to the services
you use. Each machine/WSL instance keeps its own credentials; installation does
not copy or complete these logins.

| Tool | Sign in | Check local authentication |
|---|---|---|
| Claude Code | `claude auth login` | `claude auth status` |
| Codex | `codex login` | `codex login status` |
| GitHub | `gh auth login` | `gh auth status` |
| Atlassian (Jira and Confluence) | `acli auth login` | `acli auth status` |
| OpenCode | `opencode auth login` | `opencode auth list` lists configured providers |

Run `opencode auth login` from the shell, choose the provider/account you want,
and complete its sign-in or API-key prompt.

For Antigravity, launch `agy` and complete its Google sign-in flow. Follow each
tool's browser instructions; if a browser does not open automatically, use the
URL shown in the terminal in your browser.

Complete `gh auth login` before checking or applying tool updates. GitHub
release discovery otherwise shares the anonymous hourly API quota with other
traffic from your public IP. See [rate-limit and cache behavior](tool-updates.md).
ACLI's top-level `acli auth login` supports Jira and Confluence OAuth; the
Jira-specific alternative is `acli jira auth login --web`.

Context7 works without a login up to its anonymous limits; `ctx7 login` provides
higher account limits. Optional HeyGen services need their own account; local
HyperFrames rendering already works without one.

Claude manages `~/.claude/skills/synced` after account sign-in. Those downloads
remain account-owned; the installer does not distribute them to other apps.

## Reapply and update

From the public dotfiles checkout:

```console
chezmoi apply
python3 -B scripts/install-tools --dry-run --from-chezmoi
```

The installer reads one catalog. Source pins and unknown existing customizations
are checked before replacement. Use `dotfiles-update --check` and
`dotfiles-update --apply` to discover, install and validate newer releases before
publishing the tested catalog. Npm/Python top-level package versions are pinned;
their transitive dependencies are not a complete reproducible-build lock.
Owned native memory plugin/Bun upgrades are supported by the explicit
[tool update workflow](tool-updates.md); modified or unknown content is retained.

## Local memory service

When selected, the local memory worker runs as `claude-mem.service` in the
user's systemd manager, with linger enabled. Installation checks its initialized
health, approved version/path and service PID. Provider login is still required
for summarization/model turns. Existing memory databases, observations, sessions
and credentials are retained on their owning machine.

## Windows T3 with WSL

Select the target WSL environment in Windows T3 and authenticate the provider
CLIs inside that distro. T3 installs its matching server runtime automatically;
no separate T3 server installation is needed.
