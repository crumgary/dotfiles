"""Install isolated user Python tools with uv, preserving the system interpreter."""

import json
import os
import subprocess
from pathlib import Path


def install_python_tools(home: Path, packages):
    receipt = home / ".local/state/dotfiles/python-tools.json"
    previous = json.loads(receipt.read_text()) if receipt.is_file() else {}
    uv = str(home / ".local/bin/uv")
    environment = {**os.environ, "UV_TOOL_BIN_DIR": str(home / ".local/bin")}
    for name, entry in packages.items():
        root = home / ".local/share/uv/tools" / name
        interpreter = root / "bin/python"
        actual = None
        if interpreter.is_file():
            actual = subprocess.check_output(
                [
                    str(interpreter),
                    "-c",
                    "import importlib.metadata,sys;print(importlib.metadata.version(sys.argv[1]))",
                    name,
                ],
                text=True,
            ).strip()
        ready = all(
            (home / ".local/bin" / command).is_file() for command in entry["commands"]
        )
        if actual == entry["version"] and previous.get(name) == entry and ready:
            continue
        if root.exists() and name not in previous:
            raise ValueError("Unmanaged Python tool environment retained: " + str(root))
        extras = (
            "[" + ",".join(entry.get("extras", [])) + "]" if entry.get("extras") else ""
        )
        command = [
            uv,
            "tool",
            "install",
            "--python",
            entry["python"],
            name + extras + "==" + entry["version"],
        ]
        if root.exists():
            command.append("--force")
        subprocess.run(command, check=True, env=environment)
        if not all(
            (home / ".local/bin" / command).is_file() for command in entry["commands"]
        ):
            raise ValueError("Python tool did not expose its commands: " + name)
    contents = json.dumps(packages, indent=2) + "\n"
    if not receipt.is_file() or receipt.read_text() != contents:
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(contents)
