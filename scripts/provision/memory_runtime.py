"""Pinned claude-mem native integrations and a supervised, fresh local worker."""

import getpass
import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from provision.skill_adapters import source_root, verify_plugin_files
from provision.tool_bundle import download, verify_payload


def run(command, env=None):
    return subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=600,
        env=env,
    )


def read_config(path):
    if path.is_symlink():
        raise ValueError(f"Symlinked configuration retained: {path}")
    value = json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")  # noqa: TRY004 - invalid config is a provisioning error
    return value


def write_file(path, data, mode=0o644):
    if path.is_symlink():
        raise ValueError(f"Symlinked managed file retained: {path}")
    if path.exists() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        staged = Path(temporary.name)
        try:
            temporary.write(data)
            temporary.flush()
            staged.chmod(mode)
            staged.replace(path)
        finally:
            staged.unlink(missing_ok=True)
    return True


def version_key(value):
    try:
        return tuple(int(part) for part in value.lstrip("v").split("."))
    except (AttributeError, ValueError) as error:
        raise ValueError("Expected a stable numeric memory runtime version") from error


def previous_memory(home, entry):
    """Ownership requires the activation receipt and an unedited immutable source."""
    receipt = read_config(home / ".local/state/dotfiles/agent-apps.json").get("memory")
    if receipt is None:
        return None
    required = {"version", "source", "runtime", "integrations", "health"}
    if not isinstance(receipt, dict) or not required.issubset(receipt):
        raise ValueError("Previous memory ownership receipt is incomplete")
    previous = Path(receipt["source"])
    if (
        source_root(previous, home / ".local/share/dotfiles/skill-sources/claude-mem")
        != previous.resolve()
    ):
        raise ValueError("Previous memory source receipt does not name its root")
    actual_version = json.loads((previous / "plugin/package.json").read_text())[
        "version"
    ]
    if (
        actual_version != receipt["version"]
        or receipt["health"].get("version") != actual_version
        or receipt["health"].get("status") != "ok"
    ):
        raise ValueError("Previous memory ownership version is inconsistent")
    if version_key(entry["version"]) < version_key(actual_version):
        raise ValueError("Memory downgrades are not supported")
    if not isinstance(receipt["integrations"], dict):
        raise TypeError("Previous memory integrations receipt is invalid")
    runtime = Path(receipt["runtime"])
    allowed = [
        Path(item["path"])
        for key, item in receipt["integrations"].items()
        if key in {"claude", "codex"} and isinstance(item, dict) and "path" in item
    ]
    allowed.append(home / ".local/share/dotfiles/memory-runtime" / previous.name)
    if runtime not in allowed:
        raise ValueError("Previous memory runtime is outside its owned integrations")
    # Legacy activation receipts predate Bun hashes. Bootstrap only from the
    # unchanged baseline catalog and its exact source artifact identity.
    if not receipt.get("bun_sha256"):
        baseline = json.loads(
            (Path(__file__).resolve().parents[2] / "config/tools.lock.json").read_text()
        )["skills"]["claude-mem"]
        source_receipt = read_config(previous / ".dotfiles-source.json")
        if (
            baseline["version"] != actual_version
            or baseline["revision"] != previous.name
            or baseline["sha256"] != source_receipt.get("sha256")
        ):
            raise ValueError(
                "Legacy Bun ownership cannot be proven from the baseline catalog"
            )
        receipt = {
            **receipt,
            "bun_sha256": baseline["bun"]["binary_sha256"],
            "bun_version": baseline["bun"]["version"],
        }
    if receipt.get("bun_version") and version_key(
        entry["bun"]["version"]
    ) < version_key(receipt["bun_version"]):
        raise ValueError("Bun downgrades are not supported")
    return receipt


