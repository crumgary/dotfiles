# Machine inventory and read-only doctor implementation plan

> **For agentic workers:** Use executing-plans to implement this plan task by task in this session.

**Goal:** Declare a machine once and inspect its environment without applying configuration.

**Architecture:** A Python standard-library CLI reads a strict TOML inventory and existing chezmoi data. Independent checks return structured findings. Static managed files are compared directly; templates and unaudited agent loading are explicitly unverified.

**Tech Stack:** Python 3.11+, tomllib, unittest, Linux bubblewrap for acceptance verification.

## Global constraints

- Inventory records belong in the enabled personal or work overlay; public examples contain no machine identity.
- No live apply, network, sudo, password-manager access, installer execution, or arbitrary template evaluation.
- Never print config contents, credentials, history, or subprocess output.
- Keep existing reconciliation edits and other repositories intact.
- Required failures and incomplete checks return a nonzero exit code.
- Only the fixed Git revision probe may spawn a subprocess; disable optional locks, fsmonitor, hooks and global/system configuration.

### Task 1: Validated inventory and migration preview

Files: `scripts/dotfiles-doctor`, `scripts/provision/inventory.py`, `scripts/provision/__init__.py`, `tests/test_doctor.py`, `docs/provisioning/machine.example.toml`.

Interface: `load_record(path) -> dict`; CLI `--machine RECORD --home HOME --source SOURCE --json`. `--import-current --id ID --owner personal|work|local` prints a record to stdout without writing a file. Commands use `python3 -B` to avoid bytecode writes.

- [x] Write CLI fixture tests for malformed records, unknown fields, overlay ownership, duplicate overlays, unsupported platforms, contradictory work selections, and import previews that exclude secrets.
- [x] Run `python3 -B -m unittest discover -s tests -v`; confirm missing implementation fails.
- [x] Implement strict validation, public examples and read-only migration preview. Accept schema version 1, stable IDs, four existing profiles, Ubuntu x86_64, explicit overlays and owner, optional bundle names and immutable source revisions. Import only profile and boolean selections, never identity, keys or endpoints.
- [x] Re-run inventory tests.

### Task 2: Structured checks and human-readable CLI

Files: `scripts/provision/checks.py`, `scripts/provision/managed.py`, CLI, tests, existing `home/.chezmoidata/packages.toml`.

Interface: `inspect(record, home, source) -> list[dict]`; findings contain `check`, `status`, `path`, `message`. Status is matching, drifted, missing, blocked or unverified. Exit 0 only for entirely matching checks, 1 for findings, 2 for invalid inputs.

- [x] Add fixture tests that detect changed static files, missing required commands, wrong private permissions, disabled overlay drift, missing overlays, unsafe source attributes and unevaluated malicious templates.
- [x] Run tests and confirm new behaviors fail before implementing them.
- [x] Implement local config comparison, platform expectations, overlay availability, safe static source mapping, profile tool declarations and presence/version distinctions, fixed Git revision probe and revision comparison. Do not run tools to ask for versions. Treat agent instruction loading and templates as unverified.
- [x] Re-run all CLI tests and check human output and JSON agree.

### Task 3: Restricted acceptance and documentation

Files: `tests/test_doctor.py`, `docs/provisioning/README.md`, main README.

- [x] Add an execution guard test denying network, file mutation and subprocesses except the fixed Git revision probe, including malicious templates and executable decoys.
- [x] Run the fixture suite under `bwrap --ro-bind / / --unshare-net`, with a temporary fixture directory explicitly writable only by the test setup; run the doctor itself against a fully read-only filesystem.
- [x] Run a migration preview and live doctor without redirecting output to a machine record. Verify no live configuration changes and report incomplete template/version checks honestly.
- [x] Document record ownership, migration review, stable IDs, invocation, status/exit contracts, and deferred plan/apply/update and agent installation.
- [x] Run the full test suite, syntax checks and `git diff --check` for changed files. Review the complete patch before handoff.

No commits or live deployment are part of this slice. The earlier reconciliation approval gate remains in place.


## Review adjustment

Independent review reproduced execution of a repository clean filter through
Git status. Repository cleanliness is therefore reported as unverified in this
slice; only the fixed HEAD query is permitted. This follows the design contract
that a check unable to prove read-only behavior must report unverified. No raw
Git status call remains. Additional regressions cover decoded path containment,
unreadable source traversal and independent directory/file permission scopes.
