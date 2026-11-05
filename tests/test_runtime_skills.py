"""Native skill generation must preserve unknown and edited local skills."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from provision.runtime_skills import configure_runtime_skills
from provision.tool_bundle import tree_digest


class RuntimeSkillTests(unittest.TestCase):
    def test_unknown_native_skill_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            skill = home / ".agents/skills/graphify"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("custom skill")
            with patch("provision.runtime_skills.subprocess.run") as run:
                with self.assertRaises(ValueError):
                    configure_runtime_skills(
                        home, {"codex"}, {"graphifyy": {"version": "1"}}
                    )
                run.assert_not_called()
            self.assertEqual((skill / "SKILL.md").read_text(), "custom skill")

    def test_repeat_preserves_native_skill_and_observer_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            skill = home / ".agents/skills/graphify"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("native skill")
            receipt = home / ".local/state/dotfiles/runtime-skills.json"
            receipt.parent.mkdir(parents=True)
            receipt.write_text(
                json.dumps({"version": "1", "tree": tree_digest(skill)}, indent=2)
                + "\n"
            )
            with patch("provision.runtime_skills.subprocess.run") as run:
                configure_runtime_skills(
                    home, {"claude", "antigravity"}, {"graphifyy": {"version": "1"}}
                )
                log = (
                    home
                    / ".local/state/agent-observer/skill-observations/observation-log/0001-test.md"
                )
                log.write_text("existing observation")
                before = {
                    p: (p.read_bytes(), p.stat().st_mtime_ns)
                    for p in (receipt, log, skill / "SKILL.md")
                }
                configure_runtime_skills(
                    home, {"claude", "antigravity"}, {"graphifyy": {"version": "1"}}
                )
                run.assert_not_called()
            self.assertEqual(
                before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}
            )
            self.assertTrue((home / ".claude/skills/graphify").is_symlink())