def install_bun(home, entry, previous=None):
    target = home / ".local/bin/bun"
    if target.is_symlink():
        raise ValueError("Existing Bun symlink retained for review")
    if target.is_file():
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest == entry["binary_sha256"]:
            return target
        if previous is None or digest != previous.get("bun_sha256"):
            raise ValueError(
                "Existing Bun differs from the pinned binary; retained for review"
            )
    with zipfile.ZipFile(io.BytesIO(download(entry))) as archive:
        payload = verify_payload(archive.read(entry["member"]), entry["binary_sha256"])
    write_file(target, payload, 0o755)
    return target


def native_plugins(home, selected, source, version, previous=None):
    """Verify ownership before asking each native CLI to replace its plugin."""
    roots, result = [], {}
    for app, identity, field, marketplace in (
        ("claude", "claude-mem@thedotmack", "id", "thedotmack"),
        ("codex", "claude-mem@claude-mem-local", "pluginId", "claude-mem-local"),
    ):
        if app not in selected:
            continue
        cli = str(home / ".local/bin" / app)

        def installed_plugins(cli=cli, app=app):
            value = json.loads(run([cli, "plugin", "list", "--json"]).stdout)
            return value if app == "claude" else value["installed"]

        installed = installed_plugins()
        matches = [
            item
            for item in installed
            if item.get(field, "").split("@")[0] == "claude-mem"
        ]
        if len(matches) > 1:
            raise ValueError("Multiple memory registrations retained for review")
        if matches:
            item = matches[0]
            if item.get(field) != identity or item.get("enabled") is not True:
                raise ValueError(
                    f"Existing {app} memory plugin is foreign or disabled; retained"
                )
            registered_source = Path(
                item.get("readFromFolder", "")
                if app == "claude"
                else item.get("source", {}).get("path", "")
            )
            cache = (
                Path(item.get("installPath", ""))
                if app == "claude"
                else home
                / ".codex/plugins/cache/claude-mem-local/claude-mem"
                / item["version"]
            )
            current = (
                item.get("version") == version
                and registered_source.resolve() == (source / "plugin").resolve()
            )
            if current:
                verify_plugin_files(cache, source / "plugin")
            else:
                owned = (previous or {}).get("integrations", {}).get(app, {})
                if (
                    not previous
                    or owned.get("plugin") != identity
                    or owned.get("path") != str(cache)
                    or item.get("version") != previous["version"]
                    or registered_source.resolve()
                    != (Path(previous["source"]) / "plugin").resolve()
                ):
                    raise ValueError(
                        f"Existing {app} memory plugin differs from its ownership receipt; retained"
                    )
                verify_plugin_files(cache, Path(previous["source"]) / "plugin")
                if app == "claude":
                    run([cli, "plugin", "uninstall", identity, "--scope", "user"])
                else:
                    run([cli, "plugin", "remove", identity, "--json"])
                run([cli, "plugin", "marketplace", "remove", marketplace])
                matches = []
        if not matches:
            run(
                [
                    cli,
                    "plugin",
                    "marketplace",
                    "add",
                    str(source),
                    *(["--json"] if app == "codex" else []),
                ]
            )
            run(
                [
                    cli,
                    "plugin",
                    "install" if app == "claude" else "add",
                    identity,
                    *(["--scope", "user"] if app == "claude" else ["--json"]),
                ]
            )
            installed = installed_plugins()
        item = next(item for item in installed if item.get(field) == identity)
        registered_source = Path(
            item.get("readFromFolder", "")
            if app == "claude"
            else item.get("source", {}).get("path", "")
        )
        if (
            item.get("version") != version
            or item.get("enabled") is not True
            or registered_source.resolve() != (source / "plugin").resolve()
        ):
            raise ValueError(f"{app} memory plugin is not the managed pinned source")
        cache = (
            Path(item["installPath"])
            if app == "claude"
            else home / ".codex/plugins/cache/claude-mem-local/claude-mem" / version
        )
        verify_plugin_files(cache, source / "plugin")
        roots.append(cache)
        result[app] = {"plugin": identity, "path": str(cache)}
    return roots, result


