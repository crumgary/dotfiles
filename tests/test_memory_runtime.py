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
