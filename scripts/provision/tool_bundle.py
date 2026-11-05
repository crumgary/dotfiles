"""Declared developer-tool acquisition, separate from app login and activation."""

import argparse
import hashlib
import io
import json
import os
import platform
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath


def verify_payload(data, expected):
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("Downloaded content failed SHA-256 verification.")
    return data


def download(entry):
    with urllib.request.urlopen(entry["url"], timeout=120) as response:
        return verify_payload(response.read(), entry["sha256"])


def extract_source(data, destination, excluded=()):
    """Extract regular source files only, stripping a single codeload root."""
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Unsafe skill source archive entry.")
            relative = str(PurePosixPath(*path.parts[1:]))
            if relative in excluded:
                continue
            if not (member.isfile() or member.isdir()):
                raise ValueError("Unsafe skill source archive entry.")
            if len(path.parts) < 2 and member.isfile():
                raise ValueError("Expected a repository-root archive.")
        destination.mkdir(parents=True, exist_ok=True)
        for member in members:
            parts = PurePosixPath(member.name).parts[1:]
            if str(PurePosixPath(*parts)) in excluded:
                continue
            if not parts:
                continue
            path = destination.joinpath(*parts)
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.extractfile(member).read())
                path.chmod(0o755 if member.mode & 0o111 else 0o644)


def tree_digest(root):
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.name == ".dotfiles-source.json":
            continue
        if path.is_symlink():
            raise ValueError("Unexpected symlink in managed skill source.")
        if path.is_file():
            digest.update(str(path.relative_to(root)).encode() + b"\0")
            digest.update(str(path.stat().st_mode & 0o777).encode() + b"\0")
            digest.update(path.read_bytes())
    return digest.hexdigest()


def run(command, env=None):
    subprocess.run(command, check=True, env=env, stdin=subprocess.DEVNULL)


def write_system(path, data):
    if path.exists() and path.read_bytes() == data:
        return False
    with tempfile.NamedTemporaryFile() as temporary:
        temporary.write(data)
        temporary.flush()
        run(["sudo", "-n", "install", "-D", "-m", "0644", temporary.name, str(path)])
    return True


def install_apt(lock):
    required = []
    for name, version in lock["apt"].items():
        result = subprocess.run(
            ["dpkg-query", "-W", "-f=${db:Status-Status}|${Version}", name],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.startswith("installed|"):
            actual = result.stdout.partition("|")[2]
            newer = subprocess.run(
                ["dpkg", "--compare-versions", actual, "gt", version], check=False
            )
            if newer.returncode == 0:
                raise ValueError(
                    f"{name} is newer than the lock; update the lock or explicitly reconcile it. Automatic downgrade is disabled"
                )
        if result.returncode or result.stdout != "installed|" + version:
            required.append(name + "=" + version)
    changed = False
    for name, entry in lock["repositories"].items():
        key = Path("/etc/apt/keyrings") / f"dotfiles-{name}.{entry['format']}"
        if (
            not key.is_file()
            or hashlib.sha256(key.read_bytes()).hexdigest() != entry["key_sha256"]
        ):
            data = download({"url": entry["key_url"], "sha256": entry["key_sha256"]})
            changed |= write_system(key, data)
        content = (
            f"Types: deb\nURIs: {entry['uri']}\nSuites: {entry.get('suite', 'stable')}\nComponents: main\n"
            f"Architectures: amd64\nSigned-By: {key}\n"
        ).encode()
        changed |= write_system(
            Path("/etc/apt/sources.list.d") / f"dotfiles-{name}.sources", content
        )
    if required or changed:
        run(["sudo", "-n", "apt-get", "update", "-qq"])
    if required:
        run(
            [
                "sudo",
                "-n",
                "env",
                "DEBIAN_FRONTEND=noninteractive",
                "apt-get",
                "install",
                "-y",
                *required,
            ]
        )


def install_binary(home, name, entry):
    target = home / ".local/bin" / name
    if (
        target.is_file()
        and hashlib.sha256(target.read_bytes()).hexdigest() == entry["binary_sha256"]
    ):
        if not target.is_symlink():
            if target.stat().st_mode & 0o777 != 0o755:
                target.chmod(0o755)
            return
        if target.stat().st_mode & 0o111:
            return
    payload = download(entry)
    if entry.get("format") == "raw":
        data = verify_payload(payload, entry["binary_sha256"])
    else:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
            member = archive.getmember(entry["member"])
            if not member.isfile():
                raise ValueError("Expected an ordinary binary in release archive.")
            data = verify_payload(
                archive.extractfile(member).read(), entry["binary_sha256"]
            )
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temporary:
        staged = Path(temporary.name)
        try:
            temporary.write(data)
            temporary.flush()
            staged.chmod(0o755)
            staged.replace(target)
        finally:
            staged.unlink(missing_ok=True)


def stage_skills(home, name, entry):
    base = home / ".local/share/dotfiles/skill-sources" / name
    target = base / entry["revision"]
    receipt = target / ".dotfiles-source.json"
    if target.exists():
        if not receipt.is_file():
            raise ValueError(
                "Existing skill source has no ownership receipt; left intact."
            )
        recorded = json.loads(receipt.read_text())
        if recorded.get("sha256") != entry["sha256"] or recorded.get(
            "tree"
        ) != tree_digest(target):
            raise ValueError("Managed skill source has local edits; left intact.")
        return str(target)
    payload = download(entry)
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=base) as temporary:
        staged = Path(temporary) / "source"
        extract_source(payload, staged, entry.get("exclude", ()))
        (staged / ".dotfiles-source.json").write_text(
            json.dumps({"sha256": entry["sha256"], "tree": tree_digest(staged)}) + "\n"
        )
        staged.replace(target)
    return str(target)


