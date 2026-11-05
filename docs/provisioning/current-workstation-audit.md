# Existing WSL tool and skill audit

Scope: the daily-use `Ubuntu-26.04-AI` environment, inspected on 2026-11-04.
This is an inventory of declarations and installed metadata, not a migration of
its home directory. No credentials, history, conversations or memory databases
were read or copied. Installed presence does not prove which historical command
originally installed an item.

## Already declared in dotfiles

The public package manifest declares the shell, Vim, Git and standard CLI tools.
The older all-in-one agent script declares nvm LTS, Claude Code, Codex, OpenCode,
Antigravity, herdr, claude-mem and Playwright. That script remains available for
existing configurations but is disabled for new setups in favor of explicit app
selection. Its declarations establish intended acquisition, not historical
provenance of every current binary.

The new developer bundle owns Node 26, gh, ACLI, gh-axi, RTK, actionlint, skopeo,
asciinema and Playwright. It pins tstack and Superpowers sources. The selected-app
bundle now owns Claude Code, Codex, OpenCode and Antigravity installation and
per-app registration.

## Useful installations outside those declarations

These are candidates for separate optional bundles, not automatically selected
requirements:

- **Browser workflow:** npm-installed `chrome-devtools-axi` 0.1.39 and the local
  `~/bin/axi-chrome` helper. The helper's reviewed source and WSL startup sequence
  are documented in `lab_notes/host_tools.adoc#axi-chrome`. They should be packaged
  together with a declared supported browser, including the initial pages/select
  step. A wrapper alone would not reproduce the working setup.
- **Agent utilities:** npm-installed `lavish-axi` 0.1.90, `tasks-axi` 0.2.6,
  `quota-axi` 0.1.64 and `@agentclientprotocol/codex-acp` 1.1.7. Their installation
  is present in npm metadata but absent from the old bootstrap declarations.
- **Documentation and knowledge:** `find-docs` / `find-skills` skills and the
  Context7 instructions; `graphifyy` 0.9.15 through uv with graphify commands.
  Graphify is referenced in shared instructions without a corresponding dotfiles
  acquisition declaration. Declare its tool and skill together if retained.
- **Containers:** Docker CE/CLI, containerd, buildx, Compose and local `k3d`.
  Only skopeo is currently in the selected bundle. A Docker daemon is a separate
  workload choice, not an implicit dependency of AI apps.
- **Build and embedded development:** CMake 3.31.6 and Zig 0.16.0 through pipx;
  cargo-llvm-cov, cargo-zigbuild and git-cliff through Cargo; cross GCC, musl
  tooling, bison/flex, OpenSSL/libelf headers, protoc and grpcurl. Keep these in
  project/workload bundles instead of installing all of them for every machine.
- **Documents and media:** ffmpeg, pandoc, Asciidoctor/PDF, poppler-utils,
  LibreOffice, Ruby, xvfb, GStreamer and HyperFrames helper commands. Some helpers
  invoke floating `hyperframes@latest` and remote helpers acquire another Node
  runtime. Review those recipes before adopting them into the new single-runtime
  setup.

Other local binaries and creative applications are installed, including goose,
treehouse, orca-ide, rust-docs-mcp, jira, no-mistakes, and several craft launchers.
Their presence is proven; this audit does not establish an intended baseline role
or reproducible acquisition source for each one.

## Migration update

The requested named skills and their supporting runtimes are now installed on
the test WSL, including all four claude-mem integrations. See
[the usable setup and sign-in guide](usable-wsl.md). The table below preserves
the gaps identified during the initial audit; it explains the work required,
not the final deployment status. `no-mistakes` and unrelated workload tools
remain outside the selected setup.

## Detailed skill findings

The items below were found on the existing daily-use WSL. Their presence does
**not** mean they have been provisioned on the new test WSL. The initial deployment
installed tstack, Superpowers and RTK integrations. The following table records
what acquisition recipes or account-driven installation were missing then.

