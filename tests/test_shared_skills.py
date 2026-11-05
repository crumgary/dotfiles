"""Shared skill source validation and app discovery integration."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from provision.shared_skills import activate_shared_skills
from provision.tool_bundle import tree_digest


class SharedSkillTests(unittest.TestCase):
    def source(self, home, revision="one", relative="skills/example"):
        root = home / ".local/share/dotfiles/skill-sources/bundle" / revision
        directory = root / relative
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text("Example\n")
        (root / "reference.md").write_text("Sibling resource\n")
        (root / ".dotfiles-source.json").write_text(
            json.dumps({"tree": tree_digest(root)})
        )
        return root

    def activate(self, home, root, relative="skills/example", selected=()):
        return activate_shared_skills(
            home,
            selected,
            {"bundle": root},
            {"bundle": {"paths": {"example": relative}}, "tstack": {}},
        )

    def test_all_app_links_are_idempotent_and_retain_siblings(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            root = self.source(home)
            selected = ("claude", "codex", "opencode", "antigravity")
            self.assertEqual(self.activate(home, root, selected=selected), ["example"])
            canonical = home / ".agents/skills/example"
            before = canonical.lstat().st_mtime_ns
            self.activate(home, root, selected=selected)
            self.assertEqual(before, canonical.lstat().st_mtime_ns)
            self.assertEqual(canonical.resolve(), root / "skills/example")
            self.assertTrue((canonical / "../../reference.md").is_file())
            for directory in (".claude/skills", ".gemini/config/skills"):
                self.assertEqual(
                    (home / directory / "example").resolve(), canonical.resolve()
                )

    def test_advances_only_verified_owned_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            first = self.source(home)
            self.activate(home, first, selected=("claude",))
            second = self.source(home, "two")
            self.activate(home, second, selected=("claude",))
            self.assertEqual(
                (home / ".claude/skills/example").resolve(), second / "skills/example"
            )
            (second / "reference.md").write_text("Local edit")
            with self.assertRaises(ValueError):
                self.activate(home, first)
            self.assertEqual(
                (home / ".agents/skills/example").resolve(), second / "skills/example"
            )

    def test_local_skill_conflict_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            root = self.source(home)
            local = home / ".agents/skills/example"
            local.mkdir(parents=True)
            (local / "SKILL.md").write_text("Private skill")
            with self.assertRaisesRegex(ValueError, "Conflicting"):
                self.activate(home, root)
            self.assertEqual((local / "SKILL.md").read_text(), "Private skill")

    def test_rejects_escape_and_absolute_paths_before_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            root = self.source(home)
            for path in ("../skills/example", "/tmp", "skills\\example"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    self.activate(home, root, path)
            self.assertFalse((home / ".agents").exists())

    def test_rejects_external_source_and_missing_skill(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            root = self.source(home)
            with self.assertRaises(ValueError):
                self.activate(home, home)
            with self.assertRaisesRegex(ValueError, "SKILL.md"):
                self.activate(home, root, "missing")

    def test_repository_root_skill_and_unselected_apps(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            root = self.source(home, relative=".")
            self.activate(home, root, ".", selected=("codex",))
            self.assertEqual((home / ".agents/skills/example").resolve(), root)
            self.assertFalse((home / ".claude").exists())
            self.assertFalse((home / ".gemini").exists())


if __name__ == "__main__":
    unittest.main()
