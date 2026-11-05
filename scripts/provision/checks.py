"""Filesystem checks and fixed read-only Git probes; no template or tool execution."""

import json
import platform
import shutil
import stat
import subprocess
from pathlib import Path

from .inventory import OVERLAYS, InputError, current_data, read_toml
from .managed import inspect_files

GIT = "/usr/bin/git"


def git_probe(repository, arguments):
    """The only subprocess boundary: a fixed Git revision query with sanitized env."""
    if arguments != ["rev-parse", "HEAD"]:
        raise ValueError("Unsupported Git probe")
    env = {
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
    }
    command = [
        GIT,
        "--no-optional-locks",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.untrackedCache=false",
        "-c",
        "core.hooksPath=/dev/null",
        "-C",
        str(repository),
        *arguments,
    ]
    try:
        result = subprocess.run(
            command, env=env, capture_output=True, timeout=10, check=False
        )
        return result.stdout if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def inspect(record, home, source):
    home, source = home.absolute(), source.absolute()
    findings = []

    def add(check, status, message, path=None):
        findings.append(
            {
                "check": check,
                "status": status,
                "message": message,
                "path": str(path) if path is not None else None,
            }
        )

    # Do not execute a shell or source os-release.
    try:
        os_id = next(
            line.split("=", 1)[1].strip().strip('"')
            for line in Path("/etc/os-release").read_text().splitlines()
            if line.startswith("ID=")
        )
    except (OSError, StopIteration):
        os_id = None
    add(
        "platform:os",
        "matching" if os_id == record["os"] else "blocked",
        "OS matches declaration."
        if os_id == record["os"]
        else "OS is unavailable or unsupported for this record.",
    )
    add(
        "platform:architecture",
        "matching" if platform.machine() == record["architecture"] else "blocked",
        "Architecture matches declaration."
        if platform.machine() == record["architecture"]
        else "Architecture differs from declaration.",
    )
    config = home / ".config/chezmoi/chezmoi.toml"
    try:
        data = current_data(home)
    except InputError:
        add(
            "configuration",
            "missing" if not config.exists() else "blocked",
            "Cannot read existing chezmoi selections.",
            config,
        )
    else:
        selections = {
            "profile": record["profile"],
            "work": record["work"],
            "bootstrap_priv_overlay": "personal" in record["overlays"],
            "bootstrap_work_overlay": "work" in record["overlays"],
            "install_agent_clis": "coding" in record["bundles"],
        }
        if "install_developer_tools" in data or "developer" in record["bundles"]:
            selections["install_developer_tools"] = "developer" in record["bundles"]
        if "agent_apps" in data or record.get("apps"):
            selections["agent_apps"] = record.get("apps", [])
        for key, expected in selections.items():
            observed = data.get(key)
            if key == "install_developer_tools" and type(data.get(key, False)) is bool:
                observed = data.get(key, False) or bool(data.get("agent_apps"))
            matches = type(observed) is type(expected) and observed == expected
            add(
                "selection:" + key,
                "matching" if matches else "drifted",
                "Selection matches inventory."
                if matches
                else "Local selection differs or is absent; review inventory migration.",
                config,
            )

    repositories = {"public": source}
    for name, relative in OVERLAYS.items():
        path = home / relative
        enabled = name in record["overlays"]
        present = path.is_dir()
        add(
            "overlay:" + name,
            ("matching" if present else "missing")
            if enabled
            else ("drifted" if path.exists() or path.is_symlink() else "matching"),
            "Enabled overlay directory is present."
            if enabled and present
            else "Enabled overlay directory is missing."
            if enabled
            else "Disabled overlay still exists; review its activation separately."
            if path.exists()
            else "Overlay is disabled and absent.",
            path,
        )
        if enabled and present:
            repositories[name] = path
            fragment = path / "agents/AGENTS.md"
            if record["profile"] != "embedded":
                add(
                    "instructions:" + name,
                    "matching" if fragment.is_file() else "missing",
                    "Instruction fragment is present; loading is checked separately."
                    if fragment.is_file()
                    else "Instruction fragment is missing.",
                    fragment,
                )

    for name, path in repositories.items():
        if not (path / ".git").exists():
            add(
                "repository:" + name,
                "unverified",
                "Not a standalone Git checkout; cleanliness cannot be verified.",
                path,
            )
            continue
        add(
            "repository:" + name,
            "unverified",
            "Cleanliness was not checked: Git status can execute repository filters.",
            path,
        )
        revision = record["revisions"].get(name)
        if revision:
            actual = git_probe(path, ["rev-parse", "HEAD"])
            add(
                "revision:" + name,
                "unverified"
                if actual is None
                else "matching"
                if actual.strip().decode("ascii", errors="replace") == revision
                else "drifted",
                "Could not inspect HEAD."
                if actual is None
                else "Compared HEAD with the declared immutable revision.",
                path,
            )
        else:
            add(
                "revision:" + name,
                "unverified",
                "No immutable source revision is declared.",
                path,
            )

    inspect_files(source / "home", home, add)
    runtime = home / ".pi/agent"
    if record["profile"] != "embedded":
        if runtime.is_symlink():
            add(
                "permission:.pi/agent",
                "blocked",
                "Private runtime directory is a symlink; inspect its ownership.",
                runtime,
            )
        elif runtime.is_dir():
            mode = stat.S_IMODE(runtime.stat().st_mode)
            add(
                "permission:.pi/agent",
                "matching" if mode == 0o700 else "drifted",
                "Private runtime directory has mode 0700."
                if mode == 0o700
                else "Private runtime directory must have mode 0700.",
                runtime,
            )
        else:
            add(
                "permission:.pi/agent",
                "missing",
                "Private runtime directory is missing.",
                runtime,
            )
        add(
            "agent-loading",
            "unverified",
            "Instruction loading by individual agents has not been exercised.",
        )
    inspect_tools(source, record, add)
    return findings


