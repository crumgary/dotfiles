# Version ownership and updates

`tools.lock.json` records approved tool versions, native artifact hashes and skill
source revisions. Normal apply uses that catalog. Updates are explicit:

```console
dotfiles-update --check
dotfiles-update --apply
dotfiles-update --apply --only opencode
dotfiles-update --apply --commit --push
```

The command is installed with the developer bundle. From a checkout it is also
available as `python3 -B scripts/update-tools`. `--check` is the default and makes
no installation or catalog changes. Discovery uses upstream stable npm/PyPI
releases, official native release manifests and repository commit metadata.
Downloaded native artifacts are checked against publisher checksums when
provided, then pinned by archive and binary SHA-256. Skills retain complete
source archives and explicit exclusions for unrelated upstream symlinks.

`--only` accepts comma-separated tool or skill collection names. It selects
which versions advance; the configured installation is still validated together.
Graphify selections advance its runtime and source metadata together. The
user's chosen Node LTS major is retained. Managed Python tools can advance their
interpreter patch within their existing Python minor series.

## Package policy

- Apt entries are tested minimum baselines, not exact package installation pins.
  Newer distribution/security packages are retained. Apply installs repository
  candidates by name and never requests an automatic downgrade. Explicit tool
  update upgrades managed apt packages, while ordinary OS updates remain under
  apt. NodeSource's repository selects the chosen Node major.
- npm and Python top-level packages have approved versions. Their transitive
  dependencies remain package-manager resolved; this is not a byte-identical
  reproducible-build guarantee.
- Native apps, binaries and skills are pinned. Unknown or edited owned content
  is retained for reconciliation instead of silently replaced. Plugin caches are
  changed through supported app managers, not fabricated by the updater.

## One update owner

The selected managed AI apps use dotfiles as their update owner. Claude's
settings disable its background updater. OpenCode's settings disable update
checks/notices. Antigravity's public command is a small managed launcher that
sets `AGY_CLI_DISABLE_AUTO_UPDATE=true` and invokes the verified `agy-native`
binary; this also works when T3 launches it without an interactive shell.
Codex/OpenCode npm releases are installed through the declared npm recipe.

Manually invoking native upgrade commands remains possible, but can put a tool
ahead of the approved catalog. Run the updater to reconcile stable versions;
normal apply rejects unexpected newer or modified installations instead of
silently downgrading them.

## Candidate validation and failures

Apply resolves a complete candidate and freezes it under
`~/.local/state/dotfiles/updates/`. It stages/verifies sources, uses the normal
developer/app installers, probes the local browser and selected app versions,
checks skill integrity and validates the local memory worker. Only successful
validation replaces the approved catalog. A concurrent catalog edit is retained
and reported as a conflict.

Package installation is not a transaction across apt, npm, uv and native plugin
managers. If a later stage fails, already-installed packages can remain newer.
The old catalog is retained and the frozen candidate is resumable: rerun the
same `--apply` selection. Do not delete the pending state or pull a different
catalog over it to simulate rollback. The error and result report identify the
pending operation; resume after correcting the reported conflict or dependency.

`--commit` commits only the validated catalog; `--push` uses the current branch's
upstream and requires `--commit`. Other staged files are not included. Without
those flags, the tested catalog remains a normal local Git change for review.
Credentials, account login, memory databases and observations are never copied
between machines by this workflow. GitHub authentication improves discovery
rate limits; a fresh machine otherwise uses the public API allowance.

## Acceptance

The test Ubuntu-26.04 WSL successfully ran a complete update to Antigravity
1.5.1, HyperFrames 0.9.16, Graphify 0.9.103 and refreshed skill revisions.
An unchanged follow-up update preserved configuration/catalog contents, modes
and mtimes; ordinary chezmoi apply stayed silent and clean. Auto-update ownership
was checked in Claude/OpenCode settings and the direct Antigravity launcher.
The updated HyperFrames rendered a local 1920x1080 H.264 clip.

Local regression coverage includes candidate failure/resume, concurrent edits,
legacy receipt migration, modified/foreign content preservation, checksum
verification, and real Git commit isolation from other staged files. Provider
model turns still require user login. The existing host WSL interop shutdown
limitation remains documented in [the setup guide](usable-wsl.md).
