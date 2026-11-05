"""Exercise tool-bundle planning and archive integrity without installing tools."""

import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]
CLI = SOURCE / "scripts/install-developer-tools"


class BundleTests(unittest.TestCase):
    def test_dry_run_lists_requested_tools_without_creating_home(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "absent-home"
            result = subprocess.run(
                [sys.executable, "-B", str(CLI), "--dry-run", "--home", str(home)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertEqual(
                set(plan["tools"]),
                {
                    "gh",
                    "acli",
                    "skopeo",
                    "asciinema",
                    "rtk",
                    "actionlint",
                    "gh-axi",
                    "playwright",
                    "nodejs",
                    "uv",
                    "ctx7",
                    "skills",
                    "hyperframes",
                    "chrome-devtools-axi",
                    "jira-axi",
                    "confluence-axi",
                    "ffmpeg",
                    "imagemagick",
                    "pandoc",
                    "poppler-utils",
                    "librsvg2-bin",
                },
            )
            self.assertTrue(plan["tools"]["nodejs"].startswith("26."))
            self.assertEqual(plan["skills"]["tstack"]["repository"], "crumgary/tstack")
            self.assertFalse(home.exists())

    def load_module(self):
        spec = importlib.util.spec_from_file_location(
            "tool_bundle", SOURCE / "scripts/provision/tool_bundle.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_wrong_checksum_is_rejected_before_archive_use(self):
        module = self.load_module()
        with self.assertRaises(ValueError):
            module.verify_payload(b"untrusted payload", "0" * 64)

    def test_skill_archive_cannot_escape_destination(self):
        module = self.load_module()
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            data = b"outside"
            entry = tarfile.TarInfo("repo/../../escape")
            entry.size = len(data)
            archive.addfile(entry, io.BytesIO(data))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                module.extract_source(stream.getvalue(), root / "source")
            self.assertFalse((root / "escape").exists())

    def test_skill_archive_preserves_executable_scripts(self):
        module = self.load_module()
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            data = b"#!/bin/sh\nexit 0\n"
            entry = tarfile.TarInfo("repo/skills/example/run")
            entry.mode = 0o755
            entry.size = len(data)
            archive.addfile(entry, io.BytesIO(data))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "source"
            module.extract_source(stream.getvalue(), destination)
            self.assertEqual((destination / "skills/example/run").read_bytes(), data)
            self.assertTrue((destination / "skills/example/run").stat().st_mode & 0o100)

    def test_matching_binary_with_wrong_mode_is_repaired(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            binary = home / ".local/bin/example"
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b"#!/bin/sh\nexit 0\n")
            binary.chmod(0o644)
            module.install_binary(
                home,
                "example",
                {"binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()},
            )
            self.assertEqual(binary.stat().st_mode & 0o777, 0o755)

    def test_newer_apt_package_is_an_explicit_conflict_without_downgrade(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / "sudo-executed"
            query = root / "dpkg-query"
            query.write_text('#!/bin/sh\nprintf "installed|99.0"\n')
            query.chmod(0o755)
            sudo = root / "sudo"
            sudo.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\nexit 88\n')
            sudo.chmod(0o755)
            with (
                patch.dict(os.environ, {"PATH": str(root) + ":/usr/bin:/bin"}),
                self.assertRaisesRegex(ValueError, "newer"),
            ):
                module.install_apt({"repositories": {}, "apt": {"gh": "2.103.3"}})
            self.assertFalse(marker.exists())

    def test_only_explicitly_excluded_archive_symlinks_are_omitted(self):
        module = self.load_module()
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            entry = tarfile.TarInfo("repo/CLAUDE.md")
            entry.type = tarfile.SYMTYPE
            entry.linkname = "AGENTS.md"
            archive.addfile(entry)
            content = b"skill"
            entry = tarfile.TarInfo("repo/skills/example/SKILL.md")
            entry.size = len(content)
            archive.addfile(entry, io.BytesIO(content))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "source"
            with self.assertRaises(ValueError):
                module.extract_source(stream.getvalue(), destination)
            self.assertFalse(destination.exists())
            module.extract_source(stream.getvalue(), destination, ["CLAUDE.md"])
            self.assertFalse((destination / "CLAUDE.md").exists())
            self.assertEqual(
                (destination / "skills/example/SKILL.md").read_bytes(), b"skill"
            )
