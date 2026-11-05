"""Resolve stable native releases without installing or executing downloaded code."""

import copy
import hashlib
import io
import re
import stat
import tarfile
import zipfile
from pathlib import PurePosixPath
from urllib.parse import urlsplit

GITHUB = "https://api.github.com/repos"
CLAUDE = "https://downloads.claude.ai/claude-code-releases"
AGY_INSTALLER = "https://antigravity.google/cli/install.sh"


def _stable_version(version):
    match = re.fullmatch(r"(?:bun-v|v)?(\d+)\.(\d+)\.(\d+)", version)
    return tuple(map(int, match.groups())) if match else None


def _newer(version, current):
    proposed = _stable_version(version)
    pinned = _stable_version(current)
    if pinned is None:
        raise ValueError(f"Invalid pinned native version: {current}")
    return proposed is not None and proposed > pinned


def _verify(data, checksum, algorithm="sha256"):
    length = hashlib.new(algorithm).digest_size * 2
    if not isinstance(checksum, str) or not re.fullmatch(
        r"[0-9a-fA-F]{" + str(length) + "}", checksum
    ):
        raise ValueError(f"Invalid {algorithm} checksum")
    if hashlib.new(algorithm, data).hexdigest() != checksum.lower():
        raise ValueError(f"{algorithm} checksum mismatch")


def _binary_bytes(data, entry):
    if entry.get("format") == "raw":
        return data
    member = entry["member"]
    path = PurePosixPath(member)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Unsafe archive member")
    # Read just the pinned member in memory. Never extract paths onto disk.
    if entry["url"].endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            matches = [info for info in archive.infolist() if info.filename == member]
            if len(matches) != 1:
                raise ValueError(f"Expected one archive member: {member}")
            info = matches[0]
            mode = info.external_attr >> 16
            if info.is_dir() or (stat.S_IFMT(mode) not in (0, stat.S_IFREG)):
                raise ValueError("Binary member must be a regular file")
            return archive.read(info)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as archive:
        matches = [info for info in archive if info.name == member]
        if len(matches) != 1:
            raise ValueError(f"Expected one archive member: {member}")
        info = matches[0]
        if not info.isfile():
            raise ValueError("Binary member must be a regular file")
        stream = archive.extractfile(info)
        if stream is None:
            raise ValueError("Missing binary member data")
        return stream.read()


def _pin(entry, version, url, fetch_bytes, checksum=None, algorithm="sha256"):
    data = fetch_bytes(url)
    if checksum is not None:
        _verify(data, checksum, algorithm)
    result = dict(entry, version=version, url=url)
    result["sha256"] = hashlib.sha256(data).hexdigest()
    result["binary_sha256"] = hashlib.sha256(_binary_bytes(data, result)).hexdigest()
    return result


def _github_checksum(release, asset, fetch_bytes):
    digest = asset.get("digest")
    if digest:
        if not digest.startswith("sha256:"):
            raise ValueError("Unsupported GitHub artifact checksum")
        return digest.removeprefix("sha256:")
    assets = release["assets"]
    checksum_assets = [a for a in assets if a["name"] == asset["name"] + ".sha256"]
    if not checksum_assets:
        checksum_assets = [
            a
            for a in assets
            if re.search(
                r"(?:checksums.*\.txt|sha256\.sum|SHASUMS256\.txt)$",
                a["name"],
                re.IGNORECASE,
            )
        ]
    if not checksum_assets:
        return None
    if len(checksum_assets) != 1:
        raise ValueError("Ambiguous release checksum assets")
    checksums = fetch_bytes(checksum_assets[0]["browser_download_url"]).decode("utf-8")
    if checksum_assets[0]["name"] == asset["name"] + ".sha256" and re.fullmatch(
        r"[a-fA-F0-9]{64}\s*", checksums
    ):
        return checksums.strip()
    for line in checksums.splitlines():
        match = re.fullmatch(r"([a-fA-F0-9]{64})\s+\*?(.+)", line.strip())
        if match and match[2].removeprefix("./") == asset["name"]:
            return match[1]
    raise ValueError(f"Missing checksum for {asset['name']}")


