# Selected AI apps and skills

The selected apps are Claude Code, Codex, OpenCode and Antigravity CLI. This setup
is declared in `config/tools.lock.json`, installed by
`scripts/install-agent-apps`, and registered by `scripts/provision/skill_adapters.py`.
The new setup does not run the legacy install-every-agent script.

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
as TOML rather than interpolated into a shell command. It fingerprints both the
app lock and the developer/skill lock. The installed-state receipt is
`~/.local/state/dotfiles/agent-apps.json`.

## Runtime and installation ownership

Node 26 LTS is explicit policy: the verified version is 26.13.0, installed through
NodeSource's signed Node 26 apt repository at `/usr/bin/node`. This is a NodeSource
package, not Ubuntu's older Node 22 package or a Node-project apt repository. It
supplies npm 11.20.0 too. Node/npm were removed from baseline package ownership;
the developer/runtime bundle owns them. No nvm or second Node manager is added.

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
Native vendor auto-updaters can consequently require a deliberate lock update.
Npm versions are pinned but this slice does not promise fully locked transitive
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

## T3 on Windows

In the Windows T3 desktop app, select `Ubuntu-26.04` as its WSL environment.
Current upstream documentation places this under Settings > Sharing & access;
older app versions label it Connections. T3 installs its matching server runtime
inside the chosen distro automatically. This setup installs the Linux provider
CLIs and Node; it creates no separate T3 server or background service.

The apps must be authenticated inside the selected distro. Windows-side logins
and the daily WSL instance's tokens were not copied. The remaining user actions
are the supported sign-in flows, such as `claude auth login`, `codex login`,
`opencode auth login`, and launching `agy` for its Google sign-in flow.

## Acceptance and limits

On the clean WSL target, all four version probes pass. Native plugin registries
report Superpowers 7.0.2 enabled. Claude's component inspector lists 15 skills and
a SessionStart hook. Antigravity lists 15 bundled skills. OpenCode's actual skill
discovery lists 25 skills: its built-in skill plus nine tstack and fifteen
Superpowers skills. Codex can render the local model-visible prompt without a
model call, exposing both skill collections.

Installation and local discovery are verified separately from authenticated
model behavior. No billable model calls or browser login were made. Full skill
invocation and startup-hook behavior during an authenticated agent turn remain
login-gated. RTK automatic integration is registered through `rtk init` for all
four selected apps. Codex gets a generated instruction file that renders the
canonical shared rules and adds its RTK reference before initialization; the
shared rules remain unchanged. Hook payload checks exercise local command
rewriting without running a model. The pinned RTK OpenCode initializer also
configures Claude, so this bundle requires selecting Claude with OpenCode.
Repeat installation preserves RTK settings and generated plugin files.

See the [existing workstation audit](current-workstation-audit.md) for additional
installed tools and skills considered for future optional bundles.

Upstream documentation used: Node release schedule and NodeSource distributions;
Claude Code setup/skills; official OpenAI skills/plugins docs; OpenCode skills;
Antigravity skills/customization discovery; Superpowers per-app installation;
and T3's `docs/user/install.md` WSL section. CLI help from the installed pinned
versions verified the concrete plugin commands before registration.