def configure_opencode(home, source, runtime, previous=None):
    path = home / ".config/opencode/opencode.json"
    if path.with_suffix(".jsonc").exists():
        raise ValueError("Existing OpenCode JSONC retained for review")
    data = read_config(path)
    plugins = data.get("plugin", [])
    if not isinstance(plugins, list) or any(
        not isinstance(item, str) for item in plugins
    ):
        raise ValueError("OpenCode plugins must be a list of strings")
    desired_plugin = "./plugins/claude-mem.js"
    if any("claude-mem" in item and item != desired_plugin for item in plugins):
        raise ValueError("Another OpenCode memory integration is already configured")
    desired_mcp = {
        "type": "local",
        "command": [shutil.which("node"), str(runtime / "scripts/mcp-server.cjs")],
    }
    mcp = data.get("mcp", {})
    if not isinstance(mcp, dict) or (
        "claude-mem" in mcp
        and mcp["claude-mem"] != desired_mcp
        and mcp["claude-mem"]
        != (previous or {}).get("integrations", {}).get("opencode", {}).get("mcp")
    ):
        raise ValueError(
            "Existing OpenCode memory MCP configuration retained for review"
        )
    bundle = (source / "dist/opencode-plugin/index.js").read_bytes()
    destination = home / ".config/opencode/plugins/claude-mem.js"
    old_bundle = None
    if previous and previous.get("integrations", {}).get("opencode", {}).get(
        "plugin"
    ) == str(destination):
        old_bundle = (
            Path(previous["source"]) / "dist/opencode-plugin/index.js"
        ).read_bytes()
    if destination.exists() and destination.read_bytes() not in (bundle, old_bundle):
        raise ValueError(
            "Existing OpenCode memory plugin has local differences; retained"
        )
    write_file(destination, bundle)
    data["plugin"] = (
        plugins if desired_plugin in plugins else [*plugins, desired_plugin]
    )
    data["mcp"] = {**mcp, "claude-mem": desired_mcp}
    write_file(path, (json.dumps(data, indent=2) + "\n").encode())
    return {"plugin": str(destination), "mcp": desired_mcp}


def write_system_owned(path, content):
    """Create an exact managed system file, preserving existing customizations."""
    if path.is_symlink():
        raise ValueError(f"Symlinked system customization retained: {path}")
    if path.exists():
        if path.read_text() != content:
            raise ValueError(f"Existing system customization retained: {path}")
        return False
    with tempfile.NamedTemporaryFile() as temporary:
        temporary.write(content.encode())
        temporary.flush()
        run(["sudo", "-n", "install", "-D", "-m", "0644", temporary.name, str(path)])
    return True


def wsl_interop_unit():
    return (
        "# Managed by dotfiles memory_runtime.py\n"
        "[Unit]\nDescription=Restore missing WSL Windows interop registration\n"
        "ConditionVirtualization=wsl\nAfter=systemd-binfmt.service\n"
        "After=proc-sys-fs-binfmt_misc.mount\nBefore=systemd-user-sessions.service\n"
        "[Service]\nType=oneshot\nRemainAfterExit=yes\n"
        'ExecStart=/bin/sh -c "if [ ! -e /proc/sys/fs/binfmt_misc/WSLInterop ]; then '
        "echo ':WSLInterop:M::MZ::/init:PF' > /proc/sys/fs/binfmt_misc/register; fi\"\n"
        "[Install]\nWantedBy=multi-user.target\n"
    )


