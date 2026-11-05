# Developer tools and skill-source bundle implementation plan

Goal: Install the user's requested developer tools on the clean WSL instance through declared supported package sources, and stage immutable skill sources without copying the organic workstation layout.

Scope: gh and acli from their signed official apt repositories; skopeo and asciinema from Ubuntu; pinned verified RTK/actionlint binaries; pinned per-user npm gh-axi/Playwright; pinned tstack fork and Superpowers sources. Only explicitly selected AI apps receive activation. No credentials are copied or login performed automatically.

- [x] Verify upstream docs, package availability and current immutable source revisions.
- [x] Write failing tests for dry-run output/no mutation, checksums, path containment and executable skill scripts.
- [x] Implement `config/tools.lock.json`, `scripts/install-developer-tools`, and bounded helpers in `scripts/provision/`.
- [x] Add dry-run and explicit apply modes. Preserve existing source edits; repeat applies verify installed versions/hashes and leave skill-source edits intact with an actionable conflict.
- [x] Add opt-in chezmoi configuration and source-runner integration, separate from the legacy install-every-agent script.
- [x] Deploy to Ubuntu-26.04; test command help/versions, harmless actionlint validation and Chromium launch against local content.
- [x] Verify repeat installation and unchanged shell configuration.
- [ ] Activate skills through the selected apps' supported mechanisms; missing authentication or app choice is reported separately.
- [x] Run tests, lint and independent review, document actual acceptance and remaining app/login work.

The installer is an explicit acquisition/install command, not the full proposed reviewed-plan/apply/update framework. Its dry run lists declarations without rendering templates, network or target writes. It does not claim that staged skills are loaded.


Current app activation state: waiting for the user's selection of Claude Code,
Codex or both. The tool bundle and pinned source staging are accepted on WSL;
no app-specific skill/plugin/hook activation or authentication has occurred.
