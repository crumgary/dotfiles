"""Initialize native-generated skills and local observation storage."""

import json
import subprocess
from pathlib import Path

from provision.skill_adapters import ensure_link
from provision.tool_bundle import tree_digest


def configure_runtime_skills(home: Path, selected, packages):
    version = packages["graphifyy"]["version"]
    destination = home / ".agents/skills/graphify"
    receipt = home / ".local/state/dotfiles/runtime-skills.json"
    previous = json.loads(receipt.read_text()) if receipt.is_file() else {}
    if (destination.exists() or destination.is_symlink()) and (
        destination.is_symlink() or previous.get("tree") != tree_digest(destination)
    ):
        raise ValueError(
            "Existing Graphify skill has unknown or modified content; retained"
        )
    if previous.get("version") != version or not destination.is_dir():
        subprocess.run(
            [str(home / ".local/bin/graphify"), "install", "--platform", "agents"],
            check=True,
            cwd=home,
        )
        if not (destination / "SKILL.md").is_file():
            raise ValueError("Graphify native installer did not create its skill")
    contents = (
        json.dumps({"version": version, "tree": tree_digest(destination)}, indent=2)
        + "\n"
    )
    if not receipt.is_file() or receipt.read_text() != contents:
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(contents)
    if "claude" in selected:
        ensure_link(home / ".claude/skills/graphify", destination)
    if "antigravity" in selected:
        ensure_link(home / ".gemini/config/skills/graphify", destination)
    workspace = home / ".local/state/agent-observer"
    observations = workspace / "skill-observations"
    if (observations / "log.md").exists():
        raise ValueError("Legacy task-observer log requires its native migration first")
    (observations / "observation-log/archive").mkdir(parents=True, exist_ok=True)
    (workspace / "skill-updates").mkdir(parents=True, exist_ok=True)
    initial = {
        "last-review-date.txt": "never\n",
        "cross-cutting-principles.md": "# Cross-Cutting Principles\n\nPrinciples that apply to all skills. Read as a mandatory checklist during\nany skill creation or regeneration.\n\n---\n\n## Active Principles\n",
    }
    for name, contents in initial.items():
        path = observations / name
        if not path.exists():
            path.write_text(contents)
