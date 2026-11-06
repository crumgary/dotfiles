"""User-only installation never adopts system packages or requests privileges."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from provision import install_tools, memory_runtime, tool_bundle, tool_updates


class UserOnlyTests(unittest.TestCase):
    def test_cli_preview_excludes_system_management(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "absent"
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/install-tools"),
                    "--dry-run",
                    "--user-only",
                    "--apps",
                    "codex",
                    "--home",
                    str(home),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertEqual(plan["installation_mode"], "user")
            self.assertEqual(plan["system"], {})
            self.assertNotIn("nodejs", plan["tools"])
            self.assertIn("playwright", plan["tools"])
            self.assertFalse(home.exists())

    def test_bundle_records_missing_native_packages_without_using_sudo(self):
        catalog = json.loads((ROOT / "config/tools.lock.json").read_text())
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            with (
                patch.object(tool_bundle, "run") as run,
                patch.object(tool_bundle, "validate_binary_ownership"),
                patch.object(tool_bundle, "install_binary"),
                patch.object(tool_bundle, "install_npm"),
                patch.object(tool_bundle, "stage_skills", return_value="staged"),
                patch("provision.python_tools.install_python_tools"),
                patch("provision.system_packages.installed_version", return_value=None),
                patch("provision.system_packages.install_system") as system,
                patch.object(
                    tool_bundle.subprocess, "check_output", return_value="v26.13.0\n"
                ),
            ):
                receipt = tool_bundle.install_bundle(
                    home, catalog, ROOT / "config/tools.lock.json", user_only=True
                )
            system.assert_not_called()
            self.assertFalse(any(c.args[0][0] == "sudo" for c in run.call_args_list))
            self.assertEqual(receipt["installation_mode"], "user")
            self.assertIsNone(receipt["system_packages"]["skopeo"])
            self.assertNotIn("skopeo", receipt["tools"])

    def test_runtime_mismatch_stops_before_user_or_system_installation(self):
        catalog = json.loads((ROOT / "config/tools.lock.json").read_text())
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(
                tool_bundle.subprocess, "check_output", return_value="v24.22.2\n"
            ),
            patch.object(tool_bundle, "install_binary") as binary,
            patch("provision.system_packages.install_system") as system,
            self.assertRaisesRegex(ValueError, "Node 26"),
        ):
            tool_bundle.install_bundle(
                Path(temporary),
                catalog,
                ROOT / "config/tools.lock.json",
                user_only=True,
            )
        binary.assert_not_called()
        system.assert_not_called()

    def test_failed_user_install_preserves_mode_and_ownership_for_ordinary_retry(self):
        catalog = json.loads((ROOT / "config/tools.lock.json").read_text())
        for previous in (
            {},
            {"installation_mode": "system", "binary_hashes": {"custom": "hash"}},
        ):
            with (
                self.subTest(previous=previous),
                tempfile.TemporaryDirectory() as temporary,
            ):
                home = Path(temporary)
                receipt = home / ".local/state/dotfiles/developer-tools.json"
                if previous:
                    receipt.parent.mkdir(parents=True)
                    receipt.write_text(json.dumps(previous))
                with (
                    patch.object(tool_bundle, "validate_binary_ownership"),
                    patch.object(tool_bundle, "install_binary"),
                    patch.object(
                        tool_bundle,
                        "install_npm",
                        side_effect=ValueError("browser failed"),
                    ),
                    patch(
                        "provision.system_packages.installed_version", return_value=None
                    ),
                    patch.object(
                        tool_bundle.subprocess,
                        "check_output",
                        return_value="v26.13.0\n",
                    ),
                    self.assertRaisesRegex(ValueError, "browser failed"),
                ):
                    tool_bundle.install_bundle(
                        home, catalog, ROOT / "config/tools.lock.json", user_only=True
                    )
                self.assertTrue(install_tools.user_only_mode(home))
                saved = json.loads(receipt.read_text())
                if previous:
                    self.assertEqual(saved["binary_hashes"], previous["binary_hashes"])
                with (
                    patch.object(Path, "home", return_value=home),
                    patch.object(install_tools, "require_supported_host"),
                    patch.object(
                        install_tools, "install_bundle", return_value={}
                    ) as bundle,
                ):
                    install_tools.install_tools(
                        home, catalog, ROOT / "config/tools.lock.json", []
                    )
                self.assertTrue(bundle.call_args.kwargs["user_only"])

    def test_saved_user_mode_survives_installer_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            receipt = home / ".local/state/dotfiles/developer-tools.json"
            receipt.parent.mkdir(parents=True)
            receipt.write_text('{"installation_mode":"user"}')
            self.assertTrue(install_tools.user_only_mode(home))

    def test_memory_user_service_uses_existing_manager_without_machine_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            with (
                patch.dict(memory_runtime.os.environ, {"WSL_DISTRO_NAME": "test"}),
                patch.object(
                    memory_runtime, "run", return_value=SimpleNamespace(stdout="")
                ) as run,
            ):
                memory_runtime.configure_service(home, home / "runtime", user_only=True)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertTrue(commands)
            self.assertTrue(
                all(command[:2] == ["systemctl", "--user"] for command in commands)
            )
            self.assertIn(
                ["systemctl", "--user", "enable", "--now", "claude-mem.service"],
                commands,
            )

    def test_update_does_not_request_system_upgrades_in_saved_user_mode(self):
        catalog = json.loads((ROOT / "config/tools.lock.json").read_text())
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            receipt = home / ".local/state/dotfiles/developer-tools.json"
            receipt.parent.mkdir(parents=True)
            receipt.write_text('{"installation_mode":"user"}')
            with (
                patch.object(tool_updates, "validate_npm_updates"),
                patch.object(tool_updates.subprocess, "run") as run,
            ):
                tool_updates.install_candidate(
                    catalog, ROOT / "config/tools.lock.json", home, ROOT, None
                )
            command = run.call_args.args[0]
            self.assertIn("--user-only", command)
            self.assertNotIn("--upgrade-system", command)

    def test_user_mode_rejects_explicit_native_update_instead_of_claiming_success(self):
        catalog = json.loads((ROOT / "config/tools.lock.json").read_text())
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            receipt = home / ".local/state/dotfiles/developer-tools.json"
            receipt.parent.mkdir(parents=True)
            receipt.write_text('{"installation_mode":"user"}')
            with (
                patch.object(tool_updates, "validate_npm_updates"),
                patch.object(tool_updates.subprocess, "run") as run,
                self.assertRaisesRegex(ValueError, "externally managed"),
            ):
                tool_updates.install_candidate(
                    catalog, ROOT / "config/tools.lock.json", home, ROOT, {"acli"}
                )
            run.assert_not_called()
