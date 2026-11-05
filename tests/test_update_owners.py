"""Update ownership settings and direct-exec native wrapper behavior."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from provision import update_owners


class UpdateOwnerTests(unittest.TestCase):
    payload = b'#!/bin/sh\nprintf "%s:%s" "$AGY_CLI_DISABLE_AUTO_UPDATE" "$1"\n'

    def entry(self):
        return {
            "command": "agy",
            "managed_binary": "agy-native",
            "kind": "native",
            "update_owner": "dotfiles",
            "artifact": {"binary_sha256": hashlib.sha256(self.payload).hexdigest()},
        }

    def put(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o755)

    def test_migrates_verified_native_and_direct_exec_disables_updater(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            public = home / ".local/bin/agy"
            self.put(public, self.payload)
            native = update_owners.prepare_native_app(home, "antigravity", self.entry())
            self.assertEqual(native, home / ".local/bin/agy-native")
            self.assertEqual(native.read_bytes(), self.payload)
            result = subprocess.run(
                [str(public), "--version"], capture_output=True, text=True, check=True
            )
            self.assertEqual(result.stdout, "true:--version")
            stamp = public.stat().st_mtime_ns
            update_owners.prepare_native_app(home, "antigravity", self.entry())
            self.assertEqual(public.stat().st_mtime_ns, stamp)
            self.assertEqual(
                update_owners.wrapper_hashes(home, {"antigravity": self.entry()}),
                {"antigravity": hashlib.sha256(public.read_bytes()).hexdigest()},
            )

    def test_previous_owned_native_can_migrate_and_same_candidate_retry_is_safe(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            public = home / ".local/bin/agy"
            previous = self.payload + b"# previous\n"
            self.put(public, previous)
            receipt = home / ".local/state/dotfiles/agent-apps.json"
            receipt.parent.mkdir(parents=True)
            receipt.write_text(
                json.dumps(
                    {
                        "native_hashes": {
                            "antigravity": hashlib.sha256(previous).hexdigest()
                        }
                    }
                )
            )
            native = update_owners.prepare_native_app(home, "antigravity", self.entry())
            self.assertEqual(native.read_bytes(), previous)
            self.put(native, self.payload)
            self.put(public, self.payload)
            update_owners.prepare_native_app(home, "antigravity", self.entry())
            self.assertEqual(native.read_bytes(), self.payload)

    def test_unknown_native_modified_wrapper_and_symlink_are_preserved(self):
        for contents in (b"user program", None):
            with (
                self.subTest(contents=contents),
                tempfile.TemporaryDirectory() as temporary,
            ):
                home = Path(temporary)
                public = home / ".local/bin/agy"
                self.put(public, contents or self.payload)
                if contents is None:
                    public.unlink()
                    public.symlink_to("custom")
                with self.assertRaises((ValueError, TypeError)):
                    update_owners.prepare_native_app(home, "antigravity", self.entry())
                self.assertTrue(
                    public.is_symlink()
                    if contents is None
                    else public.read_bytes() == contents
                )
                self.assertFalse((home / ".local/bin/agy-native").exists())
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            update_owners.prepare_native_app(home, "antigravity", self.entry())
            public = home / ".local/bin/agy"
            public.write_text("custom wrapper")
            with self.assertRaises((ValueError, TypeError)):
                update_owners.prepare_native_app(home, "antigravity", self.entry())
            self.assertEqual(public.read_text(), "custom wrapper")

    def test_conflicting_native_destinations_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            public, native = home / ".local/bin/agy", home / ".local/bin/agy-native"
            self.put(public, self.payload)
            self.put(native, b"unknown")
            with self.assertRaises((ValueError, TypeError)):
                update_owners.prepare_native_app(home, "antigravity", self.entry())
            self.assertEqual(public.read_bytes(), self.payload)
            self.assertEqual(native.read_bytes(), b"unknown")

    def test_receipt_owned_wrapper_can_advance_but_native_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            public = home / ".local/bin/agy"
            self.put(public, b"old generated wrapper")
            receipt = home / ".local/state/dotfiles/agent-apps.json"
            receipt.parent.mkdir(parents=True)
            receipt.write_text(
                json.dumps(
                    {
                        "native_wrapper_hashes": {
                            "antigravity": hashlib.sha256(
                                public.read_bytes()
                            ).hexdigest()
                        }
                    }
                )
            )
            update_owners.prepare_native_app(home, "antigravity", self.entry())
            self.assertIn(b"AGY_CLI_DISABLE_AUTO_UPDATE=true", public.read_bytes())
            native = home / ".local/bin/agy-native"
            native.symlink_to("unknown")
            before = public.read_bytes()
            with self.assertRaises((ValueError, TypeError)):
                update_owners.prepare_native_app(home, "antigravity", self.entry())
            self.assertTrue(native.is_symlink())
            self.assertEqual(public.read_bytes(), before)

    def test_default_native_path_is_pure(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            entry = {"command": "claude", "kind": "claude-native"}
            self.assertEqual(
                update_owners.native_binary(home, entry), home / ".local/bin/claude"
            )
            self.assertEqual(
                update_owners.prepare_native_app(home, "claude", entry),
                home / ".local/bin/claude",
            )
            self.assertEqual(list(home.iterdir()), [])

    def test_config_preserves_unrelated_settings_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            claude = home / ".claude/settings.json"
            opencode = home / ".config/opencode/opencode.json"
            self.put(claude, b'{"env":{"KEEP":"yes"},"hooks":{"custom":[]}}')
            self.put(opencode, b'{"model":"custom","autoupdate":true}')
            selected = {
                name: {"update_owner": "dotfiles"}
                for name in ("claude", "opencode", "codex")
            }
            update_owners.configure_update_owners(home, selected)
            self.assertEqual(
                json.loads(claude.read_text()),
                {
                    "env": {"KEEP": "yes", "DISABLE_AUTOUPDATER": "1"},
                    "hooks": {"custom": []},
                },
            )
            self.assertEqual(
                json.loads(opencode.read_text()),
                {"model": "custom", "autoupdate": False},
            )
            stamps = [p.stat().st_mtime_ns for p in (claude, opencode)]
            update_owners.configure_update_owners(home, selected)
            self.assertEqual([p.stat().st_mtime_ns for p in (claude, opencode)], stamps)

    def test_unowned_selection_does_not_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            update_owners.configure_update_owners(
                home, {"claude": {}, "opencode": {"update_owner": "user"}}
            )
            self.assertEqual(list(home.iterdir()), [])

    def test_jsonc_and_wrong_type_opencode_preflight_prevent_partial_writes(self):
        for payload in (b"[]", b"// comment\n{}"):
            with (
                self.subTest(payload=payload),
                tempfile.TemporaryDirectory() as temporary,
            ):
                home = Path(temporary)
                config = home / ".config/opencode/opencode.json"
                self.put(config, payload)
                with self.assertRaises((ValueError, TypeError)):
                    update_owners.configure_update_owners(
                        home,
                        {
                            name: {"update_owner": "dotfiles"}
                            for name in ("claude", "opencode")
                        },
                    )
                self.assertFalse((home / ".claude/settings.json").exists())
                self.assertEqual(config.read_bytes(), payload)
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            config = home / ".config/opencode/opencode.jsonc"
            self.put(config, b"{}")
            with self.assertRaises((ValueError, TypeError)):
                update_owners.configure_update_owners(
                    home, {"opencode": {"update_owner": "dotfiles"}}
                )
            self.assertFalse(config.with_suffix(".json").exists())

    def test_invalid_config_is_rejected_without_writes(self):
        for payload in (b"[]", b'{"env":[]}', b'{//comment\n"env":{}}'):
            with (
                self.subTest(payload=payload),
                tempfile.TemporaryDirectory() as temporary,
            ):
                home = Path(temporary)
                config = home / ".claude/settings.json"
                self.put(config, payload)
                with self.assertRaises((ValueError, TypeError)):
                    update_owners.configure_update_owners(
                        home, {"claude": {"update_owner": "dotfiles"}}
                    )
                self.assertEqual(config.read_bytes(), payload)
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            target = home / "user.json"
            target.write_text("{}")
            config = home / ".config/opencode/opencode.json"
            config.parent.mkdir(parents=True)
            config.symlink_to(target)
            with self.assertRaises((ValueError, TypeError)):
                update_owners.configure_update_owners(
                    home, {"opencode": {"update_owner": "dotfiles"}}
                )
            self.assertEqual(target.read_text(), "{}")


if __name__ == "__main__":
    unittest.main()
