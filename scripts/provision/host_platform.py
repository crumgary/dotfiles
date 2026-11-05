"""Resolve host-native package recipes separately from portable tool releases."""

import copy
import platform
from pathlib import Path

from provision.toml_compat import tomllib

ROOT = Path(__file__).resolve().parents[2]


def recipes(source=ROOT):
    return tomllib.loads(
        (Path(source) / "home/.chezmoidata/packages.toml").read_text()
    )["managed"]


def detect_host(release=Path("/etc/os-release"), architecture=None):
    values = {}
    for line in Path(release).read_text().splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value.strip().strip("\"'")
    distro, version = values.get("ID"), values.get("VERSION_ID", "")
    architecture = architecture or platform.machine()
    normalized = version.split(".")[0] if distro == "almalinux" else version
    definitions = recipes()
    if (
        architecture != "x86_64"
        or distro not in definitions
        or normalized not in definitions[distro]["releases"]
    ):
        raise ValueError(
            "Supported targets are Ubuntu 22.04/24.04/26.04 and AlmaLinux 9 on x86_64"
        )
    return {
        "os": distro,
        "release": normalized,
        "architecture": architecture,
        "id": f"{distro}-{normalized}-{architecture}",
    }


def system_recipe(host=None, source=ROOT):
    host = host or detect_host()
    definition = copy.deepcopy(recipes(source)[host["os"]])
    if (
        host["release"] not in definition["releases"]
        or host["architecture"] != "x86_64"
    ):
        raise ValueError("Unsupported host package recipe")
    definition["dependencies"] = definition.pop("browser_dependencies", {}).get(
        host["release"], []
    )
    return definition


def package_ids(source=ROOT):
    return set().union(
        *(set(recipe["packages"]) for recipe in recipes(source).values())
    )


def portable_catalog(catalog):
    """Migrate the original Ubuntu-specific catalog without changing tool pins."""
    result = copy.deepcopy(catalog)
    if result.get("schema_version", 2) == 1:
        result["schema_version"] = 2
        result["platform"] = "linux-x86_64"
        result["developer"].pop("apt", None)
        result["developer"].pop("repositories", None)
    elif result.get("schema_version", 2) != 2:
        raise ValueError("Unsupported tool catalog schema")
    return result
