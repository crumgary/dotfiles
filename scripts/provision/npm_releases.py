"""Check published dependency graphs without installing or running package scripts."""

import json
import re
import subprocess
import tempfile
from pathlib import Path


class UnavailableNpmRelease(ValueError):
    """The registry cannot currently resolve a required package/version."""


def check_npm_release(package, version, registry=None):
    with tempfile.TemporaryDirectory(prefix="dotfiles-npm-check-") as temporary:
        root = Path(temporary)
        (root / "package.json").write_text(
            json.dumps(
                {
                    "name": "dotfiles-release-check",
                    "version": "0.0.0",
                    "private": True,
                    "dependencies": {package: version},
                }
            )
        )
        command = [
            "npm",
            "install",
            "--global=false",
            "--workspaces=false",
            "--update-notifier=false",
            "--package-lock-only",
            "--ignore-scripts",
            "--no-audit",
            "--no-fund",
            "--json",
            "--prefer-online",
            "--fetch-retries=0",
            "--fetch-timeout=20000",
            "--cache",
            str(root / "cache"),
        ]
        if registry:
            command += ["--registry", registry]
        result = subprocess.run(
            command, cwd=root, capture_output=True, text=True, check=False, timeout=120
        )
        if result.returncode == 0:
            return
        try:
            code = json.loads(result.stdout).get("error", {}).get("code")
        except (ValueError, AttributeError):
            code = None
        if not code:
            match = re.search(r"(?m)^npm (?:error|ERR!) code (\w+)", result.stderr)
            code = match[1] if match else "UNKNOWN"
        if code in {"ETARGET", "E404"}:
            raise UnavailableNpmRelease(
                f"{package}@{version} has an unavailable required dependency ({code})"
            )
        raise ValueError(
            f"Npm dependency check failed for {package}@{version} ({code}); no packages were installed"
        )


def validate_npm_updates(candidate, approved, checker=None):
    checker = checker or check_npm_release
    for package, version in candidate["developer"]["npm"].items():
        if version != approved["developer"]["npm"].get(package):
            checker(package, version)
    for name, entry in candidate["agents"].items():
        previous = approved["agents"].get(name, {})
        if entry["kind"] == "npm" and entry["version"] != previous.get("version"):
            checker(entry["package"], entry["version"])

    memory = candidate["skills"].get("claude-mem")
    previous = approved["skills"].get("claude-mem", {})
    if memory and memory["version"] != previous.get("version"):
        checker("claude-mem", memory["version"])
