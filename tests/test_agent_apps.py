"""App selection and safe shared skill adapters."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AgentAppTests(unittest.TestCase):
    def module(self):
        spec = importlib.util.spec_from_file_location(
            "agent_apps", ROOT / "scripts/provision/skill_adapters.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(ROOT / "scripts"))
        spec.loader.exec_module(module)
        return module

    def test_dry_run_declares_only_selected_apps_and_node26(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "new-home"
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/install-tools"),
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
            data = json.loads(result.stdout)
            self.assertEqual(
                set(data["apps"]), {"claude", "codex", "opencode", "antigravity"}
            )
            self.assertEqual(data["runtime_major"], 26)
            self.assertFalse(home.exists())

    def test_unknown_app_is_rejected_before_writes(self):
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts/install-tools"),
                "--dry-run",
                "--apps",
                "unrequested",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)

    def test_skill_adapter_is_idempotent_and_preserves_conflicting_content(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources/example"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text(
                "---\nname: example\ndescription: fixture\n---\n"
            )
            destination = root / "skills/example"
            module.ensure_link(destination, source)
            before = destination.lstat().st_mtime_ns
            module.ensure_link(destination, source)
            self.assertEqual(destination.lstat().st_mtime_ns, before)
            destination.unlink()
            destination.mkdir()
            (destination / "custom").write_text("preserve")
            with self.assertRaises(ValueError):
                module.ensure_link(destination, source)
            self.assertEqual((destination / "custom").read_text(), "preserve")

    def test_opencode_adapter_does_not_modify_symlinked_custom_config(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            original = home / "custom.json"
            original.write_text('{"custom":"preserve"}')
            config = home / ".config/opencode/opencode.json"
            config.parent.mkdir(parents=True)
            config.symlink_to(original)
            source = home / "sources/superpowers"
            (source / ".claude-plugin").mkdir(parents=True)
            (source / ".claude-plugin/plugin.json").write_text('{"version":"7.0.2"}')
            with self.assertRaises(ValueError):
                module.register_superpowers(home, {"opencode"}, source)
            self.assertEqual(original.read_text(), '{"custom":"preserve"}')

    def test_newer_installed_app_is_not_silently_downgraded(self):
        import os
        from unittest.mock import patch

        sys.path.insert(0, str(ROOT / "scripts"))
        from provision import agent_apps

        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            commands = home / ".local/bin"
            commands.mkdir(parents=True)
            (commands / "codex").write_text('#!/bin/sh\nprintf "codex-cli 99.0.0\n"\n')
            (commands / "codex").chmod(0o755)
            marker = home / "npm-ran"
            (commands / "npm").write_text(
                '#!/bin/sh\ntouch "' + str(marker) + '"\nexit 88\n'
            )
            (commands / "npm").chmod(0o755)
            with (
                patch.dict(os.environ, {"PATH": str(commands) + ":/usr/bin:/bin"}),
                self.assertRaisesRegex(ValueError, "newer"),
            ):
                agent_apps.install_app(
                    home,
                    "codex",
                    {
                        "command": "codex",
                        "version": "0.166.0",
                        "kind": "npm",
                        "package": "@openai/codex",
                    },
                )
            self.assertFalse(marker.exists())

    def test_native_version_text_cannot_bypass_declared_hash(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from provision import agent_apps

        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            binary = home / ".local/bin/agy"
            binary.parent.mkdir(parents=True)
            binary.write_text('#!/bin/sh\nprintf "1.5.0\n"\n')
            binary.chmod(0o755)
            with self.assertRaisesRegex(ValueError, "integrity"):
                agent_apps.install_app(
                    home,
                    "antigravity",
                    {
                        "command": "agy",
                        "version": "1.5.0",
                        "kind": "native",
                        "artifact": {"binary_sha256": "0" * 64},
                    },
                )

    def test_verified_owned_link_can_advance_without_overwriting_custom_sources(self):
        module = self.module()
        from provision.tool_bundle import tree_digest

        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            vault = home / "skill-sources/tstack"
            for revision in ("old", "new"):
                source = vault / revision
                (source / "skills/example").mkdir(parents=True)
                (source / "skills/example/SKILL.md").write_text(
                    "---\nname: example\ndescription: fixture\n---\n"
                )
                (source / ".dotfiles-source.json").write_text(
                    json.dumps({"tree": tree_digest(source)})
                )
            destination = home / "skills/example"
            module.ensure_link(destination, vault / "old/skills/example")
            module.ensure_link(
                destination, vault / "new/skills/example", owned_root=vault
            )
            self.assertEqual(destination.resolve(), vault / "new/skills/example")
            (vault / "new/skills/example/SKILL.md").write_text("custom edits")
            with self.assertRaises(ValueError):
                module.ensure_link(
                    destination, vault / "old/skills/example", owned_root=vault
                )
            self.assertEqual(destination.resolve(), vault / "new/skills/example")

    def test_same_version_plugin_with_modified_skill_is_rejected(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source/skills/example"
            cache = root / "cache/skills/example"
            source.mkdir(parents=True)
            cache.mkdir(parents=True)
            (source / "SKILL.md").write_text("pinned instructions")
            (cache / "SKILL.md").write_text("different same-version instructions")
            with self.assertRaisesRegex(ValueError, "differs"):
                module.verify_plugin_files(root / "cache", root / "source")

    def test_declared_native_upgrade_accepts_only_previous_owned_binary(self):
        import hashlib
        import io
        import tarfile

        sys.path.insert(0, str(ROOT / "scripts"))
        from provision import agent_apps

        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            binary = home / ".local/bin/agy"
            binary.parent.mkdir(parents=True)
            old = b'#!/bin/sh\nprintf "1.4.0\\n"\n'
            new = b'#!/bin/sh\nprintf "1.5.0\\n"\n'
            binary.write_bytes(old)
            binary.chmod(0o755)
            receipt = home / ".local/state/dotfiles/agent-apps.json"
            receipt.parent.mkdir(parents=True)
            receipt.write_text(
                json.dumps(
                    {"native_hashes": {"antigravity": hashlib.sha256(old).hexdigest()}}
                )
            )
            archive_path = home / "new.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                member = tarfile.TarInfo("antigravity")
                member.size = len(new)
                archive.addfile(member, io.BytesIO(new))
            entry = {
                "command": "agy",
                "version": "1.5.0",
                "kind": "native",
                "artifact": {
                    "url": archive_path.as_uri(),
                    "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
                    "member": "antigravity",
                    "binary_sha256": hashlib.sha256(new).hexdigest(),
                },
            }
            agent_apps.install_app(home, "antigravity", entry)
            self.assertEqual(binary.read_bytes(), new)

    def test_codex_rtk_preflight_protects_shared_instructions(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from provision import rtk_setup

        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            shared = home / ".config/agents/AGENTS.md"
            shared.parent.mkdir(parents=True)
            shared.write_text("shared source must remain unchanged")
            codex = home / ".codex/AGENTS.md"
            codex.parent.mkdir(parents=True)
            codex.symlink_to(shared)
            with self.assertRaises(ValueError):
                rtk_setup.configure_rtk(home, {"codex"})
            self.assertEqual(shared.read_text(), "shared source must remain unchanged")

    def test_fresh_claude_install_verifies_installed_binary_after_bootstrap_cleanup(
        self,
    ):
        import hashlib
        import os
        from unittest.mock import patch

        from provision import agent_apps

        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            payload = b"""#!/bin/sh
