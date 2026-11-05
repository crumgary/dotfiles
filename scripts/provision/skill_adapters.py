"""Supported per-app registration; plugin caches are written only by each app."""

import json
import subprocess
import tempfile
from pathlib import Path

from provision.tool_bundle import tree_digest


def source_root(path, owned_root):
    path, owned_root = path.resolve(), owned_root.resolve()
    if not path.is_relative_to(owned_root):
        raise ValueError("Customization is outside the managed source vault")
    for candidate in (path, *path.parents):
        if candidate == owned_root:
            break
        receipt = candidate / ".dotfiles-source.json"
        if receipt.is_file():
            if json.loads(receipt.read_text()).get("tree") != tree_digest(candidate):
                raise ValueError(
                    "Managed source has local edits; existing links retained"
                )
            return candidate
    raise ValueError("Managed source ownership receipt is missing")


def ensure_link(destination, source, owned_root=None):
    if destination.is_symlink() and destination.resolve() == source.resolve():
        return
    if destination.is_symlink() and owned_root is not None:
        current = destination.resolve()
        previous_root = source_root(current, owned_root)
        next_root = source_root(source, owned_root)
        if current.relative_to(previous_root) != source.resolve().relative_to(
            next_root
        ):
            raise ValueError("Managed link would change its skill identity")
        with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
            replacement = Path(temporary) / "link"
            replacement.symlink_to(source, target_is_directory=source.is_dir())
            replacement.replace(destination)
        return
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"Conflicting customization at {destination}; left intact")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(source, target_is_directory=source.is_dir())


def verify_plugin_files(actual, expected):
    # Read caches for integrity only. Installation/removal remains app-owned.
    for name in (".mcp.json", "package.json", "bun.lock", "bun.lockb"):
        expected_file, actual_file = expected / name, actual / name
        if expected_file.is_file() and (
            actual_file.is_symlink()
            or not actual_file.is_file()
            or actual_file.read_bytes() != expected_file.read_bytes()
        ):
            raise ValueError(
                f"Plugin root configuration differs from its pinned source: {name}"
            )
    for area in (
        "skills",
        "scripts",
        "hooks",
        "lib",
        ".claude-plugin",
        ".codex-plugin",
        ".antigravity-plugin",
    ):
        left, right = actual / area, expected / area
        if not right.exists():
            continue
        if not left.is_dir() or tree_digest(left) != tree_digest(right):
            raise ValueError(
                f"Plugin content in {area} differs from its pinned source at {actual}; retained for review"
            )


def json_command(command):
    result = subprocess.run(
        command, text=True, capture_output=True, check=True, timeout=90
    )
    return json.loads(result.stdout)


def run(command):
    subprocess.run(command, check=True, stdin=subprocess.DEVNULL, timeout=180)


def activate_tstack(home, selected, source):
    skills = []
    if "opencode" in selected:
        shared_rules = home / ".config/agents/AGENTS.md"
        if not shared_rules.is_file():
            raise ValueError("Apply the public shared agent rules before activation")
        ensure_link(home / ".config/opencode/AGENTS.md", shared_rules)
    for directory in sorted((source / "skills").iterdir()):
        if not (directory / "SKILL.md").is_file():
            continue
        canonical = home / ".agents/skills" / directory.name
        ensure_link(
            canonical,
            directory,
            owned_root=home / ".local/share/dotfiles/skill-sources/tstack",
        )
        if "claude" in selected:
            ensure_link(home / ".claude/skills" / directory.name, canonical)
        if "antigravity" in selected:
            ensure_link(home / ".gemini/config/skills" / directory.name, canonical)
        skills.append(directory.name)
    return skills


def owned_json(path, data):
    if path.exists():
        if json.loads(path.read_text()) != data:
            raise ValueError(
                f"Customization conflict at {path}; existing content retained"
            )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def verify_existing_plugin(items, identity, identity_field, expected_version):
    matching = []
    for item in items:
        value = item.get(identity_field, "")
        name = item.get("name") or value.split("@")[0]
        if name != "superpowers":
            continue
        if value != identity:
            raise ValueError(
                "Another Superpowers registration exists; review its source before replacing it"
            )
        if item.get("enabled") is not True or item.get("version") != expected_version:
            raise ValueError(
                "Superpowers is disabled or differs from its declared version; existing registration retained"
            )
        matching.append(item)
    return bool(matching)


