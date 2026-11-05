# Node 26, selected agent apps and shared skills

Goal: Make the selected Claude Code, Codex, OpenCode and Antigravity CLI setup reproducible from dotfiles, with a current LTS runtime and supported skill/plugin registration.

- [x] Move runtime ownership from Ubuntu's Node22/npm packages to pinned Node26 LTS from NodeSource's signed repository. Remove duplicate baseline npm ownership; NodeSource supplies npm.
- [x] Declare immutable app artifacts or exact npm versions in a separate lock. Install native Claude/Antigravity without copying old runtime state or sourcing upstream shell edits. Use per-user npm for Codex/OpenCode.
- [x] Add regression tests for conflict-safe skill adapters, repeat configuration, selected-app validation, and dry-run no mutation.
- [x] Register tstack skills from the user's pinned fork and Superpowers through per-app supported mechanisms. Preserve custom skills and do not edit app-owned plugin caches.
- [x] Add an explicit selected-app list to chezmoi and a versioned runner. Keep legacy install-every-agent disabled.
- [x] Deploy scripts to clean Ubuntu-26.04, verify noninteractive PATH and versions, check actual skill/plugin discovery where authentication is not required, and record login-gated checks honestly.
- [x] Verify repeat deployment preserves managed config and custom edits; run tests/lint and independent review.
- [x] Document existing-tool audit with provenance and optional future bundles. Do not install every organic host tool.

T3 Windows owns its matching WSL server runtime. Install Linux provider CLIs in the selected distro and point the Windows app at it; no second T3 service is created.

RTK automatic integration is initialized through the pinned native CLI. Codex instructions render the canonical rules plus an app-specific reference, protecting the shared rules from native initializer edits. Authenticated model turns remain pending user login.
