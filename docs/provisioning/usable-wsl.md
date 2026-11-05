# Usable WSL developer and agent setup

The selected setup is installed on `Ubuntu-26.04`, user `gcrum`. Acquisition is
scripted in the public repository, with versions and sources in
`config/tools.lock.json`. Windows T3 owns its matching WSL server runtime.
Select this distro in T3 after signing into the Linux provider CLIs.

## Installed capabilities

- Node 26 LTS, Vim, shell/Git baseline and the developer CLI bundle.
- Claude Code, Codex, OpenCode and Antigravity CLI, with RTK integrations.
- Nine tstack skills and Superpowers through supported per-app plugins.
- Shared find-docs/Context7, find-skills, ms-rust and task-observer.
- Graphify, installed through uv with a separate Python 3.13 environment and its
  native shared skill installer. System Python remains distribution-owned.
- HyperFrames, hyperframes-cli, hyperframes-registry and media-use; FFmpeg,
  ImageMagick, Pandoc, Poppler, librsvg and a managed local rendering browser.
- Jira/Confluence AXI CLIs and skills; Draw.io skill.
- chrome-devtools-axi with `axi-chrome`, using Playwright's Chromium. The helper
  owns its browser profile and checks ownership before stopping a process.
- claude-mem 15.9.0, Bun 1.4.4, native Claude/Codex plugins, the published
  OpenCode integration, and the official Antigravity hooks/MCP integration.

Shared skills are exposed from `~/.agents/skills`, with explicit Claude and
Antigravity adapters. Complete upstream trees retain sibling references. Native
Graphify and app plugin managers own their generated skill/plugin content.
The task-observer workspace is `~/.local/state/agent-observer`; it begins empty.
Existing memory databases, observations, sessions and credentials were not copied.

## Remaining user sign-ins

Open the distro:

```powershell
wsl --distribution Ubuntu-26.04
```

Then use the providers you want:

```console
claude auth login
codex login
opencode auth login
agy
```

Use `gh auth login` for GitHub and the native ACLI authentication flow for
Atlassian. Context7 works without a login up to its anonymous limits; `ctx7 login`
provides higher account limits. Optional HeyGen services need their own account;
local HyperFrames rendering already works without one.

Claude manages `~/.claude/skills/synced` after account sign-in. Those downloads
remain account-owned; the installer does not distribute them to other apps.

## Reapply and update

```console
chezmoi apply
python3 -B ~/.local/share/chezmoi/scripts/install-developer-tools --dry-run
python3 -B ~/.local/share/chezmoi/scripts/install-agent-apps --dry-run --from-chezmoi
```

Both installers read one catalog. Source pins and unknown existing customizations
are checked before replacement. Edit declared pins intentionally and verify the
result before publishing an update. Npm/Python top-level package versions are
pinned; their transitive dependencies are not a complete reproducible-build lock.
Native memory plugin/Bun upgrades currently require explicit reconciliation.

## Worker and WSL behavior

The local memory worker is supervised by `claude-mem.service` in the user's
systemd manager, with linger enabled. On this test distro its loopback port is
47118, distinct from the daily-use distro. The installer checks initialized
health, pinned version/path and the exact local service PID, preventing another
distro's worker from being mistaken for this one. Provider login is still
required for real summarization/model turns.

WSL distros on this host share cgroup paths and loopback ports. The setup isolates
the user manager's slice by distro and selects a distinct worker port. Startup
retries handle transient user-manager creation races. WSL can stop an idle
distro even with systemd services; the worker starts again when the distro boots.

This host also reproduced Windows binary interop loss when a distro stopped.
The installer applies Canonical's documented WSL-only systemd-binfmt override
and installs a boot oneshot that restores a missing WSL handler without removing
other handlers. These files belong only to the target distro. See
[Ubuntu's binfmt explanation](https://ubuntu.com/wsl/docs/stable/explanation/binfmt/).

## Validation boundary

The test covers versions, source integrity, skill/plugin discovery, local RTK
hook rewrites, a browser title roundtrip and a local HyperFrames H.264 render.
Repeated apply checks include instruction/configuration contents, modes and
mtimes. Automated tests also cover conflict preservation and restricted doctor
execution. Authenticated model turns require the user sign-ins above.

The local suite passes 71 tests, including fresh native bootstrap cleanup and
modified plugin MCP/dependency manifest checks. An additional real Claude native
installation into an empty fixture home passes at the pinned version. Graphify's
AST extraction produced three nodes and three edges from a small Python fixture;
the installed OpenCode discovers 37 skills. Two targeted WSL restart checks
verified fresh worker PIDs and readiness without a provisioning rerun.

A host limitation remains: stopping this WSL can remove the shared binfmt
registration used to launch Windows executables from another running WSL. The
boot unit restores it when the target starts, but does not prevent kernel/WSL
teardown from removing it. This does not prevent opening the distro from
Windows. Controller recovery can invoke the Windows WSL executable through
`/init`, then restore the missing mapping from the still-running source distro.
No Windows-wide update or shutdown was performed. Do not treat the boot checks
as proof that cross-distro Windows interop persists after target shutdown.

A second disposable WSL is the remaining clean-install acceptance test. The
current instance proves operation, repeat deployment and restart recovery after
incremental development. Do not reset this usable instance merely to run that
separate test.