def previous_superpowers(home, source):
    receipt = home / ".local/state/dotfiles/agent-apps.json"
    if not receipt.is_file():
        return None
    old = json.loads(receipt.read_text()).get("skill_sources", {}).get("superpowers")
    if not old or Path(old).resolve() == source.resolve():
        return None
    previous = Path(old)
    if (
        source_root(previous, home / ".local/share/dotfiles/skill-sources/superpowers")
        != previous.resolve()
    ):
        raise ValueError("Previous Superpowers ownership record does not name its root")
    return previous


def matches_plugin_files(actual, expected):
    try:
        verify_plugin_files(actual, expected)
        return True
    except ValueError:
        return False


def register_superpowers(home, selected, source):
    results = {}
    previous = previous_superpowers(home, source)
    old_version = (
        json.loads((previous / ".claude-plugin/plugin.json").read_text())["version"]
        if previous
        else None
    )
    version = json.loads((source / ".claude-plugin/plugin.json").read_text())["version"]
    if "claude" in selected:
        installed = json_command(
            [str(home / ".local/bin/claude"), "plugin", "list", "--json"]
        )
        existing = next(
            (
                item
                for item in installed
                if item.get("id") == "superpowers@superpowers-dev"
            ),
            None,
        )
        if (
            previous
            and existing
            and (
                Path(existing.get("readFromFolder", "")).resolve() != source.resolve()
                or not matches_plugin_files(Path(existing["installPath"]), source)
            )
        ):
            verify_existing_plugin(
                installed, "superpowers@superpowers-dev", "id", old_version
            )
            if Path(existing.get("readFromFolder", "")).resolve() != previous.resolve():
                raise ValueError(
                    "Claude plugin is not from the previous managed source"
                )
            verify_plugin_files(Path(existing["installPath"]), previous)
            run(
                [
                    str(home / ".local/bin/claude"),
                    "plugin",
                    "uninstall",
                    "superpowers@superpowers-dev",
                    "--scope",
                    "user",
                ]
            )
            run(
                [
                    str(home / ".local/bin/claude"),
                    "plugin",
                    "marketplace",
                    "remove",
                    "superpowers-dev",
                ]
            )
            installed = []
        if not verify_existing_plugin(
            installed, "superpowers@superpowers-dev", "id", version
        ):
            run(
                [
                    str(home / ".local/bin/claude"),
                    "plugin",
                    "marketplace",
                    "add",
                    str(source),
                ]
            )
            run(
                [
                    str(home / ".local/bin/claude"),
                    "plugin",
                    "install",
                    "superpowers@superpowers-dev",
                    "--scope",
                    "user",
                ]
            )
        results["claude"] = json_command(
            [str(home / ".local/bin/claude"), "plugin", "list", "--json"]
        )
        plugin = next(
            item
            for item in results["claude"]
            if item.get("id") == "superpowers@superpowers-dev"
        )
        if Path(plugin.get("readFromFolder", "")).resolve() != source.resolve():
            raise ValueError("Claude plugin source differs from the pinned collection")
        verify_plugin_files(Path(plugin["installPath"]), source)
    if "codex" in selected:
        root = home / ".local/share/dotfiles/marketplaces/agent-skills"
        registered_marketplace = False
        if previous:
            earlier = json_command(
                [str(home / ".local/bin/codex"), "plugin", "list", "--json"]
            )
            item = next(
                (
                    item
                    for item in earlier.get("installed", [])
                    if item.get("pluginId") == "superpowers@dotfiles-agent-skills"
                ),
                None,
            )
            if item:
                registered_marketplace = True
                cache = (
                    home
                    / ".codex/plugins/cache/dotfiles-agent-skills/superpowers"
                    / item["version"]
                )
                if not matches_plugin_files(cache, source):
                    verify_existing_plugin(
                        earlier["installed"],
                        "superpowers@dotfiles-agent-skills",
                        "pluginId",
                        old_version,
                    )
                    verify_plugin_files(cache, previous)
                    run(
                        [
                            str(home / ".local/bin/codex"),
                            "plugin",
                            "remove",
                            "superpowers@dotfiles-agent-skills",
                        ]
                    )
        ensure_link(
            root / "superpowers",
            source,
            owned_root=home / ".local/share/dotfiles/skill-sources/superpowers",
        )
        owned_json(
            root / ".agents/plugins/marketplace.json",
            {
                "name": "dotfiles-agent-skills",
                "interface": {"displayName": "Dotfiles agent skills"},
                "plugins": [
                    {
                        "name": "superpowers",
                        "source": {"source": "local", "path": "./superpowers"},
                        "policy": {
                            "installation": "AVAILABLE",
                            "authentication": "ON_INSTALL",
                        },
                        "category": "Developer Tools",
                    }
                ],
            },
        )
        installed = json_command(
            [str(home / ".local/bin/codex"), "plugin", "list", "--json"]
        )
        if not verify_existing_plugin(
            installed.get("installed", []),
            "superpowers@dotfiles-agent-skills",
            "pluginId",
            version,
        ):
            if not registered_marketplace:
                run(
                    [
                        str(home / ".local/bin/codex"),
                        "plugin",
                        "marketplace",
                        "add",
                        str(root),
                        "--json",
                    ]
                )
            run(
                [
                    str(home / ".local/bin/codex"),
                    "plugin",
                    "add",
                    "superpowers@dotfiles-agent-skills",
                    "--json",
                ]
            )
        results["codex"] = json_command(
            [str(home / ".local/bin/codex"), "plugin", "list", "--json"]
        )
        plugin = next(
            item
            for item in results["codex"]["installed"]
            if item.get("pluginId") == "superpowers@dotfiles-agent-skills"
        )
        if Path(plugin.get("source", {}).get("path", "")).resolve() != source.resolve():
            raise ValueError("Codex plugin source differs from the pinned collection")
        verify_plugin_files(
            home / ".codex/plugins/cache/dotfiles-agent-skills/superpowers" / version,
            source,
        )
    if "antigravity" in selected:
        installed = json_command(
            [str(home / ".local/bin/agy"), "plugin", "list", "--json"]
        )
        existing = next(
            (item for item in installed if item.get("name") == "superpowers"), None
        )
        if (
            previous
            and existing
            and not matches_plugin_files(Path(existing["path"]), source)
        ):
            verify_existing_plugin(installed, "superpowers", "name", old_version)
            verify_plugin_files(Path(existing["path"]), previous)
            run([str(home / ".local/bin/agy"), "plugin", "uninstall", "superpowers"])
            installed = []
        if not verify_existing_plugin(installed, "superpowers", "name", version):
            run([str(home / ".local/bin/agy"), "plugin", "install", str(source)])
        results["antigravity"] = json_command(
            [str(home / ".local/bin/agy"), "plugin", "list", "--json"]
        )
        plugin = next(
            item for item in results["antigravity"] if item.get("name") == "superpowers"
        )
        verify_plugin_files(Path(plugin["path"]), source)
    if "opencode" in selected:
        path = home / ".config/opencode/opencode.json"
        if path.is_symlink():
            raise ValueError(
                "Symlinked OpenCode configuration requires owner review; left intact"
            )
        if path.with_suffix(".jsonc").exists():
            raise ValueError(
                "Existing OpenCode JSONC configuration requires review before merging"
            )
        data = json.loads(path.read_text()) if path.exists() else {}
        plugins = data.get("plugin", [])
        if not isinstance(plugins, list) or any(
            not isinstance(item, str) for item in plugins
        ):
            raise ValueError(
                "OpenCode plugin declaration is not a list of package paths"
            )
        desired = str(source)
        if desired not in plugins:
            if previous and str(previous) in plugins:
                plugins = [
                    desired if item == str(previous) else item for item in plugins
                ]
                data["plugin"] = plugins
                path.write_text(json.dumps(data, indent=2) + "\n")
            if any("superpowers" in item and item != desired for item in plugins):
                raise ValueError(
                    "Another OpenCode Superpowers source is configured; left intact"
                )
            data["plugin"] = plugins if desired in plugins else [*plugins, desired]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2) + "\n")
        results["opencode"] = {
            "plugin": desired,
            "discovery_check": "opencode debug skill",
        }
    return results
