"""Selected app acquisition and conflict-safe adapters for versioned skills."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

from provision.memory_runtime import configure_memory
from provision.rtk_setup import configure_rtk
from provision.runtime_skills import configure_runtime_skills
from provision.shared_skills import activate_shared_skills
from provision.skill_adapters import activate_tstack, register_superpowers
from provision.tool_bundle import (
    download,
    install_binary,
    require_supported_host,
    run,
    stage_skills,
)

ROOT = Path(__file__).resolve().parents[2]


def app_version(home, command):
    path = home / ".local/bin" / command
    if not path.exists():
        return None
    try:
        result = subprocess.run(
            [str(path), "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode:
        return None
    return result.stdout.strip()


def install_app(home, name, entry):
    binary = home / ".local/bin" / entry["command"]
    native_matches = True
    if entry["kind"] in {"native", "claude-native"}:
        native_matches = False
        if binary.is_file():
            digest = hashlib.sha256(binary.read_bytes()).hexdigest()
            native_matches = digest == entry["artifact"]["binary_sha256"]
            receipt = home / ".local/state/dotfiles/agent-apps.json"
            old_hash = (
                json.loads(receipt.read_text()).get("native_hashes", {}).get(name)
                if receipt.is_file()
                else None
            )
            if not native_matches and digest != old_hash:
                raise ValueError(
                    f"{name} native integrity differs from the lock; existing binary retained for review"
                )
    current = app_version(home, entry["command"])
    if current and entry["version"] in current.split() and native_matches:
        return
    if current:
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", current)
        if match and tuple(map(int, match.groups())) > tuple(
            map(int, entry["version"].split("."))
        ):
            raise ValueError(
                f"{name} is newer than the lock; update the lock instead of downgrading automatically"
            )
    if entry["kind"] == "npm":
        command = [
            "npm",
            "install",
            "--global",
            "--prefix",
            str(home / ".local"),
            "--no-audit",
            "--no-fund",
        ]
        if not entry.get("allow_install_scripts", False):
            command.append("--ignore-scripts")
        run([*command, entry["package"] + "@" + entry["version"]])
    elif entry["kind"] == "claude-native":
        payload = download(entry["artifact"])
        with tempfile.TemporaryDirectory() as temporary:
            installer = Path(temporary) / "claude"
            installer.write_bytes(payload)
            installer.chmod(0o755)
            run([str(installer), "install", entry["version"]])
    elif entry["kind"] == "native":
        install_binary(home, entry["command"], entry["artifact"])
    else:
        raise ValueError("Unsupported app acquisition kind")
    if (
        entry["kind"] in {"native", "claude-native"}
        and hashlib.sha256(binary.read_bytes()).hexdigest()
        != entry["artifact"]["binary_sha256"]
    ):
        raise ValueError(f"{name} installation failed native integrity verification")
    actual = app_version(home, entry["command"])
    if not actual or entry["version"] not in actual.split():
        raise ValueError(f"{name} installation did not verify at the declared version")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--apps", help="comma-separated explicit app names")
    parser.add_argument(
        "--from-chezmoi",
        action="store_true",
        help="read the selected app list from local chezmoi data",
    )
    parser.add_argument("--home", type=Path, default=Path.home())
    args = parser.parse_args()
    lock = json.loads((ROOT / "config/tools.lock.json").read_text())
    if bool(args.apps) == args.from_chezmoi:
        parser.error("Use --apps or --from-chezmoi, exclusively.")
    if args.from_chezmoi:
        try:
            data = tomllib.loads(
                (args.home / ".config/chezmoi/chezmoi.toml").read_text()
            )
            names = data.get("data", {}).get("agent_apps", [])
        except (OSError, ValueError):
            parser.error("Cannot read selected apps from chezmoi TOML.")
    else:
        names = args.apps.split(",")
    if not isinstance(names, list) or any(not isinstance(name, str) for name in names):
        parser.error("Selected apps must be a list of app names.")
    if not names or len(names) != len(set(names)) or set(names) - set(lock["agents"]):
        parser.error("Select unique names from claude,codex,opencode,antigravity.")
    selected = {name: lock["agents"][name] for name in names}
    if args.dry_run:
        print(
            json.dumps(
                {"runtime_major": lock["runtime_major"], "apps": selected}, indent=2
            )
        )
        return 0
    try:
        if args.home.resolve() != Path.home().resolve():
            raise ValueError("Apply must run as the actual target user")
        require_supported_host()
        runtime = subprocess.check_output(["node", "--version"], text=True).strip()
        if not runtime.startswith("v" + str(lock["runtime_major"]) + "."):
            raise ValueError("Install the declared Node26 developer bundle first")
        os.environ["PATH"] = (
            str(args.home / ".local/bin") + ":" + os.environ.get("PATH", "")
        )
        for name, entry in selected.items():
            print("Installing/verifying " + name, flush=True)
            install_app(args.home, name, entry)
        source_lock = lock
        sources = {
            name: Path(stage_skills(args.home, name, entry))
            for name, entry in source_lock["skills"].items()
        }
        skills = activate_tstack(args.home, selected, sources["tstack"])
        shared_skills = activate_shared_skills(
            args.home, selected, sources, source_lock["skills"]
        )
        configure_runtime_skills(
            args.home, selected, source_lock["developer"]["python"]
        )
        memory = configure_memory(
            args.home,
            selected,
            sources["claude-mem"],
            source_lock["skills"]["claude-mem"],
        )
        plugins = register_superpowers(args.home, selected, sources["superpowers"])
        rtk = configure_rtk(args.home, selected)
        receipt = {
            "rtk": rtk,
            "shared_skills": shared_skills,
            "memory": memory,
            "schema_version": 1,
            "manifest_sha256": hashlib.sha256(
                (ROOT / "config/tools.lock.json").read_bytes()
            ).hexdigest(),
            "runtime": runtime,
            "apps": {
                name: app_version(args.home, entry["command"])
                for name, entry in selected.items()
            },
            "tstack_skills": skills,
            "skill_sources": {name: str(path) for name, path in sources.items()},
            "superpowers_version": json.loads(
                (sources["superpowers"] / ".claude-plugin/plugin.json").read_text()
            )["version"],
            "native_hashes": {
                name: hashlib.sha256(
                    (args.home / ".local/bin" / entry["command"]).read_bytes()
                ).hexdigest()
                for name, entry in selected.items()
                if entry["kind"] in {"native", "claude-native"}
            },
            "authentication": "separate user login required",
        }
        path = args.home / ".local/state/dotfiles/agent-apps.json"
        text = json.dumps(receipt, indent=2) + "\n"
        if not path.is_file() or path.read_text() != text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        print(
            json.dumps(
                {
                    "apps": {
                        name: app_version(args.home, entry["command"])
                        for name, entry in selected.items()
                    },
                    "tstack_skills": skills,
                    "superpowers_source": str(sources["superpowers"]),
                    "plugins": plugins,
                },
                indent=2,
            )
        )
        return 0
    except (
        OSError,
        ValueError,
        TypeError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ) as error:
        print(
            f"Agent app setup failed: {error}. Existing state retained for retry.",
            file=sys.stderr,
        )
        return 1
