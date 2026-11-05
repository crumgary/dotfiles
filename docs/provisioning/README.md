# Provisioning documentation

Start with the [setup guide](setup.md) to configure the optional tools, sign in
and maintain a machine. These pages are written for the person operating or
maintaining the repository; agents can use the same references.

| Guide | Purpose |
|---|---|
| [Setup](setup.md) | User workflow: select tools/apps, authenticate, reapply and update. |
| [Tool updates](tool-updates.md) | Version ownership, update commands, caching and failure recovery. |
| [Developer tools](developer-tools.md) | Installer reference: package managers, install locations and integrity checks. |
| [AI apps and skills](agent-apps.md) | Installer reference: app selection, shared skills, plugins, rules and update ownership. |
| [Machine inventory and doctor](doctor.md) | Machine-record format, read-only inspection and its limitations. |

## What controls installation

- `config/tools.lock.json` is the approved version/source catalog. Change it
  through the [tool updater](tool-updates.md).
- `home/.chezmoidata/packages.toml` declares baseline package requirements.
- Chezmoi data selects the profile, overlays and optional bundles/apps.
- `scripts/` and chezmoi templates implement installation and configuration.
- Machine records are currently inputs to the doctor; see
  [machine.example.toml](machine.example.toml) and [the doctor reference](doctor.md).

Markdown documents explain those inputs and behavior. Installers do not read
these guides as configuration. Exact package versions, hashes and skill revisions
belong in the catalog, not duplicated in current documentation.