Paths below are relative to the user's home. A symlink is distinguished from an
independent directory. Presence means the skill's instructions exist, not that
its external services, dependencies, or authenticated execution were tested.

| Capability | Installed evidence and source | Gap at initial audit |
| --- | --- | --- |
| claude-mem | Claude plugin registry: `claude-mem@thedotmack` 15.9.0, commit `63efe315b4bb85b21dad871cf7e6a9dbd1867864`; Codex's local plugin cache has 15.8.1 with its own Codex manifest. Both identify `thedotmack/claude-mem` upstream. | Not installed by the new selected-app recipe. The legacy bootstrap declares it but is disabled. Plan app integration, worker/service ownership and fresh data separately. |
| HyperFrames | `.agents/skills/hyperframes`, `hyperframes-cli`, `hyperframes-registry`; separate Claude copies; Gemini and OpenCode link to the Claude copies. Shared skill lock records `heygen-com/hyperframes`. | Not provisioned. Need one pinned source plus runtime/browser/render dependencies and app adapters. |
| media-use | `.agents/skills/media-use`, a separate Claude copy, Gemini/OpenCode links to the Claude copy. Recorded source is `heygen-com/hyperframes`, alongside the other three HyperFrames skills. | Not provisioned. Keep with the HyperFrames collection because it references sibling resources. Review local media tools and optional HeyGen login separately. |
| Context7 | Shared `AGENTS.md` contains Context7 instructions; `find-docs` calls `npx ctx7@latest`. No separate skill named `context7` was found in the inspected personal skill roots. | Instructions are deployed; a fixed CLI version is not declared. The current npx recipe fetches on demand. Account/quota setup was not migrated or tested. |
| find-skills | `.agents/skills/find-skills`, with Claude symlink to it. Shared skill lock records `vercel-labs/skills`, `skills/find-skills/SKILL.md`. | Not provisioned. Pin its source and review its package acquisition commands before adoption. |
| find-docs | Independent directories under `.agents/skills` and `.claude/skills`; skill describes current documentation lookup through Context7. No matching acquisition record in the shared skill lock. | Not provisioned. Establish source ownership, compare the copies, and declare Context7 together. The user spelling `find-codcs` is interpreted as this installed name. |
| ms-rust | `.agents/skills/ms-rust` links to `~/projects/ms-rust-skill`; Claude links to the shared link. Checkout origin is `https://gitlab.com/lx-industries/ms-rust-skill.git`, HEAD `029818f763afd314c46a7adae3118e6af2b3cba6`. | Not provisioned. Current setup depends on a development checkout. HEAD alone does not prove the installed tree has no local changes; retain any intentional changes before choosing a revision. |
| task-observer | `.agents/skills/task-observer`, Claude symlink to it; installed frontmatter version 3.6.0. Shared lock records `rebelytics/one-skill-to-rule-them-all`. | Not provisioned. Install the whole bundle, then configure one stable observation-log location. Existing observation records are data, not disposable installer output. |
| graphify | `.claude/skills/graphify` with eight reference documents; `uv tool list` records `graphifyy` 0.9.15 exposing `graphify` and `graphify-mcp`. Shared instructions reference the skill. | Not provisioned. No shared-lock source record for this skill; declare both the Python tool and matching skill source. Existing generated knowledge graphs are separate project data. |
| Draw.io | `.agents/skills/drawio`; lock records `jgraph/drawio-mcp`, `plugins/claude-code/skills/drawio/SKILL.md`. Claude plugin registry also records `drawio@drawio` 1.2.0. | Not provisioned. Decide which supported plugin/skill integration each app should receive. |
| Jira / Confluence | `.agents/skills/jira-axi` and `confluence-axi`; Claude links to them. Shared lock records `emilchristensen/atlassian-axi`. | The new developer bundle installs ACLI, but these skills and the AXI wrappers are not yet declared. CLI installation does not establish skill availability or account authentication. |
| no-mistakes | Independent skill directories under `.agents/skills` and `.claude/skills`; no source record in the shared lock. | Not provisioned. Establish provenance and compare copies before migration. |
| Superpowers | Daily Claude registry has 6.1.1; daily Codex has individual workflow skill directories. | New test setup deliberately uses pinned 7.0.2 through supported app integrations, rather than copying the old layout. |

