"""Resolve real archive bytes against controlled official release metadata."""

import copy
import hashlib
import io
import json
import sys
import tarfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from provision.version_artifacts import resolve_artifacts


def tar_payload(member, data=b"new binary", symlink=False):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        info = tarfile.TarInfo(member)
        info.size = len(data)
        if symlink:
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
        archive.addfile(info, io.BytesIO(data))
    return stream.getvalue()


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(
            (Path(__file__).resolve().parents[1] / "config/tools.lock.json").read_text()
        )
        self.original = copy.deepcopy(self.catalog)
        self.json = {}
        self.blobs = {}

    def resolve(self, *names):
        return resolve_artifacts(
            self.catalog, self.json.__getitem__, self.blobs.__getitem__, only=set(names)
        )

    def github(self, repo, tag, name, blob, **fields):
        url = f"https://github.com/{repo}/releases/download/{tag}/{name}"
        asset = {
            "name": name,
            "browser_download_url": url,
            "digest": "sha256:" + hashlib.sha256(blob).hexdigest(),
        }
        self.json[f"https://api.github.com/repos/{repo}/releases/latest"] = {
            "tag_name": tag,
            "prerelease": False,
            "draft": False,
            "assets": [asset],
            **fields,
        }
        self.blobs[url] = blob
        return asset

    def test_updates_archive_and_binary_hash_without_mutating_input(self):
        blob = tar_payload("actionlint")
        self.github(
            "rhysd/actionlint", "v1.8.0", "actionlint_1.8.0_linux_amd64.tar.gz", blob
        )
        candidate = self.resolve("actionlint")
        entry = candidate["developer"]["binaries"]["actionlint"]
        self.assertEqual(entry["version"], "1.8.0")
        self.assertEqual(entry["sha256"], hashlib.sha256(blob).hexdigest())
        self.assertEqual(
            entry["binary_sha256"], hashlib.sha256(b"new binary").hexdigest()
        )
        self.assertEqual(
            set(entry), set(self.catalog["developer"]["binaries"]["actionlint"])
        )
        self.assertEqual(self.catalog, self.original)

    def test_unchanged_or_older_release_never_downloads(self):
        for version in ("v1.1.0", "v1.0.99"):
            self.github("rtk-ai/rtk", version, "unused", b"")
            self.blobs.clear()
            self.assertEqual(self.resolve("rtk"), self.catalog)

    def test_prerelease_or_draft_never_selected(self):
        for fields in (
            {"prerelease": True},
            {"draft": True},
            {"tag_name": "v9.0.0-rc.1"},
        ):
            self.github("rtk-ai/rtk", "v9.0.0", "unused", b"", **fields)
            self.assertEqual(self.resolve("rtk"), self.catalog)

    def test_rejects_tampered_release_asset(self):
        asset = self.github(
            "rtk-ai/rtk",
            "v2.0.0",
            "rtk-x86_64-unknown-linux-musl.tar.gz",
            tar_payload("rtk"),
        )
        asset["digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.resolve("rtk")

    def test_keeps_uv_gnu_asset_family(self):
        self.github(
            "astral-sh/uv",
            "0.14.0",
            "uv-x86_64-unknown-linux-gnu.tar.gz",
            tar_payload("uv-x86_64-unknown-linux-gnu/uv"),
        )
        result = self.resolve("uv")["developer"]["binaries"]["uv"]
        self.assertEqual(result["version"], "0.14.0")
        self.assertIn("linux-gnu.tar.gz", result["url"])

    def test_checks_checksum_file_when_asset_digest_unavailable(self):
        asset = self.github(
            "rtk-ai/rtk",
            "v2.0.0",
            "rtk-x86_64-unknown-linux-musl.tar.gz",
            tar_payload("rtk"),
        )
        asset.pop("digest")
        self.json["https://api.github.com/repos/rtk-ai/rtk/releases/latest"][
            "assets"
        ].append(
            {
                "name": "checksums.txt",
                "browser_download_url": "https://github.com/checksums",
            }
        )
        self.blobs["https://github.com/checksums"] = (
            "0" * 64 + "  " + asset["name"]
        ).encode()
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.resolve("rtk")

    def test_archive_symlink_member_rejected(self):
        self.github(
            "rtk-ai/rtk",
            "v2.0.0",
            "rtk-x86_64-unknown-linux-musl.tar.gz",
            tar_payload("rtk", symlink=True),
        )
        with self.assertRaisesRegex(ValueError, "regular"):
            self.resolve("rtk")

    def test_bun_uses_baseline_zip(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("bun-linux-x64-baseline/bun", b"bun binary")
        self.github(
            "oven-sh/bun", "bun-v1.5.0", "bun-linux-x64-baseline.zip", buffer.getvalue()
        )
        entry = self.resolve("bun")["skills"]["claude-mem"]["bun"]
        self.assertEqual(entry["version"], "1.5.0")
        self.assertEqual(
            entry["binary_sha256"], hashlib.sha256(b"bun binary").hexdigest()
        )

    def test_claude_manifest_and_parent_version_stay_consistent(self):
        root = "https://downloads.claude.ai/claude-code-releases"
        self.blobs[root + "/latest"] = b"2.2.0\n"
        self.blobs[root + "/2.2.0/linux-x64/claude"] = b"claude binary"
        self.json[root + "/2.2.0/manifest.json"] = {
            "version": "2.2.0",
            "platforms": {
                "linux-x64": {
                    "binary": "claude",
                    "checksum": hashlib.sha256(b"claude binary").hexdigest(),
                }
            },
        }
        entry = self.resolve("claude")["agents"]["claude"]
        self.assertEqual(entry["version"], "2.2.0")
        self.assertEqual(entry["artifact"]["version"], "2.2.0")
        self.assertEqual(
            entry["artifact"]["sha256"], entry["artifact"]["binary_sha256"]
        )

    def test_claude_same_or_older_channel_retains_pin_without_artifact_io(self):
        for version in ("2.1.318", "2.1.317", "3.0.0-beta.1"):
            self.blobs["https://downloads.claude.ai/claude-code-releases/latest"] = (
                version.encode()
            )
            self.assertEqual(self.resolve("claude"), self.catalog)

    def test_empty_selection_does_no_network_io_and_returns_independent_copy(self):
        candidate = self.resolve()
        candidate["developer"]["binaries"]["rtk"]["version"] = "9.9.9"
        self.assertEqual(self.catalog, self.original)

    def test_rejects_github_asset_url_from_different_tag(self):
        asset = self.github(
            "rtk-ai/rtk",
            "v2.0.0",
            "rtk-x86_64-unknown-linux-musl.tar.gz",
            tar_payload("rtk"),
        )
        asset["browser_download_url"] = asset["browser_download_url"].replace(
            "v2.0.0", "v1.0.0"
        )
        with self.assertRaisesRegex(ValueError, "URL"):
            self.resolve("rtk")

    def test_claude_rejects_mismatched_manifest_version(self):
        root = "https://downloads.claude.ai/claude-code-releases"
        self.blobs[root + "/latest"] = b"2.2.0"
        self.json[root + "/2.2.0/manifest.json"] = {"version": "2.1.0"}
        with self.assertRaisesRegex(ValueError, "version"):
            self.resolve("claude")

    def test_agy_uses_immutable_url_and_verifies_sha512(self):
        root = "https://antigravity-cli-auto-updater-974169037036.us-central1.run.app"
        self.blobs["https://antigravity.google/cli/install.sh"] = (
            f'DOWNLOAD_BASE_URL="{root}"'.encode()
        )
        url = "https://storage.googleapis.com/antigravity-public/antigravity-cli/1.6.0-1234/linux-x64/cli_linux_x64.tar.gz"
        blob = tar_payload("antigravity")
        self.json[root + "/manifests/linux_amd64.json"] = {
            "version": "1.6.0",
            "url": url,
            "sha512": hashlib.sha512(blob).hexdigest(),
        }
        self.blobs[url] = blob
        entry = self.resolve("antigravity")["agents"]["antigravity"]
        self.assertEqual(entry["version"], "1.6.0")
        self.assertEqual(entry["artifact"]["url"], url)
        self.json[root + "/manifests/linux_amd64.json"]["sha512"] = "0" * 128
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.resolve("antigravity")


if __name__ == "__main__":
    unittest.main()
