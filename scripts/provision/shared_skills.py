"""Expose explicitly declared, immutable skills through native app discovery."""

import re
from pathlib import Path, PurePosixPath

from provision.skill_adapters import ensure_link, source_root


def activate_shared_skills(home, selected, sources, entries):
    """Retain complete source trees so relative skill resources remain available."""
    home = Path(home)
    pending = []
    names = set()
    for bundle, entry in sorted(entries.items()):
        paths = entry.get("paths", {})
        if not paths:
            continue
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", bundle):
            raise ValueError("Invalid shared skill bundle name")
        owned = home / ".local/share/dotfiles/skill-sources" / bundle
        root = Path(sources[bundle]).resolve()
        if source_root(root, owned) != root:
            raise ValueError("Shared skill source must name its managed root")
        for name, relative in sorted(paths.items()):
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
                raise ValueError("Invalid shared skill name")
            if name in names:
                raise ValueError(f"Duplicate shared skill name: {name}")
            names.add(name)
            path = PurePosixPath(relative)
            if path.is_absolute() or ".." in path.parts or "\\" in relative:
                raise ValueError("Shared skill path must stay inside its source")
            directory = root.joinpath(*path.parts).resolve()
            if not directory.is_relative_to(root):
                raise ValueError("Shared skill path escapes its source")
            if not (directory / "SKILL.md").is_file():
                raise ValueError(f"Shared skill has no SKILL.md: {name}")
            pending.append((name, directory, owned))
    for name, directory, owned in pending:
        canonical = home / ".agents/skills" / name
        ensure_link(canonical, directory, owned_root=owned)
        if "claude" in selected:
            ensure_link(home / ".claude/skills" / name, canonical)
        if "antigravity" in selected:
            ensure_link(home / ".gemini/config/skills" / name, canonical)
    return sorted(names)
