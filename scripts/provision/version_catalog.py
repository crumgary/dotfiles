"""Resolve stable upstream versions without installing or executing downloads."""

import base64
import copy
import hashlib
import json
import re
import urllib.parse

from provision.npm_releases import UnavailableNpmRelease, check_npm_release
from provision.upstream_http import fetch_bytes
from provision.version_artifacts import resolve_artifacts


def fetch_json(url):
    return json.loads(fetch_bytes(url))


def stable_version(value):
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        raise ValueError("Upstream did not identify a stable release: " + value)
    return tuple(map(int, match.groups()))


def npm_metadata(package, get_json):
    return get_json(
        "https://registry.npmjs.org/"
        + urllib.parse.quote(package, safe="@/")
        + "/latest"
    )


def refreshed_source(entry, revision, get_bytes):
    if not re.fullmatch(r"[0-9a-f]{40,64}", revision):
        raise ValueError("Invalid upstream source revision")
    if revision == entry["revision"]:
        return entry
    result = copy.deepcopy(entry)
    result["revision"] = revision
    repository = entry["repository"]
    if "gitlab.com/" in entry["url"]:
        result["url"] = (
            f"https://gitlab.com/{repository}/-/archive/{revision}/{repository.rsplit('/', 1)[-1]}-{revision}.tar.gz"
        )
    else:
        result["url"] = f"https://codeload.github.com/{repository}/tar.gz/{revision}"
    result["sha256"] = hashlib.sha256(get_bytes(result["url"])).hexdigest()
    return result


def known_names(catalog):
    dev = catalog["developer"]
    return (
        set(dev["apt"])
        | set(dev["npm"])
        | set(dev["binaries"])
        | set(dev.get("python", {}))
        | set(catalog["agents"])
        | set(catalog["skills"])
        | {"bun", "node", "agy"}
    )


def resolve_catalog(
    catalog,
    only=None,
    get_json=fetch_json,
    get_bytes=fetch_bytes,
    npm_checker=None,
    deferred=None,
):
    """Return a complete candidate; the approved input remains untouched."""
    if only and set(only) - known_names(catalog):
        raise ValueError(
            "Unknown update selection: "
            + ", ".join(sorted(set(only) - known_names(catalog)))
        )
    selected = set(only) if only is not None else None
    if selected and "node" in selected:
        selected.add("nodejs")
    if selected and "agy" in selected:
        selected.add("antigravity")
    if selected and ("graphify" in selected or "graphifyy" in selected):
        selected.update({"graphify", "graphifyy"})

    def wanted(name):
        return selected is None or name in selected

    candidate = copy.deepcopy(catalog)
    npm_checker = npm_checker or check_npm_release
    deferred = deferred if deferred is not None else []

    def installable(package, version, name):
        try:
            npm_checker(package, version)
            return True
        except UnavailableNpmRelease as error:
            deferred.append({"tool": name, "version": version, "reason": str(error)})
            return False

    for name, version in catalog["developer"]["npm"].items():
        if wanted(name):
            latest = npm_metadata(name, get_json)["version"]
            if stable_version(latest) > stable_version(version) and installable(
                name, latest, name
            ):
                candidate["developer"]["npm"][name] = latest
    for name, entry in catalog["agents"].items():
        if entry["kind"] == "npm" and wanted(name):
            latest = npm_metadata(entry["package"], get_json)["version"]
            if stable_version(latest) > stable_version(
                entry["version"]
            ) and installable(entry["package"], latest, name):
                candidate["agents"][name]["version"] = latest
    for name, entry in catalog["developer"].get("python", {}).items():
        if wanted(name):
            latest = get_json("https://pypi.org/pypi/" + name + "/json")["info"][
                "version"
            ]
            if stable_version(latest) > stable_version(entry["version"]):
                candidate["developer"]["python"][name]["version"] = latest
            release = get_json(
                "https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest"
            )
            major, minor, _ = stable_version(entry["python"])
            versions = []
            for asset in release.get("assets", []):
                match = re.match(r"cpython-(\d+\.\d+\.\d+)\+", asset["name"])
                if match and stable_version(match[1])[:2] == (major, minor):
                    versions.append(match[1])
            if versions:
                latest_python = max(versions, key=stable_version)
                if stable_version(latest_python) > stable_version(entry["python"]):
                    candidate["developer"]["python"][name]["python"] = latest_python
    for name, entry in catalog["skills"].items():
        if not wanted(name):
            continue
        if name == "claude-mem":
            metadata = npm_metadata("claude-mem", get_json)
            latest = metadata["version"]
            if stable_version(latest) <= stable_version(entry["version"]):
                continue
            if not installable("claude-mem", latest, name):
                continue
            result = copy.deepcopy(entry)
            result["version"] = latest
            result["url"] = metadata["dist"]["tarball"]
            data = get_bytes(result["url"])
            integrity = metadata["dist"].get("integrity", "")
            if (
                not integrity.startswith("sha512-")
                or base64.b64encode(hashlib.sha512(data).digest()).decode()
                != integrity[7:]
            ):
                raise ValueError(
                    "Published memory package integrity verification failed"
                )
            result["sha256"] = hashlib.sha256(data).hexdigest()
            result["revision"] = (
                metadata.get("gitHead")
                or get_json(
                    f"https://api.github.com/repos/{entry['repository']}/commits/v{latest}"
                )["sha"]
            )
            if not re.fullmatch(r"[0-9a-f]{40,64}", result["revision"]):
                raise ValueError("Memory release is missing its source revision")
            candidate["skills"][name] = result
        else:
            if "gitlab.com/" in entry["url"]:
                project = urllib.parse.quote(entry["repository"], safe="")
                revision = get_json(
                    f"https://gitlab.com/api/v4/projects/{project}/repository/commits?per_page=1"
                )[0]["id"]
            else:
                revision = get_json(
                    f"https://api.github.com/repos/{entry['repository']}/commits?per_page=1"
                )[0]["sha"]
            candidate["skills"][name] = refreshed_source(entry, revision, get_bytes)
    return resolve_artifacts(candidate, get_json, get_bytes, selected)


def changes(before, after, prefix=""):
    result = []
    for key in before.keys() | after.keys():
        left, right = before.get(key), after.get(key)
        path = prefix + key
        if isinstance(left, dict) and isinstance(right, dict):
            result += changes(left, right, path + ".")
        elif left != right:
            result.append({"field": path, "before": left, "after": right})
    return sorted(result, key=lambda item: item["field"])