def protect_wsl_interop():
    if not os.environ.get("WSL_DISTRO_NAME"):
        return
    # Canonical's documented workaround for shared WSL binfmt registration loss:
    # https://ubuntu.com/wsl/docs/stable/explanation/binfmt/
    path = Path("/etc/systemd/system/systemd-binfmt.service.d/90-dotfiles-wsl.conf")
    content = "# Managed by dotfiles memory_runtime.py\n[Unit]\nConditionVirtualization=!wsl\n"
    changed = write_system_owned(path, content)
    # Disabling systemd-binfmt also skips WSL's generated ExecStart that normally
    # restores its handler. Restore only a missing handler on every boot, never
    # unregistering the mappings shared with other distributions.
    changed |= write_system_owned(
        Path("/etc/systemd/system/dotfiles-wsl-interop.service"), wsl_interop_unit()
    )
    if changed:
        run(["sudo", "-n", "systemctl", "daemon-reload"])
    run(["sudo", "-n", "systemctl", "enable", "--now", "dotfiles-wsl-interop.service"])
    # Also recover if another distribution removed the mapping after this unit ran.
    if not Path("/proc/sys/fs/binfmt_misc/WSLInterop").exists():
        run(["sudo", "-n", "systemctl", "restart", "dotfiles-wsl-interop.service"])


def configure_port(home):
    """Choose a distro-specific default because WSL also shares loopback ports."""
    path = home / ".claude-mem/settings.json"
    settings = read_config(path)
    distro = os.environ.get("WSL_DISTRO_NAME")
    current = settings.get("CLAUDE_MEM_WORKER_PORT")
    if distro and (current is None or str(current) in {"37700", "37777"}):
        # Both values have been upstream defaults. Other ports are user choices.
        port = 40000 + int(hashlib.sha256(distro.encode()).hexdigest()[:8], 16) % 20000
        settings["CLAUDE_MEM_WORKER_PORT"] = str(port)
        write_file(path, (json.dumps(settings, indent=2) + "\n").encode(), 0o600)
    else:
        port = int(current or 37700)
    if not 1024 <= int(port) <= 65535:
        raise ValueError("Memory worker port must be in range 1024..65535")
    return int(port)


def antigravity_hooks(runtime):
    expected_events = {
        "SessionStart": "context",
        "PreInvocation": "session-init",
        "PostToolUse": "observation",
        "PostInvocation": "observation",
        "Stop": "summarize",
    }
    expected = {}
    for event, handler in expected_events.items():
        item = {
            "type": "command",
            "command": f"bun {runtime}/scripts/worker-service.cjs hook antigravity-cli {handler}",
            "timeout": 30,
        }
        expected[event] = (
            [{"matcher": "*", "hooks": [item]}] if event == "PostToolUse" else [item]
        )
    return expected


def configure_antigravity(home, runtime, bun, env, previous=None):
    hooks = read_config(home / ".gemini/config/hooks.json")
    expected = antigravity_hooks(runtime)
    old_runtime = (
        Path(previous["runtime"])
        if previous and "antigravity" in previous.get("integrations", {})
        else None
    )
    old_hooks = antigravity_hooks(old_runtime) if old_runtime else None
    desired_mcp = {
        "command": str(bun),
        "args": [str(runtime / "scripts/mcp-server.cjs")],
    }
    complete = hooks.get("claude-mem") == expected
    if "claude-mem" in hooks and not complete and hooks["claude-mem"] != old_hooks:
        raise ValueError(
            "Existing Antigravity memory hooks differ; retained for review"
        )
    for suffix in [
        ".gemini/config/mcp_config.json",
        ".gemini/antigravity/mcp_config.json",
    ]:
        servers = read_config(home / suffix).get("mcpServers", {})
        if not isinstance(servers, dict):
            raise TypeError("Antigravity mcpServers must be a JSON object")
        if (
            "claude-mem" in servers
            and servers["claude-mem"] != desired_mcp
            and servers["claude-mem"]
            != (
                {
                    "command": str(bun),
                    "args": [str(old_runtime / "scripts/mcp-server.cjs")],
                }
                if old_runtime
                else None
            )
        ):
            raise ValueError(
                "Existing Antigravity memory MCP differs; retained for review"
            )
        complete = complete and servers.get("claude-mem") == desired_mcp
    if not complete:
        run(
            [
                str(bun),
                str(runtime / "scripts/worker-service.cjs"),
                "antigravity-cli",
                "install",
            ],
            env={**env, "CLAUDE_PLUGIN_ROOT": str(runtime)},
        )


