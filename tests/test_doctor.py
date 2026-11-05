"""Exercise the CLI against fixture homes, including hostile local configuration."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "scripts/dotfiles-doctor"
RECORD = """schema_version = 1
id = "fixture-wsl"
owner = "local"
profile = "wsl"
os = "ubuntu"
architecture = "x86_64"
overlays = []
bundles = []
"""
# The actual CLI runs inside this guard, including imports and Git probes.
GUARD = """
import sys, runpy, os
sys.dont_write_bytecode = True
def guard(event, args):
    if event == 'open' and isinstance(args[2], int) and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
        raise RuntimeError('write denied')
    if event.startswith('socket.') or event in {'os.mkdir','os.remove','os.rename','os.chmod','os.symlink','os.link','os.rmdir','os.truncate','os.utime','os.chown','os.mknod','os.system','os.exec'}:
        raise RuntimeError('mutation or network denied')
    if event in {'subprocess.Popen', 'os.posix_spawn'}:
        cmd = args[1]
        if cmd[:9] != ['/usr/bin/git','--no-optional-locks','-c','core.fsmonitor=false','-c','core.untrackedCache=false','-c','core.hooksPath=/dev/null','-C'] or cmd[10:] != ['rev-parse','HEAD']:
            raise RuntimeError('subprocess denied')
