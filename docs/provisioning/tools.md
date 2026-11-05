# Tool installation and integrations

Maintainer reference for `scripts/install-tools`. For everyday operation and
login steps, start with the [setup guide](setup.md). Exact versions, revisions
and hashes live in `config/tools.lock.json`.

## Platforms and package policy

The initial x86_64 matrix is Ubuntu 22.04, 24.04 and 26.04, plus AlmaLinux 9.
Host-native package names, repositories, signing-key hashes and browser choices
are declared under `[managed]` in `home/.chezmoidata/packages.toml`. The installer
detects the host and selects its recipe before making changes. Other operating
systems and architectures are rejected rather than given an Ubuntu recipe.

`config/tools.lock.json` pins portable native/npm/Python tool releases and skill
sources. System package versions follow the host's signed repositories; Ubuntu
package revisions are not imposed on AlmaLinux or another Ubuntu release. The
Node major remains catalog policy, installed through the matching NodeSource
apt or dnf repository. Existing newer Node majors are retained with an error
rather than silently downgraded.

Python 3.9 or newer runs the installer. Python 3.9/3.10 use the included licensed
TOML parser offline; newer Python uses its standard library. System Python is not
replaced. Graphify continues to use its separate uv-managed Python environment.

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

The pinned RTK initializer configures OpenCode together with Claude. Select both
`opencode` and `claude` for now; OpenCode-only selection is rejected before tool
installation. This restriction belongs to the current RTK integration.

For direct installation, run `python3 -B scripts/install-tools --apply --from-chezmoi`.
To preview an explicit app selection without reading local chezmoi data, use
`python3 -B scripts/install-tools --dry-run --apps claude,codex`.

Dry run does not install, access the network or create state. Apply requires a supported target and a normal user with passwordless sudo. The single chezmoi hook fingerprints the catalog, system recipes, entry point
and internal installation modules.
The updater invokes this same installer with its validated candidate catalog.
Disabling a selection does not uninstall tools or delete their data.

## Installation ownership

| Tools | Source and location |
|---|---|
| GitHub CLI | Official signed apt or rpm repository for the host. |
| Atlassian CLI | Official signed apt or rpm repository for the host. |
| Node and npm | NodeSource signed apt or rpm repository for the declared major. |
| Container inspection, terminal recording and media/document utilities | Native distro packages; AlmaLinux also enables EPEL/CRB and RPM Fusion free for FFmpeg. |
| RTK, actionlint and uv | Upstream release artifacts with archive/binary integrity checks. |
| AXI CLIs, Playwright, HyperFrames, Context7 and skill utilities | Per-user npm prefix `~/.local`; package names and versions are in the catalog. |
| Graphify | uv-managed tool with a separate Python environment. |
| Shared skills, including tstack and Superpowers | Pinned upstream source archives staged for app registration. |

The table describes installation methods, not a second package inventory. The
catalog's `developer`, `agents` and `skills` groups hold the portable inventory;
`packages.toml` holds native packages and browser dependencies.
The unified installer acquires shared prerequisites first, then installs and
configures the selected tools using internal routines.

Repository keys have recorded hashes. Apt sources use `Signed-By`; dnf sources
keep package signature verification enabled and ACLI metadata signature checks.
Native packages follow repository candidates, including security updates. Managed
apt installation uses `--no-remove`; dnf never uses `--allowerasing`. Browser
native dependencies are installed by these same guarded recipes, not by a
privileged npm package helper. Npm/Python top-level versions are approved, but
transitive dependencies are package-manager resolved rather than fully locked.
Use the [tool updater](tool-updates.md) to advance approved versions and hashes.

On Ubuntu, Playwright manages Chromium and its native dependencies. AlmaLinux
uses its signed distro/EPEL Chromium package. The installer probes that browser
and records its path for `axi-chrome`. ImageMagick commands can be `magick` or
`convert`, depending on the distro's package generation. AlmaLinux's FFmpeg
comes from the signed RPM Fusion free repository so HyperFrames can use
`libx264` for its default MP4 render. Existing conflicting FFmpeg installations
are retained with an error rather than automatically erased.

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
