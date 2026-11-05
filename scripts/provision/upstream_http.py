"""Bounded upstream reads with private GitHub metadata caching and quota errors."""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

CACHE_SECONDS = 15 * 60
MAX_PAYLOAD = 512 * 1024 * 1024


def _github_token():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token and shutil.which("gh"):
        result = subprocess.run(
            ["gh", "auth", "token", "--hostname", "github.com"],
            capture_output=True,
            timeout=30,
            check=False,
        )
        if result.returncode == 0:
            token = result.stdout.decode().strip()
    return token


def _cache_path(url, token):
    root = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    # Separate credentials without persisting tokens or serving one login's data
    # to another login. Cache files contain only successful API response bodies.
    key = hashlib.sha256((url + "\0" + (token or "")).encode()).hexdigest()
    return root / "dotfiles/upstream/github" / (key + ".json")


def _cached(path):
    try:
        age = time.time() - path.stat().st_mtime
        if 0 <= age < CACHE_SECONDS:
            data = path.read_bytes()
            json.loads(data)
            return data
    except (OSError, ValueError):
        pass
    return None


def _save_cache(path, data):
    temporary = None
    try:
        json.loads(data)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(data)
        os.replace(temporary, path)
    except (OSError, ValueError):
        # An unwritable cache must not prevent a verified upstream response.
        pass
    finally:
        if temporary:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _github_error(error, authenticated):
    headers = {key.lower(): value for key, value in error.headers.items()}
    body = error.read(4096).decode(errors="replace").lower()
    if (
        error.code == 429
        or headers.get("x-ratelimit-remaining") == "0"
        or "rate limit" in body
    ):
        wait = "Wait at least 60 seconds before retrying"
        if headers.get("retry-after", "").isdigit():
            wait = f"Wait at least {headers['retry-after']} seconds before retrying"
        elif headers.get("x-ratelimit-reset", "").isdigit():
            reset = datetime.fromtimestamp(int(headers["x-ratelimit-reset"]), UTC)
            wait = "Retry after " + reset.strftime("%Y-%m-%d %H:%M:%S UTC")
        identity = "authenticated" if authenticated else "anonymous"
        login = (
            ""
            if authenticated
            else "; run gh auth login on this WSL for a higher quota"
        )
        return ValueError(
            f"GitHub {identity} API rate limit exceeded. {wait}{login}. No automatic retry was made"
        )
    if error.code in {401, 403}:
        return ValueError(
            "GitHub authentication or access failed; check gh auth status and repository permissions. Anonymous fallback was not attempted"
        )
    return ValueError(
        f"GitHub API request failed with HTTP {error.code} for {error.url}"
    )


def fetch_bytes(url):
    github = url.startswith("https://api.github.com/")
    token = _github_token() if github else None
    cache = _cache_path(url, token) if github else None
    if cache:
        data = _cached(cache)
        if data is not None:
            return data
    headers = {"User-Agent": "dotfiles-tool-updater", "Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read(MAX_PAYLOAD + 1)
    except urllib.error.HTTPError as error:
        if github:
            with error:
                failure = _github_error(error, bool(token))
            raise failure from None
        raise
    if len(data) > MAX_PAYLOAD:
        raise ValueError("Upstream payload exceeds the update size limit")
    if cache:
        _save_cache(cache, data)
    return data
