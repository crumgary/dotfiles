# Tool installation and integrations

Maintainer reference for `scripts/install-tools`. For everyday operation and
login steps, start with the [setup guide](setup.md). Exact versions, revisions
and hashes live in `config/tools.lock.json`.

## Configure and run

Select tools during `chezmoi init`, or edit the local chezmoi data:

```toml
[data]
install_agent_clis = false
install_developer_tools = true
agent_apps = ["claude", "codex", "opencode", "antigravity"]
agent_apps_csv = "claude,codex,opencode,antigravity"
```

`agent_apps` selects optional AI tools and their integrations. Selecting an app
also enables its shared prerequisites. With no apps selected,
`install_developer_tools = true` installs the shared development tools alone.
`agent_apps_csv` is the init prompt's persisted answer. Existing selection keys are retained for compatibility. The older
`install_agent_clis` script remains separate for legacy configurations; keep it
disabled when using the unified setup to avoid competing installers.

From the public dotfiles checkout:

```console
python3 -B scripts/install-tools --dry-run --from-chezmoi
chezmoi apply
```

For direct installation, run `python3 -B scripts/install-tools --apply --from-chezmoi`.
To preview an explicit app selection without reading local chezmoi data, use
`python3 -B scripts/install-tools --dry-run --apps claude,codex`.

Dry run does not install, access the network or create state. Apply requires the
supported platform and a normal user with passwordless sudo. The single chezmoi
hook fingerprints the catalog, entry point and internal installation modules.
The updater invokes this same installer with its validated candidate catalog.
Disabling a selection does not uninstall tools or delete their data.

## Installation ownership

| Tools | Source and location |
|---|---|
| GitHub CLI | Official signed GitHub apt repository. |
| Atlassian CLI | Official signed Atlassian apt repository. |
| Node and npm | NodeSource signed apt repository for the declared Node major. |
| Container inspection, terminal recording and media/document utilities | Ubuntu apt packages. |
| RTK, actionlint and uv | Upstream release artifacts with archive/binary integrity checks. |
| AXI CLIs, Playwright, HyperFrames, Context7 and skill utilities | Per-user npm prefix `~/.local`; package names and versions are in the catalog. |
| Graphify | uv-managed tool with a separate Python environment. |
| Shared skills, including tstack and Superpowers | Pinned upstream source archives staged for app registration. |

The table describes installation methods, not a second package inventory. The
catalog's `developer`, `agents` and `skills` groups are the complete inventory.
The unified installer acquires shared prerequisites first, then installs and
configures the selected tools using internal routines.

Apt trust keys have recorded hashes and repository-specific `Signed-By`
configuration. Apt versions are tested minimum baselines; newer distribution and
security packages are accepted. Npm/Python top-level versions are approved, but
transitive dependencies are package-manager resolved rather than fully locked.
Use the [tool updater](tool-updates.md) to advance approved versions and hashes.

## Native and npm tools

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

## Skills, plugins and rules

Sources are staged once under
`~/.local/share/dotfiles/skill-sources/<collection>/<commit>/` and reused for
registration. Unsafe archive paths and unapproved symlinks are rejected. Local
edits are reported and preserved; change the owning fork and catalog revision
to update managed content.

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

## Installed state and failures

Existing ownership receipts remain at
`~/.local/state/dotfiles/developer-tools.json` and
`~/.local/state/dotfiles/agent-apps.json`. They are internal records for different
resources, not separate installation workflows. Keeping them preserves existing
hash ownership and conflict detection during this consolidation.

Repeat installation verifies installed state. A partial failure retains completed
stages and returns failure for retry; it is not an atomic package transaction.
See [update recovery](tool-updates.md) for frozen candidates. Credentials,
sessions and memory databases remain machine-local. A successful install does
not prove provider authentication or that an agent invoked every installed skill.
