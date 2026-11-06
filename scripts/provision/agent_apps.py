"""Selected app acquisition and conflict-safe adapters for versioned skills."""

import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from provision.memory_runtime import configure_memory
from provision.rtk_setup import configure_rtk
from provision.runtime_skills import configure_runtime_skills
from provision.shared_skills import activate_shared_skills
from provision.skill_adapters import activate_tstack, register_superpowers
from provision.tool_bundle import (
    download,
    install_binary,
    run,
)
from provision.update_owners import (
    configure_update_owners,
    native_binary,
    prepare_native_app,
    wrapper_hashes,
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
    binary = prepare_native_app(home, name, entry)
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
        install_binary(home, binary.name, entry["artifact"])
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


def configure_apps(home, lock, catalog_path, names, sources, user_only=False):
    """Install selected tools and configure their skills, plugins and runtime."""
    selected = {name: lock["agents"][name] for name in names}
    runtime = subprocess.check_output(["node", "--version"], text=True).strip()
    if not runtime.startswith("v" + str(lock["runtime_major"]) + "."):
        raise ValueError("The installed Node runtime does not match the catalog")
    os.environ["PATH"] = str(home / ".local/bin") + ":" + os.environ.get("PATH", "")
    for name, entry in selected.items():
        print("Installing/verifying " + name, flush=True)
        install_app(home, name, entry)
    configure_update_owners(home, selected)
    source_lock = lock
    skills = activate_tstack(home, selected, sources["tstack"])
    shared_skills = activate_shared_skills(
        home, selected, sources, source_lock["skills"]
    )
    configure_runtime_skills(home, selected, source_lock["developer"]["python"])
    memory = configure_memory(
        home,
        selected,
        sources["claude-mem"],
        source_lock["skills"]["claude-mem"],
        **({"user_only": True} if user_only else {}),
    )
    plugins = register_superpowers(home, selected, sources["superpowers"])
    rtk = configure_rtk(home, selected)
    receipt = {
        "rtk": rtk,
        "shared_skills": shared_skills,
        "memory": memory,
        "schema_version": 1,
        "manifest_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        "runtime": runtime,
        "apps": {
            name: app_version(home, entry["command"])
            for name, entry in selected.items()
        },
        "tstack_skills": skills,
        "skill_sources": {name: str(path) for name, path in sources.items()},
        "superpowers_version": json.loads(
            (sources["superpowers"] / ".claude-plugin/plugin.json").read_text()
        )["version"],
        "native_wrapper_hashes": wrapper_hashes(home, selected),
        "native_hashes": {
            name: hashlib.sha256(native_binary(home, entry).read_bytes()).hexdigest()
            for name, entry in selected.items()
            if entry["kind"] in {"native", "claude-native"}
        },
        "authentication": "separate user login required",
    }
    path = home / ".local/state/dotfiles/agent-apps.json"
    text = json.dumps(receipt, indent=2) + "\n"
    if not path.is_file() or path.read_text() != text:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return {"apps": receipt["apps"], "plugins": plugins}