def service_unit(home, runtime):
    return (
        "# Managed by dotfiles memory_runtime.py\n"
        "[Unit]\nDescription=Claude Mem local memory worker\nAfter=network.target\n"
        "[Service]\nType=simple\n"
        f'Environment="PATH={home}/.local/bin:/usr/local/bin:/usr/bin:/bin"\n'
        f'Environment="CLAUDE_PLUGIN_ROOT={runtime}"\n'
        f"WorkingDirectory={home}\n"
        f"ExecStart={home}/.local/bin/bun {runtime}/scripts/worker-service.cjs --daemon\n"
        "Restart=on-failure\nRestartSec=5\nTimeoutStopSec=30\n"
        "[Install]\nWantedBy=default.target\n"
    )


def configure_service(home, runtime, restart=False, previous_runtime=None):
    # WSL --exec does not open a PAM login, so initialize the user bus explicitly.
    uid = os.getuid()
    env = {
        **os.environ,
        "XDG_RUNTIME_DIR": f"/run/user/{uid}",
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path=/run/user/{uid}/bus",
    }
    distro = os.environ.get("WSL_DISTRO_NAME")
    if distro:
        # WSL distributions share cgroups. Keep each same-UID user manager in
        # its own slice without touching another distro's processes.
        suffix = hashlib.sha256(distro.encode()).hexdigest()[:12]
        override = f"[Service]\nSlice=dotfiles-wsl-{suffix}.slice\n"
        destination = Path(
            f"/etc/systemd/system/user@{uid}.service.d/50-dotfiles-wsl-slice.conf"
        )
        if destination.exists() and destination.read_text() != override:
            raise ValueError("Existing WSL user-manager slice customization retained")
        if not destination.exists():
            with tempfile.NamedTemporaryFile() as temporary:
                temporary.write(override.encode())
                temporary.flush()
                run(
                    [
                        "sudo",
                        "-n",
                        "install",
                        "-D",
                        "-m",
                        "0644",
                        temporary.name,
                        str(destination),
                    ]
                )
            run(["sudo", "-n", "systemctl", "daemon-reload"])
    if distro:
        # A transient resource-busy start can precede a successful manager start
        # by a second while WSL finishes setting up its shared hierarchy.
        retry = (
            "# Managed by dotfiles memory_runtime.py\n[Unit]\nStartLimitIntervalSec=0\n"
            "[Service]\nRestart=on-failure\nRestartSec=1\n"
        )
        if write_system_owned(
            Path(
                f"/etc/systemd/system/user@{uid}.service.d/60-dotfiles-wsl-retry.conf"
            ),
            retry,
        ):
            run(["sudo", "-n", "systemctl", "daemon-reload"])
    run(["sudo", "-n", "loginctl", "enable-linger", getpass.getuser()])
    run(["sudo", "-n", "systemctl", "start", f"user@{uid}.service"])
    unit = service_unit(home, runtime)
    path = home / ".config/systemd/user/claude-mem.service"
    if path.exists() and path.read_text() not in (
        unit,
        service_unit(home, previous_runtime) if previous_runtime else None,
    ):
        raise ValueError("Existing memory service is not dotfiles managed; retained")
    changed = write_file(path, unit.encode())
    run(["systemctl", "--user", "daemon-reload"], env=env)
    run(["systemctl", "--user", "enable", "--now", "claude-mem.service"], env=env)
    if changed or restart:
        run(["systemctl", "--user", "restart", "claude-mem.service"], env=env)
    return env


