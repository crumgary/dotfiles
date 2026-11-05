"""Configure RTK through its supported initializers without editing shared rules."""

import hashlib
import json
import subprocess
from pathlib import Path


def configure_rtk(home: Path, selected) -> dict:
    codex_rules = home / ".codex/AGENTS.md"
    if "codex" in selected:
        reference = "@" + str(home / ".codex/RTK.md")
        if codex_rules.is_symlink() or not codex_rules.is_file():
            raise ValueError("Codex RTK requires its managed regular instruction file")
        if reference not in codex_rules.read_text().splitlines():
            raise ValueError("Apply the managed Codex RTK instruction reference first")
    if "opencode" in selected and "claude" not in selected:
        raise ValueError("RTK OpenCode initializer also requires selecting Claude")
    protected = [home / ".config/agents/AGENTS.md", codex_rules]
    before = {path: path.read_bytes() for path in protected if path.is_file()}
    commands = []
    expected = []
    if "claude" in selected:
        flags = ["--opencode"] if "opencode" in selected else ["--agent", "claude"]
        commands.append(flags + ["--hook-only", "--auto-patch", "--no-trust-filters"])
        expected.append(home / ".claude/settings.json")
    if "opencode" in selected:
        expected.append(home / ".config/opencode/plugins/rtk.ts")
    if "antigravity" in selected:
        commands.append(
            [
                "--agent",
                "antigravity",
                "--hook-only",
                "--auto-patch",
                "--no-trust-filters",
            ]
        )
        expected += [
            home / ".gemini/config/plugins/rtk/hooks.json",
            home / ".gemini/config/plugins/rtk/plugin.json",
        ]
    if "codex" in selected:
        commands.append(["--codex"])
        expected += [home / ".codex/RTK.md", home / ".codex/hooks.json"]
    rtk = home / ".local/bin/rtk"
    version = subprocess.check_output([str(rtk), "--version"], text=True).strip()
    receipt = home / ".local/state/dotfiles/rtk-setup.json"

    def state():
        return {
            str(path.relative_to(home)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in expected
            if path.is_file()
        }

    desired = {"version": version, "apps": sorted(selected), "files": state()}
    if (
        receipt.is_file()
        and len(desired["files"]) == len(expected)
        and json.loads(receipt.read_text()) == desired
    ):
        return desired
    for flags in commands:
        subprocess.run([str(rtk), "init", "-g", *flags], check=True)
        for path, contents in before.items():
            if path.read_bytes() != contents:
                raise ValueError(
                    "RTK unexpectedly changed managed instructions: " + str(path)
                )
    missing = [str(path) for path in expected if not path.is_file()]
    if missing:
        raise ValueError(
            "RTK initializer did not create expected files: " + ", ".join(missing)
        )
    desired["files"] = state()
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(desired, indent=2) + "\n")
    return desired
