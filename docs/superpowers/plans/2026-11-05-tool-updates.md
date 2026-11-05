# Managed tool updates

Approved scope: implement the update policy discussed with the user, preserve
repeatable apply, and include OpenCode in the top-level agent instructions table.

- Add an explicit updater with check/apply modes and an optional tool selection.
  Resolve stable npm/PyPI/native releases and skill source revisions, retain the
  Node major, and verify downloaded artifact hashes before installation.
- Treat apt version values as tested baselines rather than exact installation
  pins. Allow newer distro/security packages and never downgrade them.
- Add candidate catalog overrides to existing installers. Install and verify a
  frozen candidate before publishing it to the checkout. Keep failed candidates
  resumable; do not pretend installed package changes can be rolled back.
- Authorize native/plugin/Bun upgrades only from verified previously owned state;
  preserve unknown configurations and local edits.
- Give managed AI CLIs a single update owner; document native-update behavior.
- Test release resolution, exclusions, partial failures, candidate publication,
  native upgrades and source conflicts. Exercise check/update/repeat on the test
  Ubuntu-26.04 WSL only. Restore source-host Windows interop if target teardown
  removes its shared handler. Do not apply tools to the daily-use distro.
- Correct README agent discovery entries, add update instructions, review,
  commit and push the completed change.

Completed with a live full update, unchanged repeat, owner configuration checks, local rendering, unit/integration tests and independent code review. The review found a legacy native receipt migration gap; the approved-catalog bootstrap and regression test now cover it.
