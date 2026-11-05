"""Install and verify selected development tools, skills and provider integrations."""

import argparse
import json
import os
import subprocess
import sys
import tarfile
import tomllib
from pathlib import Path

from provision.agent_apps import configure_apps
from provision.inventory import validate_app_dependencies
from provision.tool_bundle import install_bundle, require_supported_host

ROOT = Path(__file__).resolve().parents[2]


def validate_selection(catalog, names):
    if (
        not isinstance(names, list)
        or any(not isinstance(name, str) for name in names)
        or len(names) != len(set(names))
        or set(names) - set(catalog["agents"])
    ):
        raise ValueError("Select unique app names from " + ",".join(catalog["agents"]))
    validate_app_dependencies(names)
    return names


def configured_selection(home, catalog):
    data = tomllib.loads((home / ".config/chezmoi/chezmoi.toml").read_text()).get(
        "data", {}
    )
    enabled = data.get("install_developer_tools", False)
    if type(enabled) is not bool:
        raise ValueError("install_developer_tools must be boolean")
    names = validate_selection(catalog, data.get("agent_apps", []))
    enabled = enabled or bool(names)
    if enabled and data.get("install_agent_clis", False):
        raise ValueError(
            "Set install_agent_clis=false before enabling managed tools; both installers cannot own the same tools"
        )
    return enabled, names


def installation_plan(catalog, names, enabled=True):
    developer = catalog["developer"]
    return {
        "enabled": enabled,
        "runtime_major": catalog["runtime_major"],
        "tools": {
            **developer["apt"],
            **{name: entry["version"] for name, entry in developer["binaries"].items()},
            **developer["npm"],
        }
        if enabled
        else {},
        "python": developer.get("python", {}) if enabled else {},
        "apps": {name: catalog["agents"][name] for name in names},
        "skills": catalog["skills"] if enabled else {},
    }


def install_tools(home, catalog, catalog_path, names, upgrade_apt=()):
    validate_selection(catalog, names)
    if home.resolve() != Path.home().resolve():
        raise ValueError(
            "Apply must run as the actual target user; --home is for dry runs"
        )
    require_supported_host()
    os.environ["PATH"] = str(home / ".local/bin") + ":" + os.environ.get("PATH", "")
    receipt = install_bundle(home, catalog, catalog_path, upgrade_apt)
    integrations = {}
    if names:
        sources = {name: Path(path) for name, path in receipt["skill_sources"].items()}
        integrations = configure_apps(home, catalog, catalog_path, names, sources)
    return {"status": "verified", "selected_apps": names, "integrations": integrations}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--apps", default="", help="comma-separated optional AI tools; blank for none"
    )
    selection.add_argument(
        "--from-chezmoi", action="store_true", help="use local tool selections"
    )
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--catalog", type=Path, default=ROOT / "config/tools.lock.json")
    parser.add_argument(
        "--upgrade-apt",
        default="",
        help="explicit comma-separated managed apt packages to upgrade",
    )
    args = parser.parse_args()
    try:
        catalog = json.loads(args.catalog.read_text())
        if args.from_chezmoi:
            enabled, names = configured_selection(args.home, catalog)
        else:
            names = args.apps.split(",") if args.apps else []
            try:
                validate_selection(catalog, names)
            except ValueError as error:
                parser.error(str(error))
            enabled = True
        upgrades = [name for name in args.upgrade_apt.split(",") if name]
        if set(upgrades) - set(catalog["developer"]["apt"]):
            raise ValueError("Only declared apt packages may be upgraded")
        if args.dry_run:
            report = installation_plan(catalog, names, enabled)
        elif not enabled:
            report = {"status": "disabled", "selected_apps": []}
        else:
            report = install_tools(args.home, catalog, args.catalog, names, upgrades)
        print(json.dumps(report, indent=2))
        return 0
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
        tarfile.TarError,
    ) as error:
        print(
            f"Tool installation failed: {error}. Completed stages are retained for retry.",
            file=sys.stderr,
        )
        return 1
