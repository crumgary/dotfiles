"""Deploy the real source into fixture homes without executing installer scripts."""

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
CHEZMOI = shutil.which("chezmoi")
CONFIG = """[data]
github_username = "fixture"
git_user_name = "Deployment Fixture"
git_user_email = "fixture@example.invalid"
profile = "wsl"
work = false
install_agent_clis = false
wsl_windows_username = ""
bootstrap_priv_overlay = false
priv_repo_url = ""
bootstrap_work_overlay = false
work_repo_url = ""
internal_registries_exist = false
create_convenience_symlinks = false
convenience_symlink_dir = ""
personal_git_email = ""
"""


@unittest.skipUnless(CHEZMOI, "chezmoi is required for deployment integration tests")
class DeploymentTests(unittest.TestCase):
    def test_pi_runtime_is_private_on_fresh_and_existing_homes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "home"
            destination.mkdir()
            config = root / "config.toml"
            config.write_text(CONFIG)
            command = [
                CHEZMOI,
                "--source",
                str(SOURCE),
                "--destination",
                str(destination),
                "--config",
                str(config),
                "--cache",
                str(root / "cache"),
                "--persistent-state",
                str(root / "state.boltdb"),
                "--no-tty",
                "--no-pager",
                "--force",
                "apply",
                "--exclude",
                "scripts",
            ]
            for initial_mode in (None, 0o755):
                with self.subTest(initial_mode=initial_mode):
                    runtime = destination / ".pi/agent"
                    if initial_mode is not None:
                        runtime.chmod(initial_mode)
                    result = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        check=False,
                        env={**os.environ, "HOME": str(destination)},
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(stat.S_IMODE(runtime.stat().st_mode), 0o700)
                    self.assertTrue((runtime / "AGENTS.md").is_symlink())
                    self.assertTrue((destination / ".vimrc").is_file())
                    self.assertFalse((destination / ".config/nvim").exists())


