# Machine inventory and read-only doctor

Reference for `scripts/dotfiles-doctor`, which inspects an existing user
environment. The doctor does not install, apply, update, fetch repositories,
render templates, or authenticate anything. Installation and tool updates have
separate commands described in the [setup guide](setup.md).

Requires Python 3.9 or newer on the supported Ubuntu/AlmaLinux x86_64 targets. The WSL, devbox and lab profiles
use the existing shell environment; embedded checks only its minimal commands.

## Repository ownership

| Repository | Responsibility |
| --- | --- |
| Public dotfiles | Generic profiles, package/command declarations, templates, doctor and public examples |
| Personal overlay | Personal machine records, endpoints, aliases, rules and custom skills |
| Work overlay | Work machine records, endpoints, policies, configuration and custom skills |
| lab_notes | Infrastructure automation, hardware/network runbooks and troubleshooting |
| axi-ai-tools | Independent tooling checkout; migration out of Firstmate is tracked separately |

Actual machine records live in `machines/<stable-id>.toml` in exactly one enabled
overlay. A machine using both overlays still has one record, with both overlays
selected. A public-only user can keep an explicitly selected local record. The
CLI reads only the record supplied with `--machine`; it never discovers and
merges competing records. `owner` identifies the intended record owner, not the
machine's Git identity. Checkout locations are resolved from the specified home.
No SSH endpoints, credentials, history or runtime databases belong in a record.

## Preview migration

From the public dotfiles checkout:

```console
python3 -B scripts/dotfiles-doctor --import-current --id primary-wsl --owner local
```

This prints TOML to stdout only. Review the ID, platform and selections, then
save a public-only/local record under `~/.config/dotfiles/machines/primary-wsl.toml`.
Use `--owner personal` or `--owner work` only when that overlay is enabled, and
save its record under the corresponding overlay's `machines/` directory. Import does not write a record, alter chezmoi data, select a default
machine, or install anything. It excludes Git identities, endpoints and secrets.
An incomplete selection set is an error, rather than a guessed default.

The reviewed record states the selections the doctor should expect. The doctor
compares local chezmoi selections with it and reports differences. Installation
still reads chezmoi data: editing a machine record does not change or deploy that
data. Machine records are not yet an installation input.

See [machine.example.toml](machine.example.toml) for schema version 1. Required
fields are `schema_version`, `id`, `owner`, `profile`, `os`, `architecture`,
`overlays` and `bundles`. The OS is `ubuntu` or `almalinux`; the actual release
selects host package requirements. Optional `apps` lists the selected AI apps and requires
the developer bundle. Optional `work` defaults to whether the work overlay is
enabled. Set it explicitly for a work machine without a work overlay. The `coding` bundle corresponds to `install_agent_clis`; `developer` corresponds
to the optional `install_developer_tools` selection or the prerequisites implied
by a nonempty app selection. Other settings,
such as Windows usernames, have not migrated into this schema and remain in existing chezmoi data. Unknown fields are rejected.

Optional `[revisions]` entries pin `public` and enabled overlays to full immutable
Git commit IDs. No revision is guessed from a dirty checkout. Unpinned sources
are explicitly unverified. Pinning the repository that contains the record
itself is optional; this slice makes no exact-rebuild guarantee.

## Inspect

```console
python3 -B scripts/dotfiles-doctor --machine ~/.config/dotfiles/machines/primary-wsl.toml
python3 -B scripts/dotfiles-doctor --machine ~/.config/dotfiles/machines/primary-wsl.toml --json
```

`--home PATH` and `--source PATH` inspect a fixture or alternate source checkout.
They do not change the process's PATH: required commands are checked on the
current invocation's PATH. Directory existence is distinct from activation;
a disabled overlay still on disk is reported for review and is never deleted.

Each finding contains `check`, `status`, `path` (or null) and a fixed explanatory
`message`. No file contents or raw Git diagnostics are printed.

| Status | Meaning |
| --- | --- |
| matching | The specific check matched; this does not imply full machine verification |
| drifted | Observed state differs, or a checkout has local changes |
| missing | A required file, overlay or command was not found |
| blocked | Inspection cannot proceed for this check, such as an unsupported platform |
| unverified | Inspection is incomplete, such as a template or unpinned version |

Exit 0 means every performed check matched, exit 1 means at least one finding
requires attention (including unverified), and exit 2 means invalid input or an
inspection input error. JSON is emitted for completed inspection; input errors
write a generic diagnostic to stderr with no partial success document.

## Read-only contract and current coverage

- Reads allowlisted selections from local chezmoi TOML, never sources shell files.
- Checks platform, enabled overlays, instruction fragment presence, declared source revisions, ordinary managed files, relevant
  file access attributes, and private Pi runtime mode 0700.
- Reads baseline/legacy command requirements from the public package declarations
  and managed tool requirements from `config/tools.lock.json`, including selected
  app commands and Python entry points. Native package commands come from the
  detected target's package recipe. Finds commands on PATH without executing
  them. Declared versions are reported as unverified; command presence alone
  does not verify a version, binary hash, plugin registration or service health.
- Walks source files without following source symlinks. Static `dot_`, `private_`,
  `readonly_`, `executable_` and literal `symlink_` file forms are supported.
  Other attributes, templates, symlinked parents and missing targets potentially
  excluded by ignore rules remain unverified. Private and readonly directory attributes are checked independently of file modes. Ignore rules are never executed.
- Does not evaluate `.chezmoi.toml.tmpl`, templates or run scripts. In particular,
  it never calls chezmoi status/diff, password managers or arbitrary executables.
- The only subprocess is `/usr/bin/git` with a fixed HEAD revision query, optional
  locking disabled, fsmonitor and hooks disabled, and a sanitized environment
  excluding inherited Git overrides and global/system configuration. Failures
  are unverified without printing subprocess output. No remote operations run.
  Repository cleanliness is unverified: Git status can execute repository clean
  filters, so it is deliberately not invoked.
- Agent loading behavior, skill installation/hashes, plugin state, MCP and secret
  setup are deferred to the scoped-agent slice. Finding an instruction file
  never claims that an agent loaded it.

All inspections currently return exit 1, including minimal profiles, because
repository cleanliness remains unverified. Templates, source pins and tool
versions can add further verification gaps. The doctor is a useful diagnostic, not a complete provisioning certificate.
The doctor has no mutation commands; `chezmoi apply` and `dotfiles-update` are separate tools.

## Verification

```console
python3 -B -m unittest discover -s tests -v
DOCTOR_SANDBOX=1 python3 -B -m unittest discover -s tests -v
```

The second command requires Linux bubblewrap with user namespaces. Each CLI
invocation runs with `/` mounted read-only and networking disabled; only the
`/dev/null` device is rebound for normal Git use. Fixtures are created outside
the doctor process. All tests also install a Python audit guard denying filesystem
mutation, network activity and subprocesses other than the fixed Git revision query.
Hostile fsmonitor and clean-filter configurations are independently checked to
ensure that neither executes during inspection.
These checks exercise the tool's implementation; it is not a sandbox for reading
untrusted repositories while another process concurrently changes them.
