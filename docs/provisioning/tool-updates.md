# Version ownership and updates

`tools.lock.json` records approved tool versions, native artifact hashes and skill
source revisions. Normal apply uses that catalog. Updates are explicit:

```console
dotfiles-update --check
dotfiles-update --apply
dotfiles-update --apply --only opencode
dotfiles-update --apply --refresh       # intentionally replace a failed candidate
dotfiles-update --apply --commit --push
```

The command is installed with the developer bundle. From a checkout it is also
available as `python3 -B scripts/update-tools`. `--check` is the default and makes
no installation or catalog changes. Discovery uses upstream stable npm/PyPI
releases, official native release manifests and repository commit metadata.
New npm releases are also resolved with npm in an isolated temporary directory
using `--package-lock-only --ignore-scripts`. This checks the required dependency
graph without installing packages or running lifecycle scripts. A release whose
required version is unavailable is listed under `deferred` and its approved
version is retained. Network/authentication errors remain errors, not silent
release deferrals. Frozen candidates are checked again before any source or
system installation changes.

GitHub discovery uses `GH_TOKEN`, `GITHUB_TOKEN`, or the target user's `gh auth login`
credentials. Successful GitHub API metadata is cached privately for 15 minutes
under `${XDG_CACHE_HOME:-~/.cache}/dotfiles/upstream/github`, including across
`--check` and `--apply --refresh`. Refresh replaces a frozen candidate; it does
not bypass that short metadata cache. Artifact downloads and npm dependency
checks are not cached by this layer. Without a login, GitHub's anonymous hourly
quota is shared with other traffic from the same public IP. Rate-limit errors
report `Retry-After` or the UTC quota reset time and stop without retrying.
Authentication/access failures never fall back to anonymous requests. Run
`gh auth login` on the target machine for a higher quota, or retry after the
reported wait.

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
same `--apply` selection. If the frozen candidate itself is unusable (for
example, a publisher advertised a release before its companion dependency
existed), use `--apply --refresh`. This explicitly resolves a new candidate from
the current catalog and archives the previous candidate as `superseded.json`.
It does not undo package changes already made. Do not delete pending state to
simulate rollback. The error and result report identify the
pending operation; resume after correcting the reported conflict or dependency.

`--commit` commits only the validated catalog; `--push` uses the current branch's
upstream and requires `--commit`. Other staged files are not included. Without
those flags, the tested catalog remains a normal local Git change for review.
Credentials, account login, memory databases and observations are never copied
between machines by this workflow. GitHub authentication improves discovery
rate limits; a fresh machine otherwise uses the public API allowance.
