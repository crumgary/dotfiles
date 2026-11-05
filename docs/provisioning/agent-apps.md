# Selected AI apps and skills

The selected apps are Claude Code, Codex, OpenCode and Antigravity CLI. This setup
is declared in `config/tools.lock.json`, installed by
`scripts/install-agent-apps`, and registered by `scripts/provision/skill_adapters.py`.
Maintainer reference for the selected-app installer. For normal operation and
login commands, start with the [setup guide](setup.md). This setup does not run
the legacy install-every-agent script.

## Configure and deploy

After the public baseline and developer bundle are available, set these local
chezmoi data values (or select them during init):

```toml
[data]
install_agent_clis = false
install_developer_tools = true
agent_apps = ["claude", "codex", "opencode", "antigravity"]
agent_apps_csv = "claude,codex,opencode,antigravity"
```

`agent_apps_csv` is the init prompt's persisted answer; `agent_apps` is the resolved
selection used by deployment and inventory. Existing configs without an app list
enable no new apps. Disabling a selection does not delete existing apps, skills,
plugins or their user data.

```console
python3 -B scripts/install-agent-apps --dry-run --apps claude,codex,opencode,antigravity
chezmoi apply
```

The after-script runs the installer with `--from-chezmoi`, so selections are read
as TOML rather than interpolated into a shell command. It fingerprints the shared
`config/tools.lock.json` catalog. The installed-state receipt is
`~/.local/state/dotfiles/agent-apps.json`.

## Runtime and installation ownership

The developer bundle owns Node and npm through NodeSource's signed apt
repository at `/usr/bin/node`. The chosen Node major is declared in the shared
catalog. No nvm or second Node manager is added; baseline packages do not own a
competing Node/npm installation.

Claude Code uses its verified native bootstrap and native install command at the
declared version. Antigravity uses the official versioned native artifact with
archive/binary integrity checks; redundant shell-setup edits are unnecessary
because the baseline already owns PATH. Codex and OpenCode use exact per-user
npm versions under `~/.local`. OpenCode explicitly allows its required postinstall
step, which creates the executable launcher. Other npm installs keep lifecycle
scripts disabled where supported.

Matching native version text is insufficient: existing Claude/Antigravity bytes
must match the declared binary hash before their version output is trusted.
Newer or altered installations are reported for review, not silently downgraded.
Selected managed apps use the [explicit tool updater](tool-updates.md).
Background native updates/checks are disabled so they do not compete with the
approved catalog; manual native upgrades can require reconciliation.
Npm versions are pinned but the installer does not promise fully locked transitive
dependencies or a byte-identical npm reconstruction.

## Skills and rules

The tstack fork stays pinned to `crumgary/tstack`. Each skill points at that
immutable staged source through `~/.agents/skills`. Claude uses corresponding
`~/.claude/skills` adapters; OpenCode discovers the shared agent directory;
Antigravity uses its supported `~/.gemini/config/skills` location. Custom skills
and unrelated configuration are preserved. Verified installer-owned links can
advance to another declared revision; customized or unowned links block changes.

Superpowers uses supported per-app registration:

- Claude's marketplace/install commands register the pinned local source.
- Codex's marketplace/add commands install through an installer-owned local
  catalog. The cache is populated by Codex, never fabricated by this script.
- Antigravity's native plugin installer registers the pinned source.
- OpenCode's JSON configuration names the absolute local pinned plugin package.
  Existing JSONC or symlink-managed config is reported for owner review.

Registry identity, version and enabled state are checked. Executable plugin
components and skill contents are also compared with the pinned source. Updates
of known owned registrations use app-native uninstall/install operations; custom
or modified content is retained with a conflict. Shared global instructions remain
in `~/.config/agents/AGENTS.md`; OpenCode receives a link to that same source.

## Authentication and platform notes

Follow the [authentication checklist](setup.md#one-time-authentication-checklist)
after installation. Installation, local discovery and authenticated model
behavior are separate checks; a successful install does not prove a provider
login or that an agent invoked every installed skill.
