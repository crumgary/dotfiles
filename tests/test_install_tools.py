"""The public installer treats AI apps and other developer tools as one setup."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/install-tools"
sys.path.insert(0, str(ROOT / "scripts"))


class InstallerCliTests(unittest.TestCase):
    def test_combined_dry_run_has_tools_apps_and_skills_without_creating_home(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "absent"
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(CLI),
                    "--dry-run",
                    "--apps",
                    "claude,codex,opencode,antigravity",
                    "--home",
                    str(home),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertIn("playwright", plan["tools"])
            self.assertIn("claude-mem", plan["skills"])
            self.assertEqual(
                set(plan["apps"]), {"claude", "codex", "opencode", "antigravity"}
            )
            self.assertFalse(home.exists())

    def test_existing_chezmoi_selections_feed_one_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            config = home / ".config/chezmoi/chezmoi.toml"
            config.parent.mkdir(parents=True)
            config.write_text(
                '[data]\ninstall_developer_tools=true\nagent_apps=["codex"]\n'
            )
            original = config.read_bytes()
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(CLI),
                    "--dry-run",
                    "--from-chezmoi",
                    "--home",
                    str(home),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(set(json.loads(result.stdout)["apps"]), {"codex"})
            self.assertEqual(config.read_bytes(), original)
            self.assertFalse((home / ".local").exists())

    def test_selected_apps_enable_prerequisites_with_old_bundle_flag_disabled(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            config = home / ".config/chezmoi/chezmoi.toml"
            config.parent.mkdir(parents=True)
            config.write_text(
                '[data]\ninstall_developer_tools=false\nagent_apps=["codex"]\n'
            )
            original = config.read_bytes()
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(CLI),
                    "--dry-run",
                    "--from-chezmoi",
                    "--home",
                    str(home),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(set(json.loads(result.stdout)["apps"]), {"codex"})
            self.assertTrue(json.loads(result.stdout)["enabled"])
            self.assertEqual(config.read_bytes(), original)
            self.assertFalse((home / ".local").exists())


class InstallerExecutionTests(unittest.TestCase):
    def setUp(self):
        from provision import install_tools

        self.installer = install_tools
        self.catalog = json.loads((ROOT / "config/tools.lock.json").read_text())

    def test_prerequisites_precede_adapters_and_staged_sources_are_reused(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            order = []

            def prerequisites(*args):
                order.append("prerequisites")
                return {"skill_sources": {"tstack": str(home / "source")}}

            def adapters(*args):
                self.assertEqual(order, ["prerequisites"])
                self.assertEqual(args[-1], {"tstack": home / "source"})
                order.append("adapters")
                return {"apps": {"codex": "verified"}}

            with (
                patch.object(Path, "home", return_value=home),
                patch.object(self.installer, "require_supported_host"),
                patch.object(
                    self.installer, "install_bundle", side_effect=prerequisites
                ),
                patch.object(self.installer, "configure_apps", side_effect=adapters),
            ):
                report = self.installer.install_tools(
                    home, self.catalog, ROOT / "config/tools.lock.json", ["codex"]
                )
            self.assertEqual(order, ["prerequisites", "adapters"])
            self.assertEqual(report["status"], "verified")

    def test_prerequisite_failure_does_not_run_app_adapters(self):
        from unittest.mock import patch

        with (
            patch.object(self.installer, "require_supported_host"),
            patch.object(
                self.installer,
                "install_bundle",
                side_effect=ValueError("dependency failed"),
            ),
            patch.object(self.installer, "configure_apps") as adapters,
            self.assertRaisesRegex(ValueError, "dependency failed"),
        ):
            self.installer.install_tools(
                Path.home(), self.catalog, ROOT / "config/tools.lock.json", ["codex"]
            )
        adapters.assert_not_called()

    def test_invalid_selection_is_rejected_before_any_package_change(self):
        from unittest.mock import patch

        with (
            patch.object(self.installer, "install_bundle") as packages,
            self.assertRaises(ValueError),
        ):
            self.installer.install_tools(
                Path.home(), self.catalog, ROOT / "config/tools.lock.json", ["unknown"]
            )
        packages.assert_not_called()

    def test_no_optional_apps_still_installs_selected_shared_tools(self):
        from unittest.mock import patch

        with (
            patch.object(self.installer, "require_supported_host"),
            patch.object(self.installer, "install_bundle", return_value={}) as packages,
            patch.object(self.installer, "configure_apps") as adapters,
        ):
            self.installer.install_tools(
                Path.home(), self.catalog, ROOT / "config/tools.lock.json", []
            )
        packages.assert_called_once()
        adapters.assert_not_called()

    def test_disabled_existing_configuration_does_not_install(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            config = home / ".config/chezmoi/chezmoi.toml"
            config.parent.mkdir(parents=True)
            config.write_text("[data]\ninstall_developer_tools=false\nagent_apps=[]\n")
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(CLI),
                    "--apply",
                    "--from-chezmoi",
                    "--home",
                    str(home),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "disabled")
            self.assertFalse((home / ".local").exists())


class ChezmoiHookTests(unittest.TestCase):
    def test_one_hook_covers_all_tools_and_is_empty_when_disabled(self):
        import shutil

        executable = shutil.which("chezmoi")
        if not executable:
            self.skipTest("chezmoi is required for hook integration checks")
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "chezmoi.toml"
            config.write_text("[data]\n")
            command = [
                executable,
                "--source",
                str(ROOT / "home"),
                "--config",
                str(config),
                "--override-data",
                '{"install_developer_tools":true,"agent_apps":["codex"]}',
                "execute-template",
                "--file",
                str(ROOT / "home/run_onchange_after_install-tools.sh.tmpl"),
            ]
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            self.assertEqual(
                result.stdout.count('scripts/install-tools" --apply --from-chezmoi'), 1
            )
            self.assertIn("# module: install_tools.py", result.stdout)
            self.assertIn("# module: agent_apps.py", result.stdout)
            self.assertIn("# module: tool_bundle.py", result.stdout)
            self.assertIn('# Selected apps: ["codex"]', result.stdout)
            command[command.index("--override-data") + 1] = (
                '{"install_developer_tools":false,"agent_apps":[]}'
            )
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            self.assertFalse(result.stdout.strip())
            command[command.index("--override-data") + 1] = (
                '{"install_agent_clis":true,"install_developer_tools":true,"agent_apps":[]}'
            )
            result = subprocess.run(
                command, capture_output=True, text=True, check=False
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("install_agent_clis=false", result.stderr)


class SelectionPreflightTests(unittest.TestCase):
    def test_opencode_dependency_is_rejected_before_apply_creates_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "absent"
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(CLI),
                    "--apply",
                    "--apps",
                    "opencode",
                    "--home",
                    str(home),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("Claude", result.stderr)
            self.assertFalse(home.exists())

    def test_conflicting_legacy_and_managed_modes_fail_before_installation(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            config = home / ".config/chezmoi/chezmoi.toml"
            config.parent.mkdir(parents=True)
            config.write_text(
                "[data]\ninstall_agent_clis=true\ninstall_developer_tools=true\n"
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(CLI),
                    "--apply",
                    "--from-chezmoi",
                    "--home",
                    str(home),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("install_agent_clis=false", result.stderr)
            self.assertFalse((home / ".local").exists())
