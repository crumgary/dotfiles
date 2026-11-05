"""Native packages follow each target's repositories rather than foreign pins."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


class RepositoryTests(unittest.TestCase):
    def test_repository_formats_are_native_and_all_signing_keys_are_pinned(self):
        from provision.host_platform import system_recipe
        from provision.system_packages import repository_files

        for distro, release, manager in [
            ("ubuntu", "22.04", "apt"),
            ("almalinux", "9", "dnf"),
        ]:
            recipe = system_recipe(
                {"os": distro, "release": release, "architecture": "x86_64"}
            )
            files = repository_files(recipe, 26)
            self.assertEqual(len(files), len(recipe["repositories"]))
            for path, content, key, entry in files:
                self.assertEqual(len(entry["key_sha256"]), 64)
                self.assertNotIn("{node_major}", content)
                if manager == "apt":
                    self.assertEqual(path.suffix, ".sources")
                    self.assertIn("Signed-By:", content)
                else:
                    self.assertEqual(path.suffix, ".repo")
                    self.assertIn("gpgcheck=1", content)
                    self.assertIn("gpgkey=file://", content)
            node = next(item for item in files if "nodesource" in str(item[0]))
            self.assertIn("26.x", node[1])


class NativePolicyTests(unittest.TestCase):
    def test_existing_distro_package_is_retained_without_foreign_version_baseline(self):
        from unittest.mock import patch

        from provision import system_packages as system

        recipe = {
            "manager": "apt",
            "packages": {"gh": {"name": "gh"}},
            "repositories": {},
        }
        with (
            patch.object(system, "installed_version", return_value="2.0"),
            patch.object(system, "run") as run,
        ):
            self.assertEqual(system.install_system(recipe, 26), {"gh": "2.0"})
        run.assert_not_called()

    def test_node_major_upgrades_without_foreign_package_revision_pins(self):
        from unittest.mock import patch

        from provision import system_packages as system

        recipe = {
            "manager": "apt",
            "packages": {"nodejs": {"name": "nodejs"}},
            "repositories": {},
        }
        with (
            patch.object(system, "installed_version", side_effect=["24.0.0", "26.0.0"]),
            patch.object(system, "run") as run,
        ):
            system.install_system(recipe, 26)
        self.assertIn("nodejs", run.call_args_list[-1].args[0])
        self.assertIn("--no-remove", run.call_args_list[-1].args[0])
        with (
            patch.object(system, "installed_version", return_value="28.0.0"),
            patch.object(system, "run") as run,
            self.assertRaises(ValueError),
        ):
            system.install_system(recipe, 26)
        run.assert_not_called()

    def test_dnf_metadata_key_confirmation_is_noninteractive_and_keeps_signature_checks(
        self,
    ):
        import hashlib
        import tempfile
        from unittest.mock import patch

        from provision import system_packages as system

        recipe = {
            "manager": "dnf",
            "packages": {"gh": {"name": "gh", "repository": "github"}},
            "repositories": {},
        }
        with tempfile.TemporaryDirectory() as temporary:
            key = Path(temporary) / "key.asc"
            key.write_bytes(b"verified key")
            generated = [
                (
                    Path(temporary) / "dotfiles-github.repo",
                    "gpgcheck=1",
                    key,
                    {"key_sha256": hashlib.sha256(key.read_bytes()).hexdigest()},
                )
            ]
            with (
                patch.object(system, "installed_version", return_value="2.0"),
                patch.object(system, "repository_files", return_value=generated),
                patch.object(system, "write_system", return_value=True),
                patch.object(system, "run") as run,
            ):
                system.install_system(recipe, 26)
            self.assertIn(
                ["sudo", "-n", "dnf", "makecache", "--refresh", "-y"],
                [call.args[0] for call in run.call_args_list],
            )
            self.assertIn(
                ["sudo", "-n", "dnf", "upgrade", "-y", "gh"],
                [call.args[0] for call in run.call_args_list],
            )

    def test_browser_native_dependencies_use_the_guarded_system_transaction(self):
        from unittest.mock import patch

        from provision import system_packages as system

        installed = {"gh": "2.0"}
        recipe = {
            "manager": "apt",
            "packages": {"gh": {"name": "gh"}},
            "dependencies": ["browser-lib"],
            "repositories": {},
        }

        def command(arguments):
            if "install" in arguments:
                self.assertIn("--no-remove", arguments)
                self.assertIn("browser-lib", arguments)
                installed["browser-lib"] = "1.0"

        with (
            patch.object(
                system,
                "installed_version",
                side_effect=lambda manager, name: installed.get(name),
            ),
            patch.object(system, "run", side_effect=command),
        ):
            system.install_system(recipe, 26)
        self.assertIn("browser-lib", installed)
