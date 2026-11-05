"""Memory provisioning preserves custom settings and uses supervised services."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from provision import memory_runtime as memory


class MemoryRuntimeTests(unittest.TestCase):
    def test_opencode_preserves_settings_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            source = home / "source"
            bundle = source / "dist/opencode-plugin/index.js"
            bundle.parent.mkdir(parents=True)
            bundle.write_text("export default {};")
            path = home / ".config/opencode/opencode.json"
            path.parent.mkdir(parents=True)
            custom = {
                "model": "custom/model",
                "plugin": ["other-plugin"],
                "mcp": {"other": {"type": "remote", "url": "https://example.org"}},
            }
            path.write_text(json.dumps(custom))
            memory.configure_opencode(home, source, home / "runtime")
            first = path.read_bytes()
            memory.configure_opencode(home, source, home / "runtime")
            self.assertEqual(first, path.read_bytes())
            data = json.loads(first)
            self.assertEqual(data["model"], custom["model"])
            self.assertEqual(data["mcp"]["other"], custom["mcp"]["other"])
            self.assertEqual(
                data["plugin"], ["other-plugin", "./plugins/claude-mem.js"]
            )

    def test_opencode_retains_conflicting_plugin_and_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            path = home / ".config/opencode/opencode.json"
            path.parent.mkdir(parents=True)
            path.write_text('{"mcp":{"claude-mem":{"type":"remote"}}}')
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                memory.configure_opencode(home, home / "source", home / "runtime")
            self.assertEqual(before, path.read_bytes())

    def test_symlinked_json_is_not_followed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "custom.json"
            target.write_text("{}")
            link = root / "config.json"
            link.symlink_to(target)
            with self.assertRaises(ValueError):
                memory.read_config(link)
            self.assertEqual("{}", target.read_text())

    def test_systemd_runs_foreground_and_persists_without_login(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            with (
                patch.object(memory, "run") as run,
                patch.object(memory.os, "getuid", return_value=1234),
            ):
                memory.configure_service(home, home / "runtime")
            commands = [call.args[0] for call in run.call_args_list]
            self.assertIn(
                ["sudo", "-n", "loginctl", "enable-linger", memory.getpass.getuser()],
                commands,
            )
            self.assertIn(
                ["sudo", "-n", "systemctl", "start", "user@1234.service"], commands
            )
            unit = (home / ".config/systemd/user/claude-mem.service").read_text()
            self.assertIn("--daemon", unit)
            self.assertIn("Restart=on-failure", unit)
            self.assertIn("WantedBy=default.target", unit)
            self.assertNotIn(" start\n", unit)

    def test_wsl_default_port_is_deterministic_and_custom_port_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            with patch.dict(memory.os.environ, {"WSL_DISTRO_NAME": "test-distro"}):
                first = memory.configure_port(home)
                path = home / ".claude-mem/settings.json"
                stamp = path.stat().st_mtime_ns
                self.assertNotIn(first, [37700, 37777])
                self.assertEqual(first, memory.configure_port(home))
                self.assertEqual(stamp, path.stat().st_mtime_ns)
                path.write_text('{"CLAUDE_MEM_WORKER_PORT":"49123","custom":true}')
                self.assertEqual(49123, memory.configure_port(home))
                self.assertTrue(json.loads(path.read_text())["custom"])

    def test_foreign_bun_binary_is_retained(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            bun = home / ".local/bin/bun"
            bun.parent.mkdir(parents=True)
            bun.write_bytes(b"custom binary")
            with self.assertRaises(ValueError):
                memory.install_bun(home, {"binary_sha256": "wrong"})
            self.assertEqual(b"custom binary", bun.read_bytes())

    def test_conflicting_antigravity_hooks_are_retained(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            path = home / ".gemini/config/hooks.json"
            path.parent.mkdir(parents=True)
            path.write_text('{"claude-mem":{"SessionStart":[]},"other":{}}')
            before = path.read_bytes()
            with patch.object(memory, "run") as run:
                with self.assertRaises(ValueError):
                    memory.configure_antigravity(
                        home, home / "runtime", home / "bun", {}
                    )
                run.assert_not_called()
            self.assertEqual(before, path.read_bytes())

    def test_boot_interop_restores_only_missing_registration(self):
        unit = memory.wsl_interop_unit()
        self.assertIn("if [ ! -e /proc/sys/fs/binfmt_misc/WSLInterop ]", unit)
        self.assertIn("After=systemd-binfmt.service", unit)
        self.assertIn("WantedBy=multi-user.target", unit)
        self.assertNotIn("echo -1", unit)
        self.assertNotIn("ExecStop", unit)

    def test_owned_system_file_retains_customization(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "custom.conf"
            path.write_text("custom")
            with patch.object(memory, "run") as run:
                with self.assertRaises(ValueError):
                    memory.write_system_owned(path, "managed")
                run.assert_not_called()
            self.assertEqual("custom", path.read_text())

    def test_owned_bun_upgrade_and_retry_preserve_unknown_binary(self):
        import hashlib
        import io
        import zipfile

        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            bun = home / ".local/bin/bun"
            bun.parent.mkdir(parents=True)
            bun.write_bytes(b"old")
            old_hash = hashlib.sha256(b"old").hexdigest()
            new_hash = hashlib.sha256(b"new").hexdigest()
            entry = {"binary_sha256": new_hash, "member": "bun"}
            payload = io.BytesIO()
            with zipfile.ZipFile(payload, "w") as archive:
                archive.writestr("bun", b"new")
            with patch.object(
                memory, "download", return_value=payload.getvalue()
            ) as download:
                memory.install_bun(home, entry, {"bun_sha256": old_hash})
                self.assertEqual(b"new", bun.read_bytes())
                memory.install_bun(home, entry, {"bun_sha256": old_hash})
                self.assertEqual(1, download.call_count)
                bun.write_bytes(b"edited")
                with self.assertRaises(ValueError):
                    memory.install_bun(home, entry, {"bun_sha256": old_hash})
                self.assertEqual(b"edited", bun.read_bytes())

    def test_opencode_upgrades_only_exact_owned_bundle_and_mcp(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            old, new = home / "old", home / "new"
            for source in (old, new):
                path = source / "dist/opencode-plugin/index.js"
                path.parent.mkdir(parents=True)
                path.write_text(source.name)
            integration = memory.configure_opencode(home, old, home / "old-runtime")
            previous = {"source": str(old), "integrations": {"opencode": integration}}
            memory.configure_opencode(home, new, home / "new-runtime", previous)
            destination = Path(integration["plugin"])
            self.assertEqual(b"new", destination.read_bytes())
            memory.configure_opencode(home, new, home / "new-runtime", previous)
            destination.write_bytes(b"edited")
            with self.assertRaises(ValueError):
                memory.configure_opencode(home, new, home / "new-runtime", previous)
            self.assertEqual(b"edited", destination.read_bytes())

    def test_service_restarts_after_bun_upgrade_even_with_unchanged_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            with (
                patch.dict(memory.os.environ, {}, clear=True),
                patch.object(memory, "run") as run,
            ):
                memory.configure_service(home, home / "runtime")
                run.reset_mock()
                memory.configure_service(home, home / "runtime", restart=True)
                self.assertIn(
                    ["systemctl", "--user", "restart", "claude-mem.service"],
                    [call.args[0] for call in run.call_args_list],
                )
                path = home / ".config/systemd/user/claude-mem.service"
                path.write_text(path.read_text() + "# owner edit\n")
                with self.assertRaises(ValueError):
                    memory.configure_service(
                        home, home / "new-runtime", previous_runtime=home / "runtime"
                    )
                self.assertTrue(path.read_text().endswith("# owner edit\n"))

    def test_native_plugin_upgrade_verifies_old_cache_and_uses_native_commands(self):
        from types import SimpleNamespace

        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            old, new = home / "old", home / "new"
            cache = home / "cache"
            cache.mkdir()
            for source in (old, new):
                (source / "plugin").mkdir(parents=True)
                (source / "plugin/package.json").write_text(source.name)
            (cache / "package.json").write_text("old")
            previous = {
                "source": str(old),
                "version": "1.0.0",
                "integrations": {
                    "claude": {"plugin": "claude-mem@thedotmack", "path": str(cache)}
                },
            }
            state = [
                {
                    "id": "claude-mem@thedotmack",
                    "version": "1.0.0",
                    "enabled": True,
                    "readFromFolder": str(old / "plugin"),
                    "installPath": str(cache),
                }
            ]

            def command(argv):
                if argv[1:3] == ["plugin", "list"]:
                    return SimpleNamespace(stdout=json.dumps(state))
                if argv[1:3] == ["plugin", "install"]:
                    state[0].update(version="2.0.0", readFromFolder=str(new / "plugin"))
                    (cache / "package.json").write_text("new")
                return SimpleNamespace(stdout="")

            with patch.object(memory, "run", side_effect=command) as run:
                memory.native_plugins(home, ["claude"], new, "2.0.0", previous)
                commands = [call.args[0] for call in run.call_args_list]
                self.assertIn(
                    [
                        str(home / ".local/bin/claude"),
                        "plugin",
                        "uninstall",
                        "claude-mem@thedotmack",
                        "--scope",
                        "user",
                    ],
                    commands,
                )
                run.reset_mock()
                memory.native_plugins(home, ["claude"], new, "2.0.0", previous)
                self.assertFalse(
                    any(call.args[0][2] == "uninstall" for call in run.call_args_list)
                )
                state[0].update(version="1.0.0", readFromFolder=str(old / "plugin"))
                (cache / "package.json").write_text("edited")
                run.reset_mock()
                with self.assertRaises(ValueError):
                    memory.native_plugins(home, ["claude"], new, "2.0.0", previous)
                self.assertEqual(1, run.call_count)

    def test_previous_receipt_requires_immutable_source_and_rejects_downgrades(self):
        from provision.tool_bundle import tree_digest

        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            source = home / ".local/share/dotfiles/skill-sources/claude-mem/revision"
            (source / "plugin").mkdir(parents=True)
            package = source / "plugin/package.json"
            package.write_text('{"version":"2.0.0"}')
            (source / ".dotfiles-source.json").write_text(
                json.dumps({"tree": tree_digest(source)})
            )
            receipt = {
                "version": "2.0.0",
                "source": str(source),
                "runtime": str(home / ".local/share/dotfiles/memory-runtime/revision"),
                "integrations": {},
                "health": {"version": "2.0.0", "status": "ok"},
                "bun_sha256": "owned",
                "bun_version": "1.4.0",
            }
            path = home / ".local/state/dotfiles/agent-apps.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"memory": receipt}))
            candidate = {"version": "3.0.0", "bun": {"version": "1.4.1"}}
            self.assertEqual(receipt, memory.previous_memory(home, candidate))
            with self.assertRaisesRegex(ValueError, "downgrades"):
                memory.previous_memory(home, {**candidate, "version": "1.0.0"})
            with self.assertRaisesRegex(ValueError, "downgrades"):
                memory.previous_memory(home, {**candidate, "bun": {"version": "1.3.0"}})
            package.write_text('{"version":"edited"}')
            with self.assertRaisesRegex(ValueError, "local edits"):
                memory.previous_memory(home, candidate)
