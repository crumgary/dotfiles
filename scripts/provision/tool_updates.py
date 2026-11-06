"""Discover, validate and publish managed tool updates with resumable failures."""

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from provision.host_platform import portable_catalog, system_recipe
from provision.install_tools import configured_selection
from provision.npm_releases import UnavailableNpmRelease, validate_npm_updates
from provision.tool_bundle import require_supported_host, user_only_mode
from provision.version_catalog import changes, resolve_catalog

ROOT = Path(__file__).resolve().parents[2]


def encoded(value):
    return (json.dumps(value, indent=2) + "\n").encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic_write(path, data, mode=0o600):
    if path.is_symlink():
        raise ValueError("Symlinked update file retained: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        staged = Path(temporary.name)
        try:
            temporary.write(data)
            temporary.flush()
            os.fsync(temporary.fileno())
            staged.chmod(mode)
            staged.replace(path)
        finally:
            staged.unlink(missing_ok=True)


def install_candidate(candidate, catalog_path, home, source, only):
    """Use the same installers as normal apply; no generated caches are fabricated."""
    approved = json.loads((source / "config/tools.lock.json").read_text())
    try:
        validate_npm_updates(candidate, approved)
    except UnavailableNpmRelease as error:
        raise ValueError(
            str(error)
            + "; retry later, or use --apply --refresh to resolve a new candidate and defer unavailable releases"
        ) from error
    try:
        system = set(system_recipe(source=source)["packages"])
    except (OSError, KeyError):
        # Older checkout fixtures and frozen pre-consolidation candidates.
        system = set(candidate["developer"].get("apt", {}))
    upgrades = system if not only else set(only) & system
    if only and "node" in only:
        upgrades.add("nodejs")
    command = [
        sys.executable,
        "-B",
        str(source / "scripts/install-tools"),
        "--apply",
        "--from-chezmoi",
        "--catalog",
        str(catalog_path),
    ]
    if user_only_mode(home):
        if only and upgrades:
            raise ValueError(
                "Native tools and Node are externally managed in user-only mode; "
                "update them separately: " + ", ".join(sorted(upgrades))
            )
        command.append("--user-only")
    elif upgrades:
        command += ["--upgrade-system", ",".join(sorted(upgrades))]
    subprocess.run(command, check=True)
    return {
        "validation": "unified tool installer, local browser probe, selected app versions, skill integrity and local worker health passed"
    }


def apply_update(
    catalog_path,
    home,
    source=ROOT,
    only=None,
    resolver=resolve_catalog,
    installer=install_candidate,
    refresh=False,
):
    """Publish only a verified candidate. A failed install remains resumable."""
    catalog_path, home = Path(catalog_path), Path(home)
    if catalog_path.is_symlink():
        raise ValueError("Catalog must be a regular managed file")
    state = home / ".local/state/dotfiles/updates"
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (state / "lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Another tool update is already running") from error
        pending = state / "pending.json"
        if pending.is_symlink():
            raise ValueError("Symlinked pending update retained for review")
        before = catalog_path.read_bytes()
        old = json.loads(before)
        if pending.exists():
            record = json.loads(pending.read_text())
            if record["catalog"] != str(catalog_path.resolve()) or record[
                "only"
            ] != sorted(only or []):
                raise ValueError(
                    "A different update is pending; rerun its original selection first"
                )
            candidate = record["candidate"]
            if (
                not refresh
                and digest(before) != record["base_sha256"]
                and before != encoded(candidate)
            ):
                raise ValueError(
                    "Catalog changed since the pending update; reconcile it before retrying"
                )
            if not refresh:
                migrated = portable_catalog(candidate)
                if migrated != candidate:
                    atomic_write(
                        state / record["run"] / "legacy-candidate.json", encoded(record)
                    )
                    candidate = migrated
                    record["candidate"] = migrated
                    record["base_sha256"] = digest(before)
                    atomic_write(pending, encoded(record))
        if not pending.exists() or refresh:
            deferred = []
            candidate = (
                resolver(old, only, deferred=deferred)
                if resolver is resolve_catalog
                else resolver(old, only)
            )
            if pending.exists():
                archived = state / record["run"] / "superseded.json"
                atomic_write(
                    archived,
                    encoded({**record, "status": "superseded by explicit refresh"}),
                )
            record = {
                "schema_version": 1,
                "catalog": str(catalog_path.resolve()),
                "base_sha256": digest(before),
                "only": sorted(only or []),
                "candidate": candidate,
                "deferred": deferred,
                "run": uuid.uuid4().hex,
            }
            atomic_write(pending, encoded(record))
        workspace = state / record["run"]
        workspace.mkdir(exist_ok=True, mode=0o700)
        candidate_path = workspace / "tools.lock.json"
        atomic_write(candidate_path, encoded(candidate))
        try:
            validation = installer(candidate, candidate_path, home, source, only)
        except Exception:
            atomic_write(
                workspace / "result.json",
                encoded(
                    {
                        "status": "failed",
                        "resume": "rerun the same --apply selection",
                        "catalog_published": False,
                    }
                ),
            )
            raise
        # Protect concurrent edits made while package installation was running.
        if catalog_path.read_bytes() != before:
            raise ValueError(
                "Catalog changed during installation; validated candidate retained for reconciliation"
            )
        if before != encoded(candidate):
            atomic_write(
                catalog_path, encoded(candidate), catalog_path.stat().st_mode & 0o777
            )
        report = {
            "status": "verified",
            "deferred": record.get("deferred", []),
            "changes": changes(old, candidate),
            "validation": validation,
            "catalog": str(catalog_path),
            "report": str(workspace / "result.json"),
        }
        atomic_write(workspace / "result.json", encoded(report))
        pending.unlink()
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="discover updates without installing or writing files (default)",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="install, verify and publish a frozen candidate; rerun to resume a failure",
    )
    parser.add_argument(
        "--only", help="comma-separated tools or skill collections; omit for all"
    )
    parser.add_argument("--catalog", type=Path, default=ROOT / "config/tools.lock.json")
    parser.add_argument(
        "--commit",
        action="store_true",
        help="commit the tested catalog only, after successful apply",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="push the commit to the current branch upstream; requires --commit",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="explicitly replace a failed frozen candidate using current upstream availability",
    )
    args = parser.parse_args()
    if args.refresh and not args.apply:
        parser.error("--refresh requires --apply")
    if args.commit and not args.apply or args.push and not args.commit:
        parser.error("--commit requires --apply; --push requires --commit")
    only = (
        {name.strip() for name in args.only.split(",") if name.strip()}
        if args.only
        else None
    )
    if args.only is not None and not only:
        parser.error("--only must contain at least one tool name")
    report = None
    try:
        if args.commit:
            args.catalog.resolve().relative_to(ROOT)
        if not args.apply:
            before = json.loads(args.catalog.read_text())
            deferred = []
            candidate = resolve_catalog(before, only, deferred=deferred)
            print(
                json.dumps(
                    {
                        "mode": "check",
                        "deferred": deferred,
                        "changes": changes(before, candidate),
                        "system_packages": (
                            "externally managed (user-only mode)"
                            if user_only_mode(Path.home())
                            else "host repository candidates; upgrades are installed only with --apply"
                        ),
                        "node_major": candidate["runtime_major"],
                    },
                    indent=2,
                )
            )
            return 0
        require_supported_host()
        enabled, _ = configured_selection(
            Path.home(), json.loads(args.catalog.read_text())
        )
        if not enabled:
            raise ValueError(
                "Enable development tools or select apps in chezmoi before applying updates"
            )
        report = apply_update(
            args.catalog, Path.home(), only=only, refresh=args.refresh
        )
        if args.commit:
            relative = args.catalog.resolve().relative_to(ROOT)
            dirty = subprocess.run(
                [
                    "git",
                    "-C",
                    str(ROOT),
                    "diff",
                    "--quiet",
                    "HEAD",
                    "--",
                    str(relative),
                ],
                check=False,
            )
            if dirty.returncode not in {0, 1}:
                raise ValueError("Cannot inspect the catalog's Git publication state")
            if dirty.returncode == 1:
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(ROOT),
                        "commit",
                        "--only",
                        str(relative),
                        "-m",
                        "chore: update validated developer tools and skills",
                    ],
                    check=True,
                )
            if args.push:
                subprocess.run(["git", "-C", str(ROOT), "push"], check=True)
        print(json.dumps(report, indent=2))
        return 0
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as error:
        recovery = (
            "Installed versions and catalog are verified; finish Git publication separately."
            if report is not None
            else "Completed package changes are retained; retry the same --apply selection to resume."
            if args.apply
            else "No packages or catalog files were changed."
        )
        print(f"Tool update failed: {error}. {recovery}", file=sys.stderr)
        return 1
