"""Validate versioned machine selections and preview existing chezmoi selections."""

import json
import re
import tomllib
from pathlib import Path

PROFILES = {"wsl", "devbox", "lab", "embedded"}
OVERLAYS = {"personal": ".config/dotfiles-priv", "work": ".config/dotfiles-work"}
FIELDS = {
    "schema_version",
    "id",
    "owner",
    "profile",
    "os",
    "architecture",
    "overlays",
    "bundles",
    "apps",
    "revisions",
    "work",
}


class InputError(ValueError):
    """An invalid input whose message contains no input contents."""


def read_toml(path):
    try:
        with Path(path).open("rb") as stream:
            return tomllib.load(stream)
    except (OSError, ValueError):
        raise InputError(
            "Cannot read valid TOML; check the input file and permissions."
        ) from None


def validate_app_dependencies(names):
    if "opencode" in names and "claude" not in names:
        raise InputError(
            "OpenCode RTK integration currently requires selecting Claude too."
        )


def validate(record):
    if not isinstance(record, dict) or set(record) - FIELDS:
        raise InputError("Machine record contains unknown fields.")
    if type(record.get("schema_version")) is not int or record["schema_version"] != 1:
        raise InputError("Expected schema_version = 1.")
    if not isinstance(record.get("id"), str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9-]{0,62}", record["id"]
    ):
        raise InputError(
            "Machine id must be 1-63 lowercase letters, digits or hyphens."
        )
    for field, allowed in [
        ("owner", {"local", "personal", "work"}),
        ("profile", PROFILES),
        ("os", {"ubuntu"}),
        ("architecture", {"x86_64"}),
    ]:
        if not isinstance(record.get(field), str) or record[field] not in allowed:
            raise InputError(f"Invalid or unsupported {field}.")
    for field, allowed in [
        ("overlays", set(OVERLAYS)),
        ("bundles", {"coding", "developer"}),
    ]:
        values = record.get(field)
        if (
            not isinstance(values, list)
            or any(not isinstance(v, str) for v in values)
            or len(values) != len(set(values))
            or set(values) - allowed
        ):
            raise InputError(f"Invalid or duplicated {field}.")
    if record["owner"] != "local" and record["owner"] not in record["overlays"]:
        raise InputError("Inventory owner must be an enabled overlay.")
    work = record.get("work", "work" in record["overlays"])
    if type(work) is not bool or ("work" in record["overlays"] and not work):
        raise InputError("Work overlay requires work = true.")
    if record["profile"] == "embedded" and record["bundles"]:
        raise InputError("Embedded profile cannot enable developer or coding bundles.")
    apps = record.get("apps", [])
    if (
        not isinstance(apps, list)
        or any(not isinstance(app, str) for app in apps)
        or len(apps) != len(set(apps))
        or set(apps) - {"claude", "codex", "opencode", "antigravity"}
    ):
        raise InputError("Invalid or duplicated app selection.")
    validate_app_dependencies(apps)
    if apps and "developer" not in record["bundles"]:
        raise InputError("Selected apps require the developer runtime bundle.")
    revisions = record.get("revisions", {})
    if not isinstance(revisions, dict) or set(revisions) - {
        "public",
        *record["overlays"],
    }:
        raise InputError("Revisions may name only public and enabled overlays.")
    if any(
        not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", v)
        for v in revisions.values()
    ):
        raise InputError("Revisions must be full immutable Git commit IDs.")
    return {**record, "work": work, "revisions": revisions, "apps": apps}


def load_record(path):
    return validate(read_toml(path))


def current_data(home):
    data = read_toml(home / ".config/chezmoi/chezmoi.toml").get("data")
    if not isinstance(data, dict):
        raise InputError("Existing chezmoi configuration needs a data table.")
    return data


def import_current(home, machine_id, owner):
    data = current_data(home)
    for field in (
        "work",
        "bootstrap_priv_overlay",
        "bootstrap_work_overlay",
        "install_agent_clis",
    ):
        if type(data.get(field)) is not bool:
            raise InputError(
                "Existing chezmoi selections are incomplete; review boolean selections first."
            )
    if (
        "install_developer_tools" in data
        and type(data["install_developer_tools"]) is not bool
    ):
        raise InputError("Developer-tool selection must be boolean.")
    record = validate(
        {
            "schema_version": 1,
            "id": machine_id,
            "owner": owner,
            "profile": data.get("profile"),
            "apps": data.get("agent_apps", []),
            "os": "ubuntu",
            "architecture": "x86_64",
            "work": data["work"],
            "overlays": [
                name
                for name, key in [
                    ("personal", "bootstrap_priv_overlay"),
                    ("work", "bootstrap_work_overlay"),
                ]
                if data[key]
            ],
            "bundles": (["coding"] if data["install_agent_clis"] else [])
            + (
                ["developer"]
                if data.get("install_developer_tools", False) or data.get("agent_apps")
                else []
            ),
        }
    )
    # Emit only allowlisted selections, never identities, URLs or credentials.
    lines = ["# Preview only. Review platform, selections and owner before saving."]
    for key in (
        "schema_version",
        "id",
        "owner",
        "profile",
        "os",
        "architecture",
        "work",
        "overlays",
        "bundles",
        "apps",
    ):
        lines.append(f"{key} = {json.dumps(record[key])}")
    return "\n".join(lines) + "\n"