def install_npm(home, packages):
    prefix = home / ".local"
    required = []
    for name, version in packages.items():
        path = prefix / "lib/node_modules" / name / "package.json"
        try:
            actual = json.loads(path.read_text())["version"]
        except (OSError, ValueError, KeyError):
            actual = None
        if actual != version or not (prefix / "bin" / name).exists():
            required.append(name + "@" + version)
    if required:
        run(
            [
                "npm",
                "install",
                "--global",
                "--prefix",
                str(prefix),
                "--ignore-scripts",
                "--no-audit",
                "--no-fund",
                *required,
            ]
        )
    env = {**os.environ, "PATH": str(prefix / "bin") + ":" + os.environ.get("PATH", "")}
    module = str(prefix / "lib/node_modules/playwright")
    browser = subprocess.check_output(
        [
            "node",
            "-e",
            "process.stdout.write(require(process.argv[1]).chromium.executablePath())",
            module,
        ],
        text=True,
        env=env,
    )
    if not Path(browser).is_file():
        run(
            [str(prefix / "bin/playwright"), "install", "--with-deps", "chromium"],
            env=env,
        )
    if "hyperframes" in packages:
        run([str(prefix / "bin/hyperframes"), "browser", "ensure"], env=env)
    run(
        [
            "node",
            "-e",
            "const {chromium}=require(process.argv[1]); (async()=>{const browser=await chromium.launch();try{const page=await browser.newPage();await page.setContent('<title>Provisioning smoke</title>');if(await page.title()!=='Provisioning smoke')throw Error('Unexpected title');}finally{await browser.close();}})().catch(error=>{console.error(error.message);process.exit(1)});",
            module,
        ],
        env=env,
    )


def require_supported_host():
    release = Path("/etc/os-release").read_text()
    if (
        platform.machine() != "x86_64"
        or 'VERSION_ID="26.04"' not in release
        or "ID=ubuntu\n" not in release
    ):
        raise ValueError("This bundle is verified only on Ubuntu 26.04 x86_64.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--home", type=Path, default=Path.home())
    args = parser.parse_args()
    lock_path = Path(__file__).resolve().parents[2] / "config/tools.lock.json"
    catalog = json.loads(lock_path.read_text())
    lock = {**catalog["developer"], "skills": catalog["skills"]}
    tools = {
        **lock["apt"],
        **{name: entry["version"] for name, entry in lock["binaries"].items()},
        **lock["npm"],
    }
    if args.dry_run:
        print(
            json.dumps(
                {
                    "tools": tools,
                    "skills": lock["skills"],
                    "activation": "staged only; app adapters are separate",
                },
                indent=2,
            )
        )
        return 0
    try:
        if args.home.resolve() != Path.home().resolve():
            raise ValueError(
                "Apply must run as the actual target user; --home is for dry runs."
            )
        require_supported_host()
        run(["sudo", "-n", "true"])
        install_apt(lock)
        for name, entry in lock["binaries"].items():
            install_binary(args.home, name, entry)
        install_npm(args.home, lock["npm"])
        from provision.python_tools import install_python_tools

        install_python_tools(args.home, lock.get("python", {}))
        sources = {
            name: stage_skills(args.home, name, entry)
            for name, entry in lock["skills"].items()
        }
        receipt = {
            "manifest_sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
            "tools": tools,
            "skill_sources": sources,
            "activation": "staged only",
        }
        destination = args.home / ".local/state/dotfiles/developer-tools.json"
        contents = json.dumps(receipt, indent=2) + "\n"
        if not destination.is_file() or destination.read_text() != contents:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(contents)
        print(
            "Developer tools installed; pinned skill sources staged. App activation and authentication are separate."
        )
        return 0
    except (
        OSError,
        ValueError,
        KeyError,
        subprocess.CalledProcessError,
        tarfile.TarError,
    ) as error:
        print(
            f"Developer bundle failed: {error}. Completed stages are retained for retry.",
            file=sys.stderr,
        )
        return 1