@unittest.skipUnless(
    CHEZMOI and shutil.which("bwrap"),
    "chezmoi and bubblewrap are required for installer integration tests",
)
class PackageInstallerTests(unittest.TestCase):
    def test_ubuntu_26_installs_modern_tools_from_apt_without_release_downloads(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            bindir = root / "bin"
            bindir.mkdir()
            log = root / "apt.log"
            installed = root / "installed"
            for name, content in {
                "sudo": '#!/bin/sh\ncase "$1" in DEBIAN_FRONTEND=*) shift;; esac\nexec "$@"\n',
                "dpkg": '#!/bin/sh\ntest -f "' + str(installed) + '"\n',
                "apt-get": '#!/bin/sh\nprintf "%s\\n" "$*" >> "'
                + str(log)
                + '"\nif [ "$1" = install ]; then touch "'
                + str(installed)
                + '"; fi\n',
                "curl": "#!/bin/sh\nexit 88\n",
                "locale": '#!/bin/sh\nprintf "en_US.utf8\\n"\n',
            }.items():
                path = bindir / name
                path.write_text(content)
                path.chmod(0o755)
            # Existing commands simulate the PATH after apt installs its tools. Only
            # the distro-named fd/bat commands exist, to catch redundant downloads.
            for name in (
                "eza",
                "delta",
                "fdfind",
                "batcat",
                "zoxide",
                "fzf",
                "keychain",
                "glow",
                "starship",
            ):
                path = bindir / name
                path.write_text("#!/bin/sh\nexit 0\n")
                path.chmod(0o755)
            config = root / "config.toml"
            config.write_text(CONFIG)
            template = SOURCE / "home/run_onchange_before_install-packages.sh.tmpl"
            rendered = subprocess.run(
                [
                    CHEZMOI,
                    "--source",
                    str(SOURCE),
                    "--config",
                    str(config),
                    "--cache",
                    str(root / "cache"),
                    "--persistent-state",
                    str(root / "state"),
                    "execute-template",
                ],
                input=template.read_text(),
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            os_release = root / "os-release"
            os_release.write_text('ID=ubuntu\nVERSION_ID="26.04"\n')
            result = subprocess.run(
                [
                    "bwrap",
                    "--ro-bind",
                    "/",
                    "/",
                    "--bind",
                    str(root),
                    str(root),
                    "--ro-bind",
                    str(os_release),
                    "/etc/os-release",
                    "--dev-bind",
                    "/dev/null",
                    "/dev/null",
                    "--unshare-net",
                    "--",
                    "/bin/bash",
                    "-s",
                ],
                input=rendered.stdout,
                text=True,
                capture_output=True,
                check=False,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": str(bindir) + ":/usr/bin:/bin",
                },
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            commands = log.read_text()
            for package in (
                "eza",
                "bat",
                "fd-find",
                "zoxide",
                "fzf",
                "keychain",
                "glow",
                "git-delta",
                "starship",
                "vim",
            ):
                self.assertIn(package, commands.split())


class EditorPreferenceTests(unittest.TestCase):
    def test_shell_chooses_vim_when_neovim_is_also_installed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("vim", "nvim"):
                command = root / name
                command.write_text("#!/bin/sh\nexit 0\n")
                command.chmod(0o755)
            result = subprocess.run(
                [
                    "/bin/bash",
                    "-c",
                    'source "$1"; printf "%s %s" "$EDITOR" "$VISUAL"',
                    "test",
                    str(SOURCE / "home/dot_config/bash/00-env.sh"),
                ],
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "HOME": str(root),
                    "PATH": str(root) + ":/usr/bin:/bin",
                },
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "vim vim")


@unittest.skipUnless(CHEZMOI, "chezmoi is required for compatibility integration tests")
class UnifiedCompatibilityTests(unittest.TestCase):
    def test_app_selection_deploys_updater_and_browser_helper_without_bundle_flag(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            config = root / "config.toml"
            config.write_text(
                CONFIG + 'install_developer_tools=false\nagent_apps=["codex"]\n'
            )
            result = subprocess.run(
                [
                    CHEZMOI,
                    "--source",
                    str(SOURCE),
                    "--destination",
                    str(home),
                    "--config",
                    str(config),
                    "--cache",
                    str(root / "cache"),
                    "--persistent-state",
                    str(root / "state"),
                    "--no-tty",
                    "--force",
                    "apply",
                    "--exclude",
                    "scripts",
                ],
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "HOME": str(home)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((home / ".local/bin/dotfiles-update").is_symlink())
            self.assertTrue((home / ".local/bin/axi-chrome").is_file())

    def test_existing_baseline_configs_apply_across_profiles(self):
        for profile in ("wsl", "devbox", "lab", "embedded"):
            with (
                self.subTest(profile=profile),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                home = root / "home"
                home.mkdir()
                config = root / "config.toml"
                config.write_text(
                    CONFIG.replace('profile = "wsl"', 'profile = "' + profile + '"')
                )
                result = subprocess.run(
                    [
                        CHEZMOI,
                        "--source",
                        str(SOURCE),
                        "--destination",
                        str(home),
                        "--config",
                        str(config),
                        "--cache",
                        str(root / "cache"),
                        "--persistent-state",
                        str(root / "state"),
                        "--no-tty",
                        "--force",
                        "apply",
                        "--exclude",
                        "scripts",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    env={**os.environ, "HOME": str(home)},
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue((home / ".bashrc").is_file())
                self.assertFalse((home / ".local/bin/dotfiles-update").exists())

    def render_init(self, root, data):
        import tomllib

        config = root / "config.toml"
        config.write_text(data)
        source = root / "source"
        shutil.copytree(SOURCE / "home", source / "home")
        (source / ".chezmoiroot").write_text("home\n")
        result = subprocess.run(
            [
                CHEZMOI,
                "--source",
                str(source),
                "--destination",
                str(root / "home"),
                "--config",
                str(config),
                "--cache",
                str(root / "cache"),
                "--persistent-state",
                str(root / "state"),
                "--no-tty",
                "init",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return tomllib.loads(config.read_text())["data"]

    def test_reinit_preserves_main_legacy_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            data = CONFIG.replace(
                "install_agent_clis = false", "install_agent_clis = true"
            )
            data += 'install_developer_tools=false\nagent_apps_csv=""\n'
            result = self.render_init(Path(temporary), data)
            self.assertTrue(result["install_agent_clis"])

    def test_reinit_preserves_edited_app_list_over_stale_prompt_answer(self):
        with tempfile.TemporaryDirectory() as temporary:
            data = (
                CONFIG
                + 'install_developer_tools=true\nagent_apps=["codex"]\nagent_apps_csv="claude"\n'
            )
            result = self.render_init(Path(temporary), data)
            self.assertEqual(result["agent_apps"], ["codex"])
            self.assertEqual(result["agent_apps_csv"], "codex")