sys.addaudithook(guard)
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name='__main__')
"""


class DoctorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.source = self.root / "source"
        self.home.mkdir()
        (self.source / "home/.chezmoidata").mkdir(parents=True)
        (self.source / "home/.chezmoidata/packages.toml").write_text(
            '[doctor]\ncommon = ["git", "certainly-absent-doctor-tool"]\n'
            'embedded = ["sh"]\n[release_binary]\ngit="99.0"\n'
            '[doctor.bundles]\ncoding=["doctor-agent-decoy"]\n'
        )
        (self.home / ".config/chezmoi").mkdir(parents=True)
        self.config = self.home / ".config/chezmoi/chezmoi.toml"
        self.config.write_text(
            '[data]\nprofile="wsl"\nwork=false\n'
            "bootstrap_priv_overlay=false\nbootstrap_work_overlay=false\n"
            'install_agent_clis=false\nsecret="never-print-this-secret"\n'
        )
        self.record = self.root / "machine.toml"
        self.record.write_text(RECORD)

    def run_cli(self, *args):
        cmd = [
            sys.executable,
            "-B",
            "-c",
            GUARD,
            str(CLI),
            "--home",
            str(self.home),
            "--source",
            str(self.source),
            *args,
        ]
        if os.environ.get("DOCTOR_SANDBOX") == "1":
            cmd = [
                "/usr/bin/bwrap",
                "--ro-bind",
                "/",
                "/",
                "--dev-bind",
                "/dev/null",
                "/dev/null",
                "--unshare-net",
                "--",
                *cmd,
            ]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            env={
                **os.environ,
                "PYTHONDONTWRITEBYTECODE": "1",
                "PATH": str(self.root / "bin")
                + os.pathsep
                + os.environ.get("PATH", ""),
            },
        )

    def doctor(self):
        result = self.run_cli("--machine", str(self.record), "--json")
        self.assertIn(result.returncode, (0, 1), result.stderr)
        self.assertTrue(result.stdout.strip(), result.stderr)
        self.assertNotIn("never-print-this-secret", result.stdout + result.stderr)
        return json.loads(result.stdout)["findings"]

    def finding(self, findings, check):
        return next(item for item in findings if item["check"] == check)

    def test_missing_required_tool_is_not_success(self):
        findings = self.doctor()
        self.assertEqual(
            self.finding(findings, "tool:certainly-absent-doctor-tool")["status"],
            "missing",
        )

    def test_static_file_drift_and_missing_file(self):
        (self.source / "home/dot_bashrc").write_text("expected\n")
        self.assertEqual(
            self.finding(self.doctor(), "file:.bashrc")["status"], "missing"
        )
        (self.home / ".bashrc").write_text("different\n")
        self.assertEqual(
            self.finding(self.doctor(), "file:.bashrc")["status"], "drifted"
        )
        (self.home / ".bashrc").write_text("expected\n")
        self.assertEqual(
            self.finding(self.doctor(), "file:.bashrc")["status"], "matching"
        )

    def test_templates_are_never_executed(self):
        marker = self.root / "template-executed"
        (self.source / "home/dot_bashrc.tmpl").write_text(
            '{{ output "touch" "' + str(marker) + '" }}'
        )
        self.assertEqual(
            self.finding(self.doctor(), "file:.bashrc")["status"], "unverified"
        )
        self.assertFalse(marker.exists())

    def test_private_runtime_permissions(self):
        directory = self.home / ".pi/agent"
        directory.mkdir(parents=True, mode=0o755)
        directory.chmod(0o755)
        self.assertEqual(
            self.finding(self.doctor(), "permission:.pi/agent")["status"], "drifted"
        )
        directory.chmod(0o700)
        self.assertEqual(
            self.finding(self.doctor(), "permission:.pi/agent")["status"], "matching"
        )

    def test_disabled_work_content_is_reported(self):
        overlay = self.home / ".config/dotfiles-work"
        overlay.mkdir()
        self.assertEqual(
            self.finding(self.doctor(), "overlay:work")["status"], "drifted"
        )

    def test_selected_overlay_missing(self):
        self.record.write_text(
            RECORD.replace("overlays = []", 'overlays = ["personal"]')
        )
        self.assertEqual(
            self.finding(self.doctor(), "overlay:personal")["status"], "missing"
        )

    def test_inventory_owner_must_be_selected(self):
        self.record.write_text(RECORD.replace('owner = "local"', 'owner = "work"'))
        result = self.run_cli("--machine", str(self.record), "--json")
        self.assertEqual(result.returncode, 2)

    def test_invalid_records_are_errors_without_echoing_contents(self):
        for content in [
            RECORD + 'unknown="never-print-this-secret"\n',
            RECORD.replace("schema_version = 1", "schema_version = true"),
            RECORD.replace('id = "fixture-wsl"', 'id = "../../bad"'),
            RECORD.replace("overlays = []", 'overlays = ["work", "work"]'),
            RECORD.replace('os = "ubuntu"', 'os = "unknown"'),
            RECORD.replace("bundles = []", 'bundles = ["unrecognized"]'),
            RECORD + '[revisions]\npublic="main"\n',
            'bad="never-print-this-secret"\n[',
        ]:
            with self.subTest(content=content[:30]):
                self.record.write_text(content)
                result = self.run_cli("--machine", str(self.record), "--json")
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertNotIn(
                    "never-print-this-secret", result.stdout + result.stderr
                )

    def test_config_selection_drift_reports_only_field_names(self):
        self.config.write_text(
            self.config.read_text().replace('profile="wsl"', 'profile="lab"')
        )
        self.assertEqual(
            self.finding(self.doctor(), "selection:profile")["status"], "drifted"
        )

    def test_import_is_a_preview_without_secrets_or_writes(self):
        before = sorted(str(p) for p in self.root.rglob("*"))
        result = self.run_cli("--import-current", "--id", "my-wsl", "--owner", "local")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("never-print-this-secret", result.stdout + result.stderr)
        self.assertIn('id = "my-wsl"', result.stdout)
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob("*")))
        self.record.write_text(result.stdout)
        self.doctor()

    def test_import_refuses_incomplete_selections(self):
        self.config.write_text('[data]\nprofile="wsl"\n')
        result = self.run_cli("--import-current", "--id", "my-wsl", "--owner", "local")
        self.assertEqual(result.returncode, 2)

    def test_no_record_fails_with_actionable_error(self):
        result = self.run_cli("--json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--machine", result.stderr)

    def test_unsupported_source_attributes_are_unverified(self):
        (self.source / "home/modify_dot_bashrc").write_text("must never execute")
        self.assertEqual(
            self.finding(self.doctor(), "source:modify_dot_bashrc")["status"],
            "unverified",
        )

    def test_version_is_not_claimed_from_presence(self):
        findings = self.doctor()
        self.assertEqual(self.finding(findings, "version:git")["status"], "unverified")

    def test_repository_cleanliness_remains_explicitly_unverified(self):
        subprocess.run(["/usr/bin/git", "init", "-q", str(self.source)], check=True)
        subprocess.run(["/usr/bin/git", "-C", str(self.source), "add", "."], check=True)
        subprocess.run(
            [
                "/usr/bin/git",
                "-C",
                str(self.source),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "fixture",
            ],
            check=True,
        )
        self.assertEqual(
            self.finding(self.doctor(), "repository:public")["status"], "unverified"
        )
        (self.source / "home/dot_bashrc").write_text("changed\n")
        self.assertEqual(
            self.finding(self.doctor(), "repository:public")["status"], "unverified"
        )

    def test_dangerous_git_configuration_cannot_spawn_helper(self):
        subprocess.run(["/usr/bin/git", "init", "-q", str(self.source)], check=True)
        marker = self.root / "git-helper-executed"
        subprocess.run(
            [
                "/usr/bin/git",
                "-C",
                str(self.source),
                "config",
                "core.fsmonitor",
                "touch " + str(marker),
            ],
            check=True,
        )
        self.doctor()
        self.assertFalse(marker.exists())

    def test_symlinked_source_file_is_not_followed(self):
        (self.source / "home/dot_bashrc").symlink_to(self.config)
        self.assertEqual(
            self.finding(self.doctor(), "source:dot_bashrc")["status"], "unverified"
        )

    def test_instruction_loading_is_not_claimed_verified(self):
        self.assertEqual(
            self.finding(self.doctor(), "agent-loading")["status"], "unverified"
        )

    def test_readonly_and_executable_attributes(self):
        (self.source / "home/readonly_dot_readonly").write_text("fixed")
        target = self.home / ".readonly"
        target.write_text("fixed")
        target.chmod(0o644)
        self.assertEqual(
            self.finding(self.doctor(), "file:.readonly")["status"], "drifted"
        )
        target.chmod(0o444)
        self.assertEqual(
            self.finding(self.doctor(), "file:.readonly")["status"], "matching"
        )
        (self.source / "home/executable_tool").write_text("fixed")
        target = self.home / "tool"
        target.write_text("fixed")
        target.chmod(0o644)
        self.assertEqual(self.finding(self.doctor(), "file:tool")["status"], "drifted")

    def test_disabled_work_must_not_be_implicitly_activated(self):
        self.record.write_text(
            RECORD.replace("overlays = []", 'overlays = ["work"]') + "work = false\n"
        )
        result = self.run_cli("--machine", str(self.record), "--json")
        self.assertEqual(result.returncode, 2)

    def test_symlink_destination_and_symlinked_parent(self):
        (self.source / "home/symlink_dot_alias").write_text("target\n")
        (self.home / ".alias").symlink_to("wrong")
        self.assertEqual(
            self.finding(self.doctor(), "file:.alias")["status"], "drifted"
        )
        (self.home / ".alias").unlink()
        (self.home / ".alias").symlink_to("target")
        self.assertEqual(
            self.finding(self.doctor(), "file:.alias")["status"], "matching"
        )
        (self.source / "home/dot_config/app").mkdir(parents=True)
        (self.source / "home/dot_config/app/settings").write_text("expected")
        (self.home / ".config/app").symlink_to(self.root)
        self.assertEqual(
            self.finding(self.doctor(), "file:.config/app/settings")["status"],
            "unverified",
        )

    def test_unknown_ignore_rules_do_not_claim_missing_targets(self):
        (self.source / "home/.chezmoiignore.tmpl").write_text('{{ output "false" }}')
        (self.source / "home/dot_bashrc").write_text("expected")
        self.assertEqual(
            self.finding(self.doctor(), "file:.bashrc")["status"], "unverified"
        )

    def test_bundle_decoy_is_not_executed(self):
        self.record.write_text(RECORD.replace("bundles = []", 'bundles = ["coding"]'))
        bindir = self.root / "bin"
        bindir.mkdir()
        marker = self.root / "tool-executed"
        decoy = bindir / "doctor-agent-decoy"
        decoy.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n')
        decoy.chmod(0o755)
        self.assertEqual(
            self.finding(self.doctor(), "tool:doctor-agent-decoy")["status"], "matching"
        )
        self.assertFalse(marker.exists())

    def test_revision_mismatch_is_drift(self):
        subprocess.run(["/usr/bin/git", "init", "-q", str(self.source)], check=True)
        subprocess.run(["/usr/bin/git", "-C", str(self.source), "add", "."], check=True)
        subprocess.run(
            [
                "/usr/bin/git",
                "-C",
                str(self.source),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "fixture",
            ],
            check=True,
        )
        self.record.write_text(RECORD + '[revisions]\npublic="' + "0" * 40 + '"\n')
        self.assertEqual(
            self.finding(self.doctor(), "revision:public")["status"], "drifted"
        )

    def test_json_error_is_not_a_success_document(self):
        self.record.write_text("invalid = true")
        result = self.run_cli("--machine", str(self.record), "--json")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")

    def test_human_and_json_exit_codes_agree(self):
        json_result = self.run_cli("--machine", str(self.record), "--json")
        human_result = self.run_cli("--machine", str(self.record))
        self.assertEqual(json_result.returncode, human_result.returncode)
        self.assertIn("missing", human_result.stdout)

    def test_incomplete_repository_check_prevents_success(self):
        self.record.write_text(
            RECORD.replace('profile = "wsl"', 'profile = "embedded"')
        )
        self.config.write_text(
            self.config.read_text().replace('profile="wsl"', 'profile="embedded"')
        )
        subprocess.run(["/usr/bin/git", "init", "-q", str(self.source)], check=True)
        subprocess.run(["/usr/bin/git", "-C", str(self.source), "add", "."], check=True)
        subprocess.run(
            [
                "/usr/bin/git",
                "-C",
                str(self.source),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "fixture",
            ],
            check=True,
        )
        revision = subprocess.check_output(
            ["/usr/bin/git", "-C", str(self.source), "rev-parse", "HEAD"], text=True
        ).strip()
        self.record.write_text(
            self.record.read_text() + '[revisions]\npublic="' + revision + '"\n'
        )
        result = self.run_cli("--machine", str(self.record), "--json")
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertEqual(
            [
                f["check"]
                for f in json.loads(result.stdout)["findings"]
                if f["status"] != "matching"
            ],
            ["repository:public"],
        )

    def test_git_clean_filters_are_never_executed(self):
        subprocess.run(["/usr/bin/git", "init", "-q", str(self.source)], check=True)
        tracked = self.source / "tracked.txt"
        tracked.write_text("first")
        subprocess.run(["/usr/bin/git", "-C", str(self.source), "add", "."], check=True)
        subprocess.run(
            [
                "/usr/bin/git",
                "-C",
                str(self.source),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "fixture",
            ],
            check=True,
        )
        marker = self.root / "filter-executed"
        (self.source / ".gitattributes").write_text("tracked.txt filter=evil\n")
        subprocess.run(
            [
                "/usr/bin/git",
                "-C",
                str(self.source),
                "config",
                "filter.evil.clean",
                'touch "' + str(marker) + '"; cat',
            ],
            check=True,
        )
        tracked.write_text("other")
        self.doctor()
        self.assertFalse(marker.exists(), "Git clean filter executed during doctor")

    def test_decoded_source_path_cannot_escape_home(self):
        (self.source / "home/dot_.").mkdir()
        (self.source / "home/dot_./outside").write_text("same")
        (self.root / "outside").write_text("same")
        findings = self.doctor()
        self.assertFalse(any(f["check"].startswith("file:../") for f in findings))
        self.assertTrue(
            any(
                f["status"] in {"blocked", "unverified"} and "dot_." in f["check"]
                for f in findings
            )
        )

    def test_unreadable_source_subtree_is_not_silently_skipped(self):
        directory = self.source / "home/dot_config"
        directory.mkdir()
        (directory / "settings").write_text("managed")
        directory.chmod(0)
        try:
            self.assertTrue(
                any(
                    f["check"] == "source-traversal" and f["status"] == "blocked"
                    for f in self.doctor()
                )
            )
        finally:
            directory.chmod(0o700)

    def test_directory_private_attribute_does_not_apply_to_child_file(self):
        directory = self.source / "home/private_dot_config"
        directory.mkdir()
        (directory / "settings").write_text("same")
        (self.home / ".config").chmod(0o700)
        (self.home / ".config/settings").write_text("same")
        (self.home / ".config/settings").chmod(0o644)
        findings = self.doctor()
        self.assertEqual(
            self.finding(findings, "file:.config/settings")["status"], "matching"
        )
        self.assertEqual(
            self.finding(findings, "directory:.config")["status"], "matching"
        )

    def test_developer_bundle_migration_keeps_explicit_selection(self):
        self.config.write_text(
            self.config.read_text() + "install_developer_tools=true\n"
        )
        result = self.run_cli("--import-current", "--id", "my-wsl", "--owner", "local")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.record.write_text(result.stdout)
        findings = self.doctor()
        self.assertEqual(
            self.finding(findings, "selection:install_developer_tools")["status"],
            "matching",
        )

    def test_selected_apps_imply_tool_prerequisites_in_inventory(self):
        self.config.write_text(
            self.config.read_text()
            + 'install_developer_tools=false\nagent_apps=["codex"]\n'
        )
        result = self.run_cli("--import-current", "--id", "my-wsl", "--owner", "local")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.record.write_text(result.stdout)
        findings = self.doctor()
        self.assertEqual(
            self.finding(findings, "selection:install_developer_tools")["status"],
            "matching",
        )

    def test_managed_requirements_and_version_gaps_follow_tools_catalog(self):
        catalog = self.source / "config/tools.lock.json"
        catalog.parent.mkdir()
        catalog.write_text(
            json.dumps(
                {
                    "developer": {
                        "apt": {"nodejs": "26.0.0"},
                        "binaries": {"catalog-only-tool": {"version": "1.2.3"}},
                        "npm": {"catalog-only-npm": "2.0.0"},
                        "python": {
                            "example": {
                                "version": "3.0.0",
                                "commands": ["catalog-python"],
                            }
                        },
                    },
                    "agents": {
                        "codex": {"command": "catalog-codex", "version": "4.0.0"},
                        "claude": {"command": "unselected-agent", "version": "5.0.0"},
                    },
                }
            )
        )
        binary = self.root / "bin/catalog-only-tool"
        binary.parent.mkdir()
        binary.write_text("#!/bin/sh\nexit 73\n")
        binary.chmod(0o755)
        self.record.write_text(
            RECORD.replace("bundles = []", 'bundles = ["developer"]')
            + 'apps=["codex"]\n'
        )
        self.config.write_text(
            self.config.read_text()
            + 'install_developer_tools=true\nagent_apps=["codex"]\n'
        )
        findings = self.doctor()
        self.assertEqual(
            self.finding(findings, "tool:catalog-only-tool")["status"], "matching"
        )
        self.assertEqual(
            self.finding(findings, "version:catalog-only-tool")["status"], "unverified"
        )
        self.assertEqual(
            self.finding(findings, "tool:catalog-only-npm")["status"], "missing"
        )
        self.assertEqual(
            self.finding(findings, "tool:catalog-python")["status"], "missing"
        )
        self.assertEqual(
            self.finding(findings, "tool:catalog-codex")["status"], "missing"
        )
        self.assertEqual(self.finding(findings, "tool:npm")["status"], "matching")
        self.assertFalse(
            any(item["check"] == "tool:unselected-agent" for item in findings)
        )


if __name__ == "__main__":
    unittest.main()