### What the existing skill lock establishes

`~/.agents/.skill-lock.json` is a third-party installer record, distinct from
this repo's `config/tools.lock.json`. It records nine named skills, their source
repositories, skill paths, folder hashes, and installation/update dates. Those
nine are Jira, Confluence, find-skills, task-observer, Draw.io, the three
HyperFrames skills, and media-use. A folder hash is not a pinned repository
commit. These records identify likely upstream sources but are not sufficient
alone to reproduce every installed byte.

The installed layouts contain real duplication. In particular, the HyperFrames
collection is present independently under `.agents` and `.claude`, while Gemini
and OpenCode follow the Claude copies. A read-only file comparison found:

| Independent shared / Claude copies | Shared file count | Claude file count | Result |
| --- | ---: | ---: | --- |
| hyperframes | 77 | 77 | Identical relative paths and SHA-256 file contents |
| hyperframes-cli | 13 | 13 | Identical |
| hyperframes-registry | 13 | 13 | Identical |
| media-use | 116 | 116 | Identical |
| no-mistakes | 1 | 1 | Identical |
| find-docs | 1 | 1 | Different: the shared copy adds guidance about running Context7 outside Codex's sandbox after DNS/network failures |

Comparison excludes Git internals and Python bytecode caches. This establishes
content equality for these installed copies, not correspondence to a particular
upstream revision. Preserve the intentional Codex-specific instruction when
consolidating find-docs.

### What `synced` means

`~/.claude/skills/synced/` is a reserved Claude Code download location for skills
from the signed-in claude.ai account. It is **not a skill named synced**, not a
cross-app symlink, and not dotfiles synchronization. Claude downloads account
skills one way; local edits there do not update the account and may be replaced.
Manage those skills in claude.ai and let Claude recreate them after sign-in.
See [Claude's synced-skill documentation](https://code.claude.com/docs/en/skills#skills-synced-from-claudeai).

The old WSL has twelve skill packages beneath an account-scoped subdirectory:
`docs`, `docx`, `pdf`, `pptx`, `xlsx`, `google-workspace`, `import-memory`,
`morning`, `skill-creator`, and three organization-specific branding skills.
Account identifiers and organization skill content are omitted from this public
report. These are downloaded packages, not an assurance that all their required
connectors are configured. Do not copy the account directory into the new WSL
or use it as a source for Codex/OpenCode/Antigravity installation.

The installed `graphifyy` package metadata identifies
`https://github.com/safishamsi/graphify` as its upstream and requires Python
3.10 or newer. Its current uv environment uses Python 3.13. Package metadata
establishes the tool's source; it does not establish that the separately
installed Claude skill exactly matches that package's release.

### claude-mem needs more than a SKILL.md

claude-mem bundles multiple skills, hooks, an MCP integration and worker/runtime
components. The old Claude plugin registry and the Codex local plugin manifest
are separate installation evidence; a cached package alone does not establish
that an app has enabled every component. A reproducible recipe must declare the
plugin source/revision, supported per-app registration, runtime/service setup,
and a health check. Memory databases, backups, sync accounts and historical
observations need a separate data decision. This audit inspected package
metadata only, not memory records, conversations or database contents.

## Recommended next scope

After the four selected apps and shared skills are accepted, the most useful
next decision is whether to add the browser workflow and documentation/knowledge
capabilities. Containers, build tooling, media/publishing and the remaining AXI
utilities can remain separate named bundles. The old machine is evidence of
requirements, not a filesystem layout to duplicate.
