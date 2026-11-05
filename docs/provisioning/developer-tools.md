# Developer tools and skill sources

Enable `install_developer_tools = true` in local chezmoi data to install this
optional bundle. It is independent of the older `install_agent_clis` flag; turning
it on does not install every historical AI app. The first supported target is
Ubuntu 26.04 x86_64. Credentials and app login remain machine-local.

From the public dotfiles checkout:

```console
python3 -B scripts/install-developer-tools --dry-run
python3 -B scripts/install-developer-tools --apply
```

Dry run reads the lock and prints declarations without network or filesystem
mutation. Apply performs acquisition/install stages and requires the actual
logged-in target user with passwordless sudo. This is not yet the proposed
reviewed-plan/apply/update framework with target precondition binding.

## Ownership and sources

| Item | Declared installation source |
| --- | --- |
| gh | Official GitHub signed apt repository, 2.103.3 |
| acli | Official Atlassian signed apt repository, 1.3.40-stable |
| skopeo, asciinema | Ubuntu apt packages with versions recorded in the lock |
| RTK | rtk-ai/rtk 1.1.0 release, archive and installed binary SHA-256 checked |
| actionlint | rhysd/actionlint 1.7.12 release, archive and binary SHA-256 checked |
| gh-axi | Per-user npm prefix `~/.local`, version 0.1.48 |
| Playwright | Per-user npm prefix `~/.local`, version 1.64.1, Chromium only |
| tstack | `crumgary/tstack` fork, full commit and source archive SHA-256 |
| Superpowers | `obra/superpowers`, full commit and source archive SHA-256 |

Pins live in `config/tools.lock.json`. Apt trust keys have recorded
hashes and repository-specific `Signed-By` configuration. The bundle owns Node 26 LTS through NodeSource's signed apt repository, supplying
npm with Node and avoiding a second Node manager. Npm package
versions are explicit; transitive dependencies are not fully locked by this
installer, so it does not claim a byte-identical npm rebuild. System dependency
versions installed by Playwright are also distribution-managed.

Only explicit selection enables the bundle. Ubuntu's older gh package is
upgraded through GitHub's official repository for current APIs and newer gh-axi
features. A newer installed apt package is an actionable conflict; the installer
does not automatically downgrade it. Updates require intentionally changing the
lock after validation. Older pinned apt versions may eventually become unavailable
upstream, producing a failure rather than selecting another version silently.

## Skills and app integration

Pinned sources are staged under:

```text
~/.local/share/dotfiles/skill-sources/<collection>/<commit>/
```

Their source receipts record archive and content integrity. Repeated installation
checks the staged contents. Local edits are reported and preserved; they are not
automatically reset. Modify the owning fork and select its new commit instead.
Executable helper scripts retain executable permissions. Archive traversal and
symlink entries are rejected before extraction.

Staging is not activation. Claude Code and Codex have different supported plugin
and skill-loading mechanisms; their adapters must be selected and verified
separately. Superpowers' current upstream guidance favors per-app plugin
installation. Do not fabricate plugin-cache files or assume a copied SKILL.md
proves loading. RTK's binary is installed, but its hooks/instruction integration
are likewise part of the app adapter. tstack skills that require other providers
remain dependent on the harness's available delegation capabilities.

GitHub and Atlassian logins are separate supported login flows. No tokens,
credential files, browser profiles, shell history, skill lockfiles from the
current workstation, sessions or memory databases were copied.

## Acceptance on Ubuntu-26.04

The first direct install and the chezmoi opt-in integration completed. All eight
CLI version/help checks passed. RTK's savings command confirmed the intended RTK
project and reported that hooks are not yet installed. Chromium launched headless
and rendered local smoke-test content. Both skill source collections are staged;
the selected-app setup is documented separately in [agent-apps.md](agent-apps.md).

The installer verifies existing binary hashes/permissions and npm versions on
repeat runs, skips apt updates if packages and repository files match, and
avoids downloading an already-present Chromium revision. A local package receipt
lives in `~/.local/state/dotfiles/developer-tools.json`. Partial failures retain
completed stages and return failure for retry; this is not an atomic package
transaction or rollback promise.

Target logs: `/tmp/dotfiles-developer-tools-first.log` and
`/tmp/dotfiles-developer-tools-chezmoi.log`.

## Upstream references

- https://github.com/crumgary/tstack
- https://github.com/rtk-ai/rtk
- https://github.com/kunchenguid/gh-axi
- https://github.com/cli/cli/blob/trunk/docs/install_linux.md
- https://developer.atlassian.com/cloud/acli/guides/install-linux/
- https://playwright.dev/docs/browsers
- https://github.com/obra/superpowers

Final repeat-install acceptance passed: checked shell/Git/agent configuration,
RTK/actionlint binary hashes, access modes, modification times and the bundle
receipt remained unchanged. Actionlint validated a local workflow on stdin;
Chromium rendered a local test page. The controller result is
`/tmp/wsl-developer-tools-acceptance.json`. Local verification includes 41 tests,
Ruff checks/formatting, whitespace checks and the doctor's restricted test mode.

## One tool catalog

`config/tools.lock.json` is the single version and source inventory. Its
`developer` group holds apt repositories/packages, binary artifacts and npm
tools; `agents` holds selectable AI apps; `skills` holds shared source pins.
`platform` and `runtime_major` state the target constraints. The developer
opt-in and selected-app list remain independent installation choices. Their
installers and state receipts are separate because they configure different
resources, but both read this catalog. No tool version is duplicated between
lock files.

The bundle now also includes the Context7, skills, HyperFrames and browser/Atlassian AXI CLIs, uv-managed Graphify, and local media dependencies. Full selected capability and login details are in [the usable WSL guide](usable-wsl.md).
