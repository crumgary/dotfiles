"""Exercise older system Python entrypoints without network or filesystem writes."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = r"""
import os, runpy, sys
sys.dont_write_bytecode = True
mode, script, *arguments = sys.argv[1:]
if mode != 'stdlib':
    sys.modules['tomllib'] = None
if mode.startswith('3.'):
    sys.version_info = tuple(map(int, mode.split('.'))) + (0, 'final', 0)
def guard(event, args):
    if event == 'open' and isinstance(args[2], int) and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
        raise RuntimeError('filesystem write denied')
    if event.startswith('socket.') or event in {'os.mkdir', 'os.remove', 'os.rename', 'os.chmod', 'os.symlink', 'os.link', 'os.rmdir', 'os.truncate', 'os.utime', 'os.chown', 'os.mknod', 'os.system', 'os.exec', 'subprocess.Popen', 'os.posix_spawn'}:
        raise RuntimeError('mutation, network or subprocess denied')
sys.addaudithook(guard)
sys.path.insert(0, str(__import__('pathlib').Path(script).parent))
sys.argv = [script, *arguments]
runpy.run_path(script, run_name='__main__')
"""


class TomlCompatibilityTests(unittest.TestCase):
    def run_cli(self, version, script, *arguments):
        return subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                GUARD,
                version,
                str(ROOT / "scripts" / script),
                *map(str, arguments),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_installer_dry_run_uses_offline_fallback_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            config = home / ".config/chezmoi/chezmoi.toml"
            config.parent.mkdir(parents=True)
            config.write_text(
                '[data]\ninstall_developer_tools=true\nagent_apps=["codex"]\n'
            )
            original = config.read_bytes()
            for version in ("3.9", "3.10", "stdlib"):
                with self.subTest(version=version):
                    result = self.run_cli(
                        version,
                        "install-tools",
                        "--dry-run",
                        "--from-chezmoi",
                        "--home",
                        home,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(set(json.loads(result.stdout)["apps"]), {"codex"})
                    self.assertEqual(config.read_bytes(), original)
                    self.assertFalse((home / ".local").exists())

    def test_doctor_import_preview_uses_offline_fallback_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            config = home / ".config/chezmoi/chezmoi.toml"
            config.parent.mkdir(parents=True)
            config.write_text(
                '[data]\nprofile="wsl"\nwork=false\nbootstrap_priv_overlay=false\nbootstrap_work_overlay=false\ninstall_agent_clis=false\n'
            )
            for version in ("3.9", "3.10", "stdlib"):
                with self.subTest(version=version):
                    result = self.run_cli(
                        version,
                        "dotfiles-doctor",
                        "--import-current",
                        "--id",
                        "offline",
                        "--owner",
                        "local",
                        "--home",
                        home,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('id = "offline"', result.stdout)

    def test_updater_imports_and_displays_help_without_bootstrap(self):
        for version in ("3.9", "3.10", "stdlib"):
            with self.subTest(version=version):
                result = self.run_cli(version, "update-tools", "--help")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("--apply", result.stdout)

    def test_doctor_inspects_record_and_catalog_with_offline_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            packages = source / "home/.chezmoidata/packages.toml"
            packages.parent.mkdir(parents=True)
            packages.write_text('[doctor]\ncommon=["absent-compatibility-tool"]\n')
            record = root / "machine.toml"
            record.write_text(
                'schema_version=1\nid="offline"\nowner="local"\nprofile="wsl"\n'
                'os="ubuntu"\narchitecture="x86_64"\noverlays=[]\nbundles=[]\n'
            )
            for version in ("3.9", "3.10", "stdlib"):
                with self.subTest(version=version):
                    result = self.run_cli(
                        version,
                        "dotfiles-doctor",
                        "--machine",
                        record,
                        "--source",
                        source,
                        "--home",
                        root / "absent",
                        "--json",
                    )
                    self.assertEqual(result.returncode, 1, result.stderr)
                    findings = json.loads(result.stdout)["findings"]
                    tool = next(
                        item
                        for item in findings
                        if item["check"] == "tool:absent-compatibility-tool"
                    )
                    self.assertEqual(tool["status"], "missing")
                    self.assertFalse((root / "absent").exists())

    def test_entrypoints_reject_older_python_before_imports(self):
        for script in ("install-tools", "update-tools", "dotfiles-doctor"):
            with self.subTest(script=script):
                result = self.run_cli("3.8", script, "--help")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("Python 3.9 or newer", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_stdlib_parser_is_preferred_when_available(self):
        try:
            import tomllib
        except ModuleNotFoundError:
            self.skipTest("stdlib tomllib is only present on Python 3.11+")
        sys.path.insert(0, str(ROOT / "scripts"))
        from provision.toml_compat import tomllib as parser

        self.assertIs(parser, tomllib)


if __name__ == "__main__":
    unittest.main()
