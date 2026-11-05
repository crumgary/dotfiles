"""Reproduce a partially published dependency graph through a real npm client."""

import base64
import hashlib
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from provision.npm_releases import UnavailableNpmRelease, check_npm_release
from provision.version_catalog import resolve_catalog


@unittest.skipUnless(
    shutil.which("npm"), "npm is required for registry integration checks"
)
class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.marker = Path(self.temporary.name) / "lifecycle-ran"
        documents = {}
        blobs = {}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                path = unquote(self.path.split("?")[0]).strip("/")
                if path in blobs:
                    payload = blobs[path]
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                pieces = path.split("/")
                document = documents.get(pieces[0])
                if document and len(pieces) == 2:
                    document = document["versions"].get(pieces[1])
                self.send_response(200 if document else 404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps(document or {"error": "not found"}).encode()
                )

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def shutdown():
            server.shutdown()
            server.server_close()
            thread.join()

        self.addCleanup(shutdown)
        self.registry = f"http://127.0.0.1:{server.server_port}"
        script = "node -e " + shlex.quote(
            'require("fs").writeFileSync(' + json.dumps(str(self.marker)) + ',"bad")'
        )

        def release(name, version, dependencies=None):
            item = {
                "name": name,
                "version": version,
                "scripts": {"preinstall": script},
                "dependencies": dependencies or {},
            }
            payload = json.dumps(item).encode()
            archive = io.BytesIO()
            with tarfile.open(fileobj=archive, mode="w:gz") as tar:
                member = tarfile.TarInfo("package/package.json")
                member.size = len(payload)
                tar.addfile(member, io.BytesIO(payload))
            data = archive.getvalue()
            path = f"{name}/-/{name}-{version}.tgz"
            blobs[path] = data
            item["dist"] = {
                "tarball": self.registry + "/" + path,
                "integrity": "sha512-"
                + base64.b64encode(hashlib.sha512(data).digest()).decode(),
            }
            document = documents.setdefault(
                name, {"name": name, "dist-tags": {}, "versions": {}}
            )
            document["versions"][version] = item
            document["dist-tags"]["latest"] = version

        release("dotfiles-child", "1.0.0")
        release("dotfiles-probe", "1.0.0", {"dotfiles-child": "^1.0.0"})
        release("dotfiles-probe", "1.1.0", {"dotfiles-child": "^2.0.0"})

    def test_required_dependency_range_is_resolved_without_install_or_scripts(self):
        with patch.dict(os.environ, {"NPM_CONFIG_GLOBAL": "true"}):
            check_npm_release("dotfiles-probe", "1.0.0", self.registry)
        self.assertFalse(self.marker.exists())

    def test_root_is_published_but_unavailable_transitive_version_is_rejected(self):
        with self.assertRaises(UnavailableNpmRelease):
            check_npm_release("dotfiles-probe", "1.1.0", self.registry)
        self.assertFalse(self.marker.exists())

    def test_broken_latest_is_deferred_without_changing_approved_catalog(self):
        approved = {
            "runtime_major": 26,
            "developer": {
                "apt": {},
                "binaries": {},
                "python": {},
                "npm": {"dotfiles-probe": "1.0.0"},
            },
            "agents": {},
            "skills": {},
        }
        deferred = []
        candidate = resolve_catalog(
            approved,
            {"dotfiles-probe"},
            lambda url: {"version": "1.1.0"},
            lambda url: self.fail(),
            npm_checker=lambda name, version: check_npm_release(
                name, version, self.registry
            ),
            deferred=deferred,
        )
        self.assertEqual(candidate, approved)
        self.assertEqual(deferred[0]["tool"], "dotfiles-probe")
        self.assertEqual(deferred[0]["version"], "1.1.0")

    def test_network_failure_is_not_silently_treated_as_an_unpublished_release(self):
        result = subprocess.CompletedProcess(
            [], 1, json.dumps({"error": {"code": "ECONNRESET"}}), ""
        )
        with patch("provision.npm_releases.subprocess.run", return_value=result):
            with self.assertRaises(ValueError) as error:
                check_npm_release("dotfiles-probe", "1.1.0", self.registry)
            self.assertNotIsInstance(error.exception, UnavailableNpmRelease)