def wait_for_health(port=37700, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/health", timeout=2
            ) as response:
                value = json.load(response)
            if value.get("status") == "ok" and value.get("initialized") is True:
                return value
        except (OSError, ValueError, urllib.error.URLError):
            pass
        time.sleep(1)
    raise ValueError(
        "Memory worker did not become healthy; inspect journalctl --user -u claude-mem"
    )


def configure_memory(home, selected, source, entry):
    home, source = Path(home), Path(source)
    if home.resolve() != Path.home().resolve():
        raise ValueError("Memory activation must run as the actual target user")
    previous = previous_memory(home, entry)
    bun_path = home / ".local/bin/bun"
    bun_changed = (
        bun_path.is_file()
        and hashlib.sha256(bun_path.read_bytes()).hexdigest()
        != entry["bun"]["binary_sha256"]
    )
    protect_wsl_interop()
    port = configure_port(home)
    bun = install_bun(home, entry["bun"], previous)
    env = {
        **os.environ,
        "PATH": str(home / ".local/bin") + ":" + os.environ.get("PATH", ""),
    }
    roots, result = native_plugins(home, selected, source, entry["version"], previous)
    if not roots:
        # A mutable runtime for other apps, separate from the immutable source vault.
        runtime = home / ".local/share/dotfiles/memory-runtime" / entry["revision"]
        if not runtime.exists():
            runtime.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source / "plugin", runtime)
        verify_plugin_files(runtime, source / "plugin")
        roots.append(runtime)
    for runtime in roots:
        # The official installer also omits optional embeddings on its standard path.
        subprocess.run(
            [
                str(bun),
                "install",
                "--frozen-lockfile",
                "--ignore-scripts",
                "--omit=optional",
            ],
            cwd=runtime,
            env=env,
            check=True,
            stdin=subprocess.DEVNULL,
            timeout=600,
            capture_output=True,
            text=True,
        )
    runtime = roots[0]
    # Build the official standalone launcher, which native hooks call by name.
    run(
        ["node", str(runtime / "scripts/ensure-launcher.cjs")],
        env={**env, "CLAUDE_PLUGIN_ROOT": str(runtime)},
    )
    if not (home / ".local/bin/claude-mem").is_file():
        raise ValueError("Official memory launcher was not installed")
    if "opencode" in selected:
        result["opencode"] = configure_opencode(home, source, runtime, previous)
    if "antigravity" in selected:
        configure_antigravity(home, runtime, bun, env, previous)
        result["antigravity"] = {
            "integration": "official hooks and MCP",
            "hooks": str(home / ".gemini/config/hooks.json"),
        }
    service_env = configure_service(
        home,
        runtime,
        restart=bun_changed
        or bool(previous and previous["bun_sha256"] != entry["bun"]["binary_sha256"]),
        previous_runtime=Path(previous["runtime"]) if previous else None,
    )
    # The default fresh worker uses the standard loopback port. Preserve a custom port.
    health = wait_for_health(port)
    main_pid = run(
        [
            "systemctl",
            "--user",
            "show",
            "claude-mem.service",
            "--property=MainPID",
            "--value",
        ],
        env=service_env,
    ).stdout.strip()
    if main_pid != str(health.get("pid")) or not Path("/proc", main_pid).exists():
        raise ValueError("Health endpoint is not owned by the supervised local worker")
    if health.get("version") != entry["version"] or health.get("workerPath") != str(
        runtime / "scripts/worker-service.cjs"
    ):
        raise ValueError("Healthy worker does not match the pinned local runtime")
    run(
        ["systemctl", "--user", "is-active", "--quiet", "claude-mem.service"],
        env=service_env,
    )
    return {
        "version": entry["version"],
        "bun_sha256": entry["bun"]["binary_sha256"],
        "bun_version": entry["bun"]["version"],
        "source": str(source),
        "runtime": str(runtime),
        "integrations": result,
        "health": {
            "status": health["status"],
            "version": health["version"],
            "port": port,
        },
        "service": "claude-mem.service",
        "authentication": "Provider login is separate; health check makes no model call",
    }
