"""Updates preserve approved state until validation and resume frozen failures."""

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from provision import tool_updates, version_catalog


def catalog():
    return {
        "schema_version": 1,
        "runtime_major": 26,
        "developer": {
            "apt": {},
            "binaries": {},
            "npm": {"sample": "1.0.0"},
            "python": {},
        },
        "agents": {},
        "skills": {},
    }


def newer(before, only):
    after = json.loads(json.dumps(before))
    after["developer"]["npm"]["sample"] = "1.1.0"
    return after


class VersionResolutionTests(unittest.TestCase):
    def test_selected_npm_update_is_discovered_without_other_requests(self):
        before = catalog()
        requests = []

        def get_json(url):
            requests.append(url)
            return {"version": "1.1.0"}

        candidate = version_catalog.resolve_catalog(
            before, {"sample"}, get_json, lambda url: self.fail("Unexpected download")
        )
        self.assertEqual(candidate["developer"]["npm"]["sample"], "1.1.0")
        self.assertEqual(before["developer"]["npm"]["sample"], "1.0.0")
        self.assertEqual(requests, ["https://registry.npmjs.org/sample/latest"])

    def test_catalog_without_optional_native_apps_can_update_all(self):
        candidate = version_catalog.resolve_catalog(
            catalog(), None, lambda url: {"version": "1.1.0"}, lambda url: self.fail()
        )
        self.assertEqual(candidate["developer"]["npm"]["sample"], "1.1.0")

    def test_lagging_release_does_not_downgrade_and_empty_selection_has_no_io(self):
        before = catalog()
        candidate = version_catalog.resolve_catalog(
            before,
            {"sample"},
            lambda url: {"version": "0.9.0"},
            lambda url: self.fail(),
        )
        self.assertEqual(candidate, before)
        self.assertEqual(
            version_catalog.resolve_catalog(
                before, set(), lambda url: self.fail(), lambda url: self.fail()
            ),
            before,
        )

    def test_source_commit_is_pinned_with_archive_hash(self):
        before = catalog()
        before["skills"]["custom"] = {
            "repository": "owner/custom",
            "revision": "a" * 40,
            "url": "https://codeload.github.com/owner/custom/tar.gz/" + "a" * 40,
            "sha256": "0" * 64,
            "paths": {"custom": "."},
        }
        candidate = version_catalog.resolve_catalog(
            before, {"custom"}, lambda url: [{"sha": "b" * 40}], lambda url: b"archive"
        )
        self.assertEqual(candidate["skills"]["custom"]["revision"], "b" * 40)
        self.assertEqual(
            candidate["skills"]["custom"]["sha256"],
            hashlib.sha256(b"archive").hexdigest(),
        )
        self.assertEqual(before["skills"]["custom"]["revision"], "a" * 40)

    def test_unknown_selection_fails_before_network(self):
        with self.assertRaises(ValueError):
            version_catalog.resolve_catalog(
                catalog(), {"typo"}, lambda url: self.fail(), lambda url: self.fail()
            )

    def test_memory_source_requires_published_integrity(self):
        before = catalog()
        before["skills"]["claude-mem"] = {
            "repository": "thedotmack/claude-mem",
            "revision": "a" * 40,
            "version": "1.0.0",
            "url": "https://registry.npmjs.org/old.tgz",
            "sha256": "0" * 64,
        }
        with self.assertRaisesRegex(ValueError, "integrity"):
            version_catalog.resolve_catalog(
                before,
                {"claude-mem"},
                lambda url: {
                    "version": "1.1.0",
                    "dist": {
                        "tarball": "https://registry.npmjs.org/new.tgz",
                        "integrity": "sha512-invalid",
                    },
                },
                lambda url: b"tampered",
            )


