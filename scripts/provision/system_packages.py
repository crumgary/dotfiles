"""Install native system packages using pinned repository trust and host policy."""

import configparser
import hashlib
import re
import subprocess
from pathlib import Path

from provision.tool_bundle import download, run, write_system


def repository_files(recipe, node_major):
    result = []
    for name, entry in recipe["repositories"].items():
        uri = entry["uri"].format(node_major=node_major)
        if recipe["manager"] == "apt":
            key = Path("/etc/apt/keyrings") / f"dotfiles-{name}.{entry['format']}"
            path = Path("/etc/apt/sources.list.d") / f"dotfiles-{name}.sources"
            content = (
                f"Types: deb\nURIs: {uri}\nSuites: {entry.get('suite', 'stable')}\n"
                f"Components: main\nArchitectures: amd64\nSigned-By: {key}\n"
            )
        else:
            key = Path("/etc/pki/rpm-gpg") / f"RPM-GPG-KEY-dotfiles-{name}.asc"
            path = Path("/etc/yum.repos.d") / f"dotfiles-{name}.repo"
            content = (
                f"[dotfiles-{name}]\nname=Managed {name}\nbaseurl={uri}\n"
                f"enabled=1\ngpgcheck=1\ngpgkey=file://{key}\n"
            )
            content += f"repo_gpgcheck={int(entry.get('repo_gpgcheck', False))}\n"
            if entry.get("module_hotfixes"):
                content += "module_hotfixes=1\npriority=9\n"
        result.append((path, content, key, entry))
    return result


def installed_version(manager, package):
    if manager == "apt":
        command = ["dpkg-query", "-W", "-f=${db:Status-Status}|${Version}", package]
    else:
        command = ["rpm", "-q", "--qf", "%{VERSION}-%{RELEASE}", package]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode:
        return None
    if manager == "apt":
        return (
            result.stdout.partition("|")[2]
            if result.stdout.startswith("installed|")
            else None
        )
    return result.stdout.strip()


def validate_node(version, major):
    if not version:
        return False
    match = re.match(r"(?:\d+:)?(\d+)\.", version)
    if not match or int(match[1]) > major:
        raise ValueError(
            "System Node is outside the chosen major; automatic downgrade is disabled"
        )
    return int(match[1]) == major


def install_system(recipe, node_major, upgrade=()):
    manager = recipe["manager"]
    packages = recipe["packages"]
    if set(upgrade) - set(packages):
        raise ValueError("Unknown system package upgrade selection")
    versions = {
        name: installed_version(manager, entry["name"])
        for name, entry in packages.items()
    }
    node_ready = (
        validate_node(versions.get("nodejs"), node_major)
        if "nodejs" in packages
        else True
    )
    required = [
        name
        for name, version in versions.items()
        if not version or name == "nodejs" and not node_ready
    ]
    dependencies = recipe.get("dependencies", [])
    missing_dependencies = [
        name for name in dependencies if not installed_version(manager, name)
    ]
    prerequisites = recipe.get("prerequisites", {})
    if manager == "dnf":
        missing = [
            name
            for name in prerequisites.get("packages", [])
            if not installed_version(manager, name)
        ]
        if missing:
            run(["sudo", "-n", "dnf", "install", "-y", *missing])
        configuration = configparser.ConfigParser(strict=False)
        configuration.read(sorted(Path("/etc/yum.repos.d").glob("*.repo")))
        for repository in prerequisites.get("repositories", []):
            if not configuration.getboolean(repository, "enabled", fallback=False):
                run(
                    ["sudo", "-n", "dnf", "config-manager", "--set-enabled", repository]
                )
    changed = False
    adopted = set()
    for path, content, key, entry in repository_files(recipe, node_major):
        key_changed = False
        if (
            not key.is_file()
            or hashlib.sha256(key.read_bytes()).hexdigest() != entry["key_sha256"]
        ):
            key_changed = write_system(
                key, download({"url": entry["key_url"], "sha256": entry["key_sha256"]})
            )
        repository_changed = write_system(path, content.encode()) or key_changed
        changed |= repository_changed
        if repository_changed:
            repository = path.stem.removeprefix("dotfiles-")
            adopted.update(
                name
                for name, package in packages.items()
                if package.get("repository") == repository
            )
    upgrade = set(upgrade) | adopted
    if manager == "apt":
        if required or upgrade or changed or missing_dependencies:
            run(["sudo", "-n", "apt-get", "update", "-qq"])
        selected = sorted(set(required) | set(upgrade))
        if selected or missing_dependencies:
            run(
                [
                    "sudo",
                    "-n",
                    "env",
                    "DEBIAN_FRONTEND=noninteractive",
                    "apt-get",
                    "install",
                    "-y",
                    "--no-remove",
                    *(packages[name]["name"] for name in selected),
                    *missing_dependencies,
                ]
            )
    else:
        if changed:
            run(["sudo", "-n", "dnf", "makecache", "--refresh", "-y"])
        if required:
            run(
                [
                    "sudo",
                    "-n",
                    "dnf",
                    "install",
                    "-y",
                    *(packages[name]["name"] for name in required),
                ]
            )
        if upgrade:
            run(
                [
                    "sudo",
                    "-n",
                    "dnf",
                    "upgrade",
                    "-y",
                    *(packages[name]["name"] for name in sorted(upgrade)),
                ]
            )
    actual = {
        name: installed_version(manager, entry["name"])
        for name, entry in packages.items()
    }
    dependencies_ready = all(installed_version(manager, name) for name in dependencies)
    if (
        not dependencies_ready
        or not all(actual.values())
        or (
            "nodejs" in packages and not validate_node(actual.get("nodejs"), node_major)
        )
    ):
        raise ValueError(
            "System package installation did not satisfy the selected target"
        )
    return actual
