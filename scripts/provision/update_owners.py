"""Keep selected app updates owned by the dotfiles version manifest."""

import hashlib
import json
import os
import shlex
import tempfile
from pathlib import Path


def native_binary(home, entry):
    """Return the real artifact path without touching the filesystem."""
    return Path(home) / ".local/bin" / entry.get("managed_binary", entry["command"])


def _ordinary(home, path):
    for parent in (path, *path.parents):
        if parent == home:
            break
        if parent.is_symlink():
            raise ValueError(f"Update ownership refuses symlink: {parent}")
        if parent != path and parent.exists() and not parent.is_dir():
            raise ValueError(f"Update ownership requires directory: {parent}")
    if path.exists() and not path.is_file():
        raise ValueError(f"Update ownership requires ordinary file: {path}")


def _json(home, path):
    _ordinary(home, path)
    data = json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(data, dict):
        raise TypeError(f"Update ownership requires JSON object: {path}")
    return data


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path, content, mode):
    if path.is_file() and path.read_bytes() == content:
        if path.stat().st_mode & 0o777 != mode:
            path.chmod(mode)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix="." + path.name + ".", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
            output.flush()
            os.fchmod(output.fileno(), mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _wrapper(binary):
    return (
        "#!/bin/sh\n"
        "# Managed by dotfiles update ownership.\n"
        "export AGY_CLI_DISABLE_AUTO_UPDATE=true\n"
        f'exec {shlex.quote(str(binary.absolute()))} "$@"\n'
    ).encode()


def prepare_native_app(home, name, entry):
    """Migrate owned public natives and install a direct-exec update guard."""
    home = Path(home)
    binary = native_binary(home, entry)
    if not entry.get("managed_binary"):
        return binary
    if entry["command"] != "agy" or entry["managed_binary"] != "agy-native":
        raise ValueError("Unsupported managed native wrapper")
    public = home / ".local/bin" / entry["command"]
    _ordinary(home, public)
    _ordinary(home, binary)
    receipt = _json(home, home / ".local/state/dotfiles/agent-apps.json")
    hashes = receipt.get("native_hashes", {})
    wrappers = receipt.get("native_wrapper_hashes", {})
    if not isinstance(hashes, dict) or not isinstance(wrappers, dict):
        raise TypeError("Update ownership receipt hashes must be JSON objects")
    allowed = {entry["artifact"]["binary_sha256"], hashes.get(name)}
    content = _wrapper(binary)
    expected_wrapper = hashlib.sha256(content).hexdigest()
    if binary.exists() and _digest(binary) not in allowed:
        raise ValueError(
            f"{name} managed native integrity differs; existing binary retained"
        )
    if public.exists():
        digest = _digest(public)
        if digest not in {expected_wrapper, wrappers.get(name)}:
            if digest not in allowed:
                raise ValueError(
                    f"{name} native or wrapper integrity differs; existing command retained"
                )
            if binary.exists():
                if digest != _digest(binary):
                    raise ValueError(
                        f"{name} native migration conflicts; both files retained"
                    )
            else:
                # Copy first so a failed wrapper write always leaves a usable native.
                _write(binary, public.read_bytes(), public.stat().st_mode & 0o777)
    _write(public, content, 0o755)
    return binary


def wrapper_hashes(home, selected):
    """Report only verified generated wrappers for the app receipt."""
    result = {}
    home = Path(home)
    for name, entry in selected.items():
        if not entry.get("managed_binary"):
            continue
        public = home / ".local/bin" / entry["command"]
        _ordinary(home, public)
        if not public.is_file() or public.read_bytes() != _wrapper(
            native_binary(home, entry)
        ):
            raise ValueError(f"{name} wrapper integrity differs")
        result[name] = _digest(public)
    return result


def configure_update_owners(home, selected):
    """Merge documented update controls, retaining unrelated user settings."""
    home = Path(home)
    pending = []
    for name, entry in selected.items():
        if entry.get("update_owner") != "dotfiles":
            continue
        if name == "claude":
            # https://code.claude.com/docs/en/setup#disable-auto-updates
            path = home / ".claude/settings.json"
            data = _json(home, path)
            env = data.setdefault("env", {})
            if not isinstance(env, dict):
                raise TypeError("Claude settings env must be a JSON object")
            env["DISABLE_AUTOUPDATER"] = "1"
        elif name == "opencode":
            # https://opencode.ai/docs/config#autoupdate
            path = home / ".config/opencode/opencode.json"
            jsonc = path.with_suffix(".jsonc")
            if jsonc.exists() or jsonc.is_symlink():
                raise ValueError(
                    "OpenCode JSONC configuration requires manual reconciliation"
                )
            data = _json(home, path)
            data["autoupdate"] = False
        else:
            continue
        pending.append((path, (json.dumps(data, indent=2) + "\n").encode()))
    # Validate all configurations before writing any of them.
    for path, content in pending:
        mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
        _write(path, content, mode)