def _github(entry, repo, fetch_json, fetch_bytes):
    release = fetch_json(f"{GITHUB}/{repo}/releases/latest")
    tag = release["tag_name"]
    if (
        release.get("prerelease")
        or release.get("draft")
        or not _newer(tag, entry["version"])
    ):
        return entry
    version = ".".join(map(str, _stable_version(tag)))
    # Preserve the selected OS, architecture, libc and baseline family.
    old_name = PurePosixPath(urlsplit(entry["url"]).path).name
    name = old_name.replace(entry["version"], version)
    assets = [a for a in release["assets"] if a["name"] == name]
    if len(assets) != 1:
        raise ValueError(f"Expected exactly one release asset: {repo}/{name}")
    asset = assets[0]
    url = asset["browser_download_url"]
    expected = f"https://github.com/{repo}/releases/download/{tag}/{name}"
    if url != expected:
        raise ValueError("Release asset URL does not match repository, tag and name")
    checksum = _github_checksum(release, asset, fetch_bytes)
    return _pin(entry, version, url, fetch_bytes, checksum)


def _claude(entry, fetch_json, fetch_bytes):
    version = fetch_bytes(f"{CLAUDE}/latest").decode("utf-8").strip()
    if not _newer(version, entry["version"]):
        return entry
    manifest = fetch_json(f"{CLAUDE}/{version}/manifest.json")
    if manifest["version"] != version:
        raise ValueError("Claude manifest version mismatch")
    platform = manifest["platforms"]["linux-x64"]
    if platform["binary"] != "claude":
        raise ValueError("Unexpected Claude platform binary")
    return _pin(
        entry,
        version,
        f"{CLAUDE}/{version}/linux-x64/claude",
        fetch_bytes,
        platform["checksum"],
    )


def _antigravity(entry, fetch_json, fetch_bytes):
    # Discover Google's manifest endpoint from the official installer as text.
    installer = fetch_bytes(AGY_INSTALLER).decode("utf-8")
    match = re.search(
        r'^DOWNLOAD_BASE_URL=["\'](https://[^"\']+)["\']\s*$', installer, re.MULTILINE
    )
    if not match:
        raise ValueError("Cannot discover Antigravity release manifest endpoint")
    root = match[1]
    host = urlsplit(root)
    if (
        host.scheme != "https"
        or not host.hostname
        or not host.hostname.startswith("antigravity-cli-auto-updater-")
        or not host.hostname.endswith(".run.app")
        or host.username
        or host.password
        or host.port
        or host.path
        or host.query
        or host.fragment
    ):
        raise ValueError("Unexpected Antigravity manifest host")
    manifest = fetch_json(f"{root}/manifests/linux_amd64.json")
    version = manifest["version"]
    if not _newer(version, entry["version"]):
        return entry
    url = manifest["url"]
    pattern = (
        r"https://storage\.googleapis\.com/antigravity-public/antigravity-cli/"
        + re.escape(version)
        + r"-\d+/linux-x64/cli_linux_x64\.tar\.gz"
    )
    if not re.fullmatch(pattern, url):
        raise ValueError(
            "Antigravity release URL does not match its version and platform"
        )
    return _pin(entry, version, url, fetch_bytes, manifest["sha512"], "sha512")


def resolve_artifacts(catalog, fetch_json, fetch_bytes, only=None):
    """Return a deep copy with selected stable native release pins refreshed.

    Callbacks take an HTTPS URL and return decoded JSON or bytes respectively.
    Selection names are rtk, actionlint, uv, claude, antigravity (alias agy),
    and bun (also selected by claude-mem). An empty selection performs no IO.
    """
    result = copy.deepcopy(catalog)
    selected = lambda *names: only is None or bool(set(names) & set(only))
    for name, repo in (
        ("rtk", "rtk-ai/rtk"),
        ("actionlint", "rhysd/actionlint"),
        ("uv", "astral-sh/uv"),
    ):
        if name in result["developer"]["binaries"] and selected(name):
            entries = result["developer"]["binaries"]
            entries[name] = _github(entries[name], repo, fetch_json, fetch_bytes)
    if "claude-mem" in result["skills"] and selected("bun", "claude-mem"):
        skill = result["skills"]["claude-mem"]
        skill["bun"] = _github(skill["bun"], "oven-sh/bun", fetch_json, fetch_bytes)
    for name, aliases, resolver in (
        ("claude", ("claude",), _claude),
        ("antigravity", ("antigravity", "agy"), _antigravity),
    ):
        if (
            name in result["agents"]
            and result["agents"][name].get("kind") in {"native", "claude-native"}
            and selected(*aliases)
        ):
            agent = result["agents"][name]
            agent["artifact"] = resolver(agent["artifact"], fetch_json, fetch_bytes)
            agent["version"] = agent["artifact"]["version"]
    return result
