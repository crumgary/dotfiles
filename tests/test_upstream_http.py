"""GitHub discovery conserves quota and reports actionable retry instructions."""

import io
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from provision import upstream_http as upstream

URL = "https://api.github.com/repos/owner/project/releases/latest"


class UpstreamHttpTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        environment = patch.dict(
            os.environ, {"XDG_CACHE_HOME": temporary.name}, clear=True
        )
        environment.start()
        self.addCleanup(environment.stop)
        cli = patch.object(upstream.shutil, "which", return_value=None)
        cli.start()
        self.addCleanup(cli.stop)

    def response(self, data=b'{"tag_name":"v1.0.0"}'):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = data
        return response

    def test_repeated_discovery_reuses_successful_metadata(self):
        with patch.object(
            upstream.urllib.request, "urlopen", return_value=self.response()
        ) as request:
            self.assertEqual(upstream.fetch_bytes(URL), upstream.fetch_bytes(URL))
        self.assertEqual(request.call_count, 1)

    def test_primary_limit_reports_reset_and_login_without_retrying(self):
        error = urllib.error.HTTPError(
            URL,
            403,
            "rate limit exceeded",
            {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1793910340"},
            io.BytesIO(),
        )
        with (
            patch.object(
                upstream.urllib.request, "urlopen", side_effect=error
            ) as request,
            self.assertRaisesRegex(
                ValueError, "2026-11-05 20:25:40 UTC.*gh auth login"
            ),
        ):
            upstream.fetch_bytes(URL)
        self.assertEqual(request.call_count, 1)

    def test_authenticated_error_does_not_fall_back_to_anonymous(self):
        result = subprocess.CompletedProcess([], 0, b"fixture-secret\n", b"")
        error = urllib.error.HTTPError(URL, 401, "Unauthorized", {}, io.BytesIO())
        with (
            patch.object(upstream.shutil, "which", return_value="/bin/gh"),
            patch.object(upstream.subprocess, "run", return_value=result),
            patch.object(
                upstream.urllib.request, "urlopen", side_effect=error
            ) as request,
            self.assertRaisesRegex(ValueError, "authentication"),
        ):
            upstream.fetch_bytes(URL)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(
            request.call_args.args[0].get_header("Authorization"),
            "Bearer fixture-secret",
        )

    def test_expired_cache_fetches_current_metadata(self):
        with patch.object(
            upstream.urllib.request, "urlopen", return_value=self.response()
        ) as request:
            upstream.fetch_bytes(URL)
            cache = upstream._cache_path(URL, None)
            os.utime(cache, (1, 1))
            upstream.fetch_bytes(URL)
        self.assertEqual(request.call_count, 2)

    def test_retry_after_is_reported_without_automatic_retries(self):
        error = urllib.error.HTTPError(
            URL, 429, "Too Many Requests", {"Retry-After": "120"}, io.BytesIO()
        )
        with (
            patch.object(
                upstream.urllib.request, "urlopen", side_effect=error
            ) as request,
            self.assertRaisesRegex(ValueError, "at least 120 seconds"),
        ):
            upstream.fetch_bytes(URL)
        self.assertEqual(request.call_count, 1)

    def test_credentials_and_cache_are_isolated_from_external_downloads(self):
        with (
            patch.dict(os.environ, {"GH_TOKEN": "fixture-secret"}),
            patch.object(
                upstream.urllib.request, "urlopen", return_value=self.response()
            ) as request,
        ):
            upstream.fetch_bytes(URL)
            cache = upstream._cache_path(URL, "fixture-secret")
            self.assertEqual(cache.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(b"fixture-secret", cache.read_bytes())
            upstream.fetch_bytes("https://example.com/archive.tgz")
            upstream.fetch_bytes("https://example.com/archive.tgz")
            self.assertIsNone(request.call_args.args[0].get_header("Authorization"))
            upstream.fetch_bytes(URL)
        self.assertEqual(request.call_count, 3)
        with patch.object(
            upstream.urllib.request, "urlopen", return_value=self.response()
        ) as request:
            upstream.fetch_bytes(URL)
        self.assertEqual(request.call_count, 1)

    def test_unwritable_cache_does_not_break_discovery(self):
        with (
            patch.object(
                upstream.urllib.request, "urlopen", return_value=self.response()
            ),
            patch.object(upstream.Path, "mkdir", side_effect=PermissionError),
        ):
            self.assertEqual(upstream.fetch_bytes(URL), b'{"tag_name":"v1.0.0"}')
