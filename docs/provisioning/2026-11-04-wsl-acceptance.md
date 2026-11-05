# Ubuntu 26.04 WSL baseline acceptance

Target: `Ubuntu-26.04`, Ubuntu 26.04.1 x86_64, user `gcrum`.

## Design direction

The existing `Ubuntu-26.04-AI` environment supplies requirements and experience;
its organically accumulated tool/config layout is not the target architecture.
Prefer standard locations and supported package managers. Keep tool ownership
explicit and avoid multiple installations of the same command. Optional personal,
work and agent bundles need their own acceptance runs.

Ubuntu 26.04's signed apt repositories provide the core CLI and editor versions
needed here. Its package path now owns eza, bat, fd-find, zoxide, fzf, keychain,
glow, git-delta, starship and Neovim, plus locale/font prerequisites. Older
systems retain the existing release-download fallback. Commands named `batcat`
and `fdfind` count as installed tools; they no longer trigger duplicate downloads.

## Deployment performed

- Started from a clean user home with no chezmoi or overlay configuration.
- Installed system prerequisites using the explicit public package declaration.
  Initial installation used WSL root; subsequent apply used the normal user with
  the passwordless sudo configured by the user.
- Downloaded chezmoi 2.71.0 from its release, verified its published SHA-256, and
  installed it in `~/.local/bin`.
- Staged the public working-source snapshot, not the current workstation's home,
  caches, credentials or runtime databases. The source includes uncommitted work;
  this is an integration test, not a published-release acceptance certificate.
- Used explicit public-only WSL configuration with the test Git identity
  `Dotfiles Acceptance <dotfiles-test@example.invalid>`.
- Disabled overlays, agent installers, editor AI, convenience links and Windows
  font installation. No Windows username was supplied.
- First deployment exposed a mode-0755 Pi runtime directory. Renaming its chezmoi
  source directory to `private_agent` enforces mode 0700, including correction of
  pre-existing directories. A real chezmoi fixture regression covers both cases.
- Replaced the first test run's standalone CLI binaries with distro packages.
  Prior test-generated binaries were preserved outside PATH under
  `~/.local/state/dotfiles/acceptance-release-backup` in the test instance.

## Verification

- Existing `scripts/smoke-test-wsl.sh` passed: tools, shell modules, ble.sh, Nerd
  Font, starship config, Neovim config/binary, tmux config and Git delta wiring.
- Interactive shell startup passed. Ctrl-R uses `__fzf_history__`; Ctrl-T uses
  `fzf-file-widget`. Git identity is the test identity and pager is delta.
- Core commands resolve to `/usr/bin`, without user-local binaries shadowing the
  package installations.
- Repeat apply exited 0, emitted no output, and changed none of the 35 checked
  managed file/directory entries, their access modes, or package versions.
- `chezmoi status --exclude scripts` was empty after deployment and repeat apply.
- Pi runtime directory is 0700.
- Local regressions use fixture homes. The package installer test binds a
  controlled Ubuntu 26.04 os-release file in bubblewrap, avoiding assumptions
  about the test runner's distribution and denying real network/system writes.

Installed apt versions: Neovim 0.11.6, eza 0.23.4, bat 0.25.0, fd-find 10.3.0,
fzf 0.67.0, delta 0.18.2, glow 2.1.1, keychain 2.8.5, starship 1.22.1 and
zoxide 0.9.8. Package revisions are recorded in the local JSON result.

## Boundaries still open

This run validates the public baseline using existing chezmoi deployment. It does
not implement the proposed plan/apply/update command suite, immutable acquisition
for every dependency, interruption recovery, private authentication, scoped agent
installation, or a Linux VM acceptance run. The smoke test launches Neovim without
plugins; full LazyVim plugin synchronization and language tooling need separate
verification. Installed tools may use upstream download fallbacks on older OSes;
those paths have not been newly accepted by this WSL run.

Target logs: `/tmp/dotfiles-apt.log`, `/tmp/dotfiles-file-plan.txt`,
`/tmp/dotfiles-apply-first.log`, `/tmp/dotfiles-apply-optimized.log`,
`/tmp/dotfiles-smoke.log`, and `~/dotfiles-repeat-apply.log`.
Controller result: `/tmp/wsl-acceptance-result.json`.


## Editor correction

The user clarified that regular Vim is their editor. The baseline now installs
Vim, uses `~/.vimrc`, and selects Vim for EDITOR/VISUAL even if Neovim also exists.
Neovim/LazyVim source configuration, download/install requirements, editor-AI
init prompts and checks were removed. The initial Neovim results above describe
the first test run, not the final baseline. Test-instance Neovim artifacts are
preserved outside their active locations, and its test-installed packages were
removed. The existing daily-use distro was not changed.

The corrected Vim baseline passed the WSL smoke test. Fresh interactive shells
report `EDITOR=vim` and `VISUAL=vim`, resolving to `/usr/bin/vim` (Ubuntu Vim
9.1.2141). Neovim is absent from PATH and `~/.config/nvim` is absent. A repeat
apply emitted no output and the managed-file status remained clean. Local
verification now includes 34 passing tests plus Ruff and Bash ShellCheck checks.

## Selected apps, shared skills and RTK acceptance

The final test target runs Node 26.13.0 LTS and npm 11.20.0 from the signed
NodeSource Node 26 repository. The versioned selected-app installer verifies
Claude Code 2.1.318, Codex 0.166.0, OpenCode 1.19.5 and Antigravity CLI 1.5.0.
Superpowers 7.0.2 is registered through each app's supported plugin mechanism;
nine tstack skills come from the pinned crumgary fork.

RTK's native initializers register the four integrations. Codex's generated
instruction file renders the canonical shared rules and includes its RTK
reference before initialization. Shared rules are unchanged. Representative
native hook payloads for Claude, Codex and Antigravity rewrite `git status` to
`rtk git status` without executing a model turn. Antigravity's registry reports
RTK enabled. OpenCode's skill discovery still lists 25 skills after registration.
Its large debug JSON is redirected to a regular file before parsing, because
this pinned CLI can truncate its output when stdout is a pipe.

A subsequent direct installer run and chezmoi apply preserve instruction,
settings, hook, receipt, shell and Git file hashes, modes and nanosecond mtimes.
The repeat apply is silent and chezmoi status is clean. Local verification:
51 tests pass both normally and with the doctor's restricted execution enabled;
Ruff check/format and git diff whitespace checks pass.

Controller evidence: `/tmp/wsl-agent-apps-acceptance.json`. Target apply log:
`/tmp/dotfiles-agent-final-apply.log`. Provider authentication and full agent
turns remain pending the user's sign-in. Windows T3 should select Ubuntu-26.04;
it owns the matching WSL server runtime automatically. The daily-use distro's
deployed configuration was not changed.

## Completed usable setup extension

The extension installs the remaining shared skills and dependencies, claude-mem
for all four selected apps, and a supervised fresh worker. Full details, evidence
and the remaining host interop limitation are in [the usable WSL guide](usable-wsl.md).
Validation includes 71 tests, a real fresh-home Claude native install, Graphify
AST extraction, 37 OpenCode skills, a browser roundtrip, local H.264 rendering,
and two target-only worker restart checks.