class UpdateTransactionTests(unittest.TestCase):
    def fixture(self, root):
        path = root / "checkout/config/tools.lock.json"
        path.parent.mkdir(parents=True)
        path.write_bytes(tool_updates.encoded(catalog()))
        path.chmod(0o644)
        return path, root / "home"

    def test_catalog_is_published_only_after_installation_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path, home = self.fixture(Path(temporary))
            original = path.read_bytes()

            def installer(candidate, candidate_path, *args):
                self.assertEqual(path.read_bytes(), original)
                self.assertEqual(json.loads(candidate_path.read_bytes()), candidate)
                return {"passed": True}

            report = tool_updates.apply_update(
                path, home, resolver=newer, installer=installer
            )
            self.assertEqual(
                json.loads(path.read_bytes())["developer"]["npm"]["sample"], "1.1.0"
            )
            self.assertEqual(path.stat().st_mode & 0o777, 0o644)
            self.assertEqual(report["status"], "verified")
            self.assertFalse(
                (home / ".local/state/dotfiles/updates/pending.json").exists()
            )

    def test_failed_partial_install_resumes_original_candidate_without_reresolving(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path, home = self.fixture(root)
            original = path.read_bytes()
            installed = root / "installed-version"

            def fail(candidate, *args):
                installed.write_text(candidate["developer"]["npm"]["sample"])
                raise ValueError("fixture failure after a package changed")

            with self.assertRaises(ValueError):
                tool_updates.apply_update(path, home, resolver=newer, installer=fail)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(installed.read_text(), "1.1.0")

            def resume(candidate, *args):
                self.assertEqual(candidate["developer"]["npm"]["sample"], "1.1.0")
                return {"passed": True}

            tool_updates.apply_update(
                path,
                home,
                resolver=lambda *args: self.fail(
                    "Pending candidate was resolved again"
                ),
                installer=resume,
            )
            self.assertEqual(
                json.loads(path.read_bytes())["developer"]["npm"]["sample"], "1.1.0"
            )

    def test_concurrent_catalog_edit_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            path, home = self.fixture(Path(temporary))

            def installer(*args):
                path.write_text("concurrent owner change")
                return {"passed": True}

            with self.assertRaisesRegex(ValueError, "changed during installation"):
                tool_updates.apply_update(
                    path, home, resolver=newer, installer=installer
                )
            self.assertEqual(path.read_text(), "concurrent owner change")

    def test_pending_update_rejects_a_different_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            path, home = self.fixture(Path(temporary))
            with self.assertRaises(ValueError):
                tool_updates.apply_update(
                    path,
                    home,
                    only={"sample"},
                    resolver=newer,
                    installer=lambda *args: (_ for _ in ()).throw(
                        ValueError("failure")
                    ),
                )
            with self.assertRaisesRegex(ValueError, "different update"):
                tool_updates.apply_update(
                    path,
                    home,
                    only={"other"},
                    resolver=lambda *args: self.fail(),
                    installer=lambda *args: self.fail(),
                )

    def test_check_does_not_create_home_or_modify_catalog(self):
        with tempfile.TemporaryDirectory() as temporary:
            path, home = self.fixture(Path(temporary))
            original = path.read_bytes()
            with (
                patch.object(
                    sys,
                    "argv",
                    [
                        "update-tools",
                        "--check",
                        "--catalog",
                        str(path),
                        "--only",
                        "sample",
                    ],
                ),
                patch.object(tool_updates, "resolve_catalog", newer),
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                self.assertEqual(tool_updates.main(), 0)
            self.assertIn("1.1.0", output.getvalue())
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(home.exists())

    def test_commit_publishes_only_catalog_and_preserves_other_staged_files(self):
        import subprocess

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path, home = self.fixture(root)
            checkout = path.parent.parent
            config = home / ".config/chezmoi/chezmoi.toml"
            config.parent.mkdir(parents=True)
            config.write_text("[data]\ninstall_developer_tools=true\n")

            def git(*args):
                return subprocess.check_output(
                    ["git", "-C", str(checkout), *args],
                    text=True,
                    stderr=subprocess.DEVNULL,
                )

            git("init")
            git("config", "user.name", "Update Fixture")
            git("config", "user.email", "fixture@example.invalid")
            git("config", "commit.gpgsign", "false")
            git("add", "config/tools.lock.json")
            git("commit", "-m", "fixture baseline")
            (checkout / "unrelated.txt").write_text("owner staged change")
            git("add", "unrelated.txt")

            def installed(*args, **kwargs):
                path.write_bytes(tool_updates.encoded(newer(catalog(), None)))
                return {"status": "verified", "changes": []}

            with (
                patch.object(tool_updates, "ROOT", checkout),
                patch.object(sys, "argv", ["update-tools", "--apply", "--commit"]),
                patch.object(tool_updates, "require_supported_host"),
                patch.object(tool_updates, "apply_update", installed),
                patch.object(Path, "home", return_value=home),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(tool_updates.main(), 0)
            self.assertEqual(
                git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").strip(),
                "config/tools.lock.json",
            )
            self.assertEqual(
                git("diff", "--cached", "--name-only").strip(), "unrelated.txt"
            )
            self.assertNotIn("Co-authored-by", git("log", "-1", "--format=%B"))