if [ "$1" = install ]; then
    mkdir -p "$DOTFILES_FIXTURE_HOME/.local/bin"
    cp "$0" "$DOTFILES_FIXTURE_HOME/.local/bin/claude"
    chmod 755 "$DOTFILES_FIXTURE_HOME/.local/bin/claude"
else
    printf '2.1.318 (Claude Code)\\n'
fi
"""
            bootstrap = home / "bootstrap"
            bootstrap.write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            with patch.dict(os.environ, {"DOTFILES_FIXTURE_HOME": str(home)}):
                agent_apps.install_app(
                    home,
                    "claude",
                    {
                        "command": "claude",
                        "version": "2.1.318",
                        "kind": "claude-native",
                        "artifact": {
                            "url": bootstrap.as_uri(),
                            "sha256": digest,
                            "binary_sha256": digest,
                        },
                    },
                )
            self.assertEqual((home / ".local/bin/claude").read_bytes(), payload)

    def test_modified_root_mcp_and_dependency_manifests_are_rejected(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, installed = root / "source", root / "installed"
            source.mkdir()
            installed.mkdir()
            for name in (".mcp.json", "package.json", "bun.lock"):
                (source / name).write_text("pinned")
                (installed / name).write_text("pinned")
            module.verify_plugin_files(installed, source)
            for name in (".mcp.json", "package.json", "bun.lock"):
                with self.subTest(name=name):
                    (installed / name).write_text("changed executable configuration")
                    with self.assertRaises(ValueError):
                        module.verify_plugin_files(installed, source)
                    (installed / name).write_text("pinned")
