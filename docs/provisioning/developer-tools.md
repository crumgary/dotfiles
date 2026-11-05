# Developer-tool installer reference

For normal setup and login steps, start with the [setup guide](setup.md). This
page explains how `scripts/install-developer-tools` acquires and verifies the
optional developer bundle. Install selections come from chezmoi data; exact
versions, source revisions and hashes come from `config/tools.lock.json`.

## Enable and run

Set `install_developer_tools = true` in local chezmoi data or select it during
init. The older `install_agent_clis` flag is independent. Selected AI apps use
the [app installer](agent-apps.md).

From the public dotfiles checkout:

```console
python3 -B scripts/install-developer-tools --dry-run
chezmoi apply
```

Dry run prints declarations without network or filesystem mutation. To invoke
the installer directly, use `python3 -B scripts/install-developer-tools --apply`.
Apply requires the supported target platform and a normal user with passwordless
sudo. See the catalog for the supported platform/runtime constraints.

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
Separate installers own package acquisition and app registration, but both read
the same catalog.

Apt trust keys have recorded hashes and repository-specific `Signed-By`
configuration. Apt versions are tested minimum baselines; newer distribution and
security packages are accepted. Npm/Python top-level versions are approved, but
transitive dependencies are package-manager resolved rather than fully locked.
Use the [tool updater](tool-updates.md) to advance approved versions and hashes.

## Source staging and app integration

Sources are staged under
`~/.local/share/dotfiles/skill-sources/<collection>/<commit>/`. Receipts record
archive and content integrity. Repeat installation checks contents and preserves
executable helper scripts. Unsafe archive paths and unapproved symlinks are
rejected. Local edits are reported and preserved; update the owning fork and its
catalog revision to change managed content.

Staging does not activate skills, plugins or hooks. The selected-app installer
performs [app-specific registration](agent-apps.md), including RTK integration.
A copied `SKILL.md` or plugin cache alone does not prove that an agent loaded it.
Skills that delegate to other providers depend on the harness's capabilities.

## Repeat installation and failures

The installer checks existing hashes, permissions, package versions and staged
sources. It avoids unnecessary apt refreshes and browser downloads when the
recorded requirements are already satisfied. Its local receipt is
`~/.local/state/dotfiles/developer-tools.json`.

A partial failure retains completed stages and returns failure for retry. Package
installation is not an atomic transaction or rollback. See the
[update recovery workflow](tool-updates.md) for frozen update candidates.
Credentials, sessions, browser profiles and memory databases remain machine-local.
