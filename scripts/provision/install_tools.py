"""Install and verify selected development tools, skills and provider integrations."""

import argparse
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

from provision.agent_apps import configure_apps
from provision.host_platform import detect_host, portable_catalog, system_recipe
from provision.inventory import validate_app_dependencies
from provision.toml_compat import tomllib
from provision.tool_bundle import install_bundle, require_supported_host, user_only_mode

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


def installation_plan(catalog, names, enabled=True, user_only=False):
    developer = catalog["developer"]
    host = detect_host()
    system = system_recipe(host)
    return {
        "target": host["id"],
        "installation_mode": "user" if user_only else "system",
        "system": system if enabled and not user_only else {},
        "enabled": enabled,
        "runtime_major": catalog["runtime_major"],
        "tools": {
            **(
                {name: "distribution" for name in system["packages"]}
                if not user_only
                else {}
            ),
            **{name: entry["version"] for name, entry in developer["binaries"].items()},
            **developer["npm"],
        }
        if enabled
        else {},
        "python": developer.get("python", {}) if enabled else {},
        "apps": {name: catalog["agents"][name] for name in names},
        "skills": catalog["skills"] if enabled else {},
    }


def install_tools(
    home, catalog, catalog_path, names, upgrade_system=(), user_only=False
):
    validate_selection(catalog, names)
    if home.resolve() != Path.home().resolve():
        raise ValueError(
            "Apply must run as the actual target user; --home is for dry runs"
        )
    require_supported_host()
    os.environ["PATH"] = str(home / ".local/bin") + ":" + os.environ.get("PATH", "")
    user_only = user_only or user_only_mode(home)
    options = {"user_only": True} if user_only else {}
    receipt = install_bundle(home, catalog, catalog_path, upgrade_system, **options)
    integrations = {}
    if names:
        sources = {name: Path(path) for name, path in receipt["skill_sources"].items()}
        integrations = configure_apps(
            home, catalog, catalog_path, names, sources, **options
        )
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
        "--user-only",
        action="store_true",
        help="install per-user tools only; requires the declared Node major and existing native dependencies",
    )
    parser.add_argument(
        "--upgrade-system",
        "--upgrade-apt",
        dest="upgrade_system",
        default="",
        help="explicit comma-separated managed system packages to upgrade",
    )
    args = parser.parse_args()
    try:
        catalog = portable_catalog(json.loads(args.catalog.read_text()))
        if args.from_chezmoi:
            enabled, names = configured_selection(args.home, catalog)
        else:
            names = args.apps.split(",") if args.apps else []
            try:
                validate_selection(catalog, names)
            except ValueError as error:
                parser.error(str(error))
            enabled = True
        upgrades = [name for name in args.upgrade_system.split(",") if name]
        user_only = args.user_only or user_only_mode(args.home)
        if user_only and upgrades:
            raise ValueError("User-only installation cannot upgrade system packages")
        if upgrades and set(upgrades) - set(system_recipe()["packages"]):
            raise ValueError("Only declared system packages may be upgraded")
        if args.dry_run:
            report = installation_plan(catalog, names, enabled, user_only)
        elif not enabled:
            report = {"status": "disabled", "selected_apps": []}
        else:
            report = install_tools(
                args.home, catalog, args.catalog, names, upgrades, user_only
            )
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
