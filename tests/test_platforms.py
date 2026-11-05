"""Resolve supported hosts and keep OS packages out of portable release pins."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class PlatformTests(unittest.TestCase):
    def module(self):
        from provision import host_platform

        return host_platform

    def target(self, distro, version, arch="x86_64"):
        with tempfile.TemporaryDirectory() as temporary:
            release = Path(temporary) / "os-release"
            release.write_text(f'ID="{distro}"\nVERSION_ID="{version}"\n')
            return self.module().detect_host(release, arch)

    def test_supported_releases_resolve_native_package_recipes(self):
        for version in ("22.04", "24.04", "26.04"):
            host = self.target("ubuntu", version)
            recipe = self.module().system_recipe(host)
            self.assertEqual(recipe["manager"], "apt")
            self.assertEqual(recipe["packages"]["nodejs"]["name"], "nodejs")
        host = self.target("almalinux", "9.7")
        recipe = self.module().system_recipe(host)
        self.assertEqual(recipe["manager"], "dnf")
        self.assertEqual(recipe["packages"]["ffmpeg"]["name"], "ffmpeg")

    def test_unknown_systems_and_architectures_fail_before_changes(self):
        for distro, version, arch in [
            ("ubuntu", "20.04", "x86_64"),
            ("fedora", "44", "x86_64"),
            ("almalinux", "8.10", "x86_64"),
            ("ubuntu", "24.04", "aarch64"),
        ]:
            with (
                self.subTest(distro=distro, version=version, arch=arch),
                self.assertRaises(ValueError),
            ):
                self.target(distro, version, arch)

    def test_legacy_catalog_migration_preserves_all_portable_pins_and_user_metadata(
        self,
    ):
        old = json.loads((ROOT / "config/tools.lock.json").read_text())
        old["schema_version"] = 1
        old["platform"] = "ubuntu-26.04-x86_64"
        old["developer"]["apt"] = {"nodejs": "26.13.0-1nodesource1"}
        old["developer"]["repositories"] = {
            "legacy": {"uri": "https://example.invalid"}
        }
        old["owner_note"] = "keep"
        migrated = self.module().portable_catalog(old)
        self.assertEqual(migrated["schema_version"], 2)
        self.assertEqual(migrated["platform"], "linux-x86_64")
        self.assertNotIn("apt", migrated["developer"])
        self.assertNotIn("repositories", migrated["developer"])
        self.assertEqual(migrated["agents"], old["agents"])
        self.assertEqual(migrated["skills"], old["skills"])
        self.assertEqual(migrated["developer"]["npm"], old["developer"]["npm"])
        self.assertEqual(migrated["owner_note"], "keep")
        self.assertIn("apt", old["developer"])

    def test_verified_update_publishes_portable_migration_after_installation(self):
        from provision import tool_updates

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "checkout/config/tools.lock.json"
            path.parent.mkdir(parents=True)
            old = json.loads((ROOT / "config/tools.lock.json").read_text())
            old["schema_version"] = 1
            old["platform"] = "ubuntu-26.04-x86_64"
            old["developer"]["apt"] = {"nodejs": "26.13.0-1nodesource1"}
            old["developer"]["repositories"] = {}
            path.write_text(json.dumps(old))
            before = path.read_bytes()

            def install(candidate, *args):
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(candidate["agents"], old["agents"])
                self.assertEqual(candidate["schema_version"], 2)
                return {"verified": True}

            result = tool_updates.apply_update(
                path,
                root / "home",
                resolver=lambda current, only: self.module().portable_catalog(current),
                installer=install,
            )
            self.assertEqual(result["status"], "verified")
            self.assertEqual(json.loads(path.read_text())["schema_version"], 2)

    def test_host_recipes_override_foreign_legacy_command_aliases_and_baselines(self):
        from provision.checks import managed_requirements

        catalog = {
            "developer": {"apt": {"imagemagick": "8.0.0"}, "binaries": {}, "npm": {}},
            "agents": {},
        }
        commands, versions = managed_requirements(
            catalog, [], {"imagemagick": {"commands": ["magick|convert"]}}
        )
        self.assertIn("magick|convert", commands)
        self.assertNotIn("magick", commands)
        self.assertNotIn("magick", versions)

    def test_resumed_legacy_candidate_migrates_without_resolving_new_versions(self):
        from provision import tool_updates

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "checkout/config/tools.lock.json"
            path.parent.mkdir(parents=True)
            legacy = json.loads((ROOT / "config/tools.lock.json").read_text())
            legacy["schema_version"] = 1
            legacy["platform"] = "ubuntu-26.04-x86_64"
            legacy["developer"]["apt"] = {"nodejs": "26.13.0-1nodesource1"}
            legacy["developer"]["repositories"] = {}
            path.write_text(json.dumps(legacy))
            with self.assertRaises(ValueError):
                tool_updates.apply_update(
                    path,
                    root / "home",
                    resolver=lambda current, only: legacy,
                    installer=lambda *args: (_ for _ in ()).throw(
                        ValueError("interrupted")
                    ),
                )

            # Simulate a prior process that published the schema-1 candidate
            # before losing its completion state, then another interrupted retry.
            path.write_bytes(tool_updates.encoded(legacy))
            with self.assertRaises(ValueError):
                tool_updates.apply_update(
                    path,
                    root / "home",
                    resolver=lambda *args: self.fail(
                        "Frozen versions must not be resolved again"
                    ),
                    installer=lambda *args: (_ for _ in ()).throw(
                        ValueError("retry interrupted")
                    ),
                )

            def verify(candidate, *args):
                self.assertEqual(candidate["schema_version"], 2)
                self.assertEqual(candidate["agents"], legacy["agents"])
                self.assertEqual(candidate["skills"], legacy["skills"])
                return {"verified": True}

            tool_updates.apply_update(
                path,
                root / "home",
                resolver=lambda *args: self.fail(
                    "Frozen versions must not be resolved again"
                ),
                installer=verify,
            )
            self.assertEqual(json.loads(path.read_text())["schema_version"], 2)