def managed_requirements(catalog, selected):
    """Derive command requirements from the installer catalog without execution."""
    developer = catalog["developer"]
    aliases = {
        "nodejs": ["node", "npm"],
        "imagemagick": ["magick"],
        "poppler-utils": ["pdftotext"],
        "librsvg2-bin": ["rsvg-convert"],
    }
    commands, versions = [], {}
    for package, version in developer["apt"].items():
        names = aliases.get(package, [package])
        commands.extend(names)
        versions[names[0]] = version
    for command, entry in developer["binaries"].items():
        commands.append(command)
        versions[command] = entry["version"]
    for command, version in developer["npm"].items():
        commands.append(command)
        versions[command] = version
    for entry in developer.get("python", {}).values():
        commands.extend(entry["commands"])
        versions.update({name: entry["version"] for name in entry["commands"]})
    for name in selected:
        entry = catalog["agents"][name]
        commands.append(entry["command"])
        versions[entry["command"]] = entry["version"]
    commands.extend(["axi-chrome", "dotfiles-update"])
    if any(not isinstance(name, str) or not name for name in commands):
        raise ValueError("Invalid catalog command declaration")
    return commands, versions


def inspect_tools(source, record, add):
    path = source / "home/.chezmoidata/packages.toml"
    try:
        packages = read_toml(path)
        catalog = packages["doctor"]
        commands = list(
            catalog["embedded"]
            if record["profile"] == "embedded"
            else catalog["common"]
        )
        for bundle in record["bundles"]:
            if bundle != "developer":
                commands.extend(catalog["bundles"][bundle])
        versions = packages.get("release_binary", {})
        if not isinstance(commands, list) or any(
            not isinstance(c, str) or not c for c in commands
        ):
            raise ValueError
    except (InputError, KeyError, TypeError, ValueError):
        add(
            "tools",
            "unverified",
            "Required-tool declarations are missing or invalid.",
            path,
        )
        return
    if "developer" in record["bundles"]:
        tool_catalog = source / "config/tools.lock.json"
        try:
            managed, pinned = managed_requirements(
                json.loads(tool_catalog.read_text()), record.get("apps", [])
            )
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            add(
                "catalog:tools",
                "unverified",
                "Managed-tool catalog is missing or invalid.",
                tool_catalog,
            )
        else:
            commands.extend(managed)
            versions.update(pinned)
            add(
                "catalog:tools",
                "matching",
                "Tool requirements read from the installer catalog; installation is checked separately.",
                tool_catalog,
            )
    for command in dict.fromkeys(commands):
        aliases = command.split("|")
        resolved = next(
            (shutil.which(alias) for alias in aliases if shutil.which(alias)), None
        )
        name = aliases[0]
        add(
            "tool:" + name,
            "matching" if resolved else "missing",
            "Command is on PATH; it was not executed."
            if resolved
            else "Required command is absent from PATH.",
            resolved,
        )
        if resolved and name in versions:
            add(
                "version:" + name,
                "unverified",
                "Presence does not prove the declared release version; executable was not run.",
                resolved,
            )
