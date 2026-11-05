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


@unittest.skipUnless(
    CHEZMOI and shutil.which("bwrap"),
    "chezmoi and bubblewrap are required for installer integration tests",
)
class BaselineDnfTests(unittest.TestCase):
    def run_baseline(
        self, distro="almalinux", version="9.7", privileged=True, minimal_curl=False
    ):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        bindir = root / "bin"
        bindir.mkdir()
        home = root / "home"
        home.mkdir()
        log = root / "commands"
        if minimal_curl:
            (root / "pkg-curl-minimal").touch()
        # Only fixture commands are on PATH, so the host apt cannot win detection.
        for name in ("mkdir", "uname", "grep", "touch", "awk"):
            (bindir / name).symlink_to(shutil.which(name))
        commands = {
            "id": "#!/bin/sh\necho " + ("0" if privileged else "1000") + "\n",
            "rpm": '#!/bin/sh\n[ "$1" = -q ] || exit 90\n'
            'case "$2" in @*) exit 1;; esac\n'
            'test -f "$FIXTURE_ROOT/pkg-$2"\n',
            "dnf": """#!/bin/sh
printf '%s\n' "$*" >> "$FIXTURE_ROOT/commands"
case "$*" in
    *"group list"*)
        case "$*" in *--installed*--ids*|*--hidden*--ids*) exit 94;; esac
        group=""
        for argument do group="$argument"; done
        if test -f "$FIXTURE_ROOT/pkg-@$group"; then
            printf 'Installed Groups:\n   Development Tools (%s)\n' "$group"
        else
            printf 'Available Groups:\n   Development Tools (%s)\n' "$group"
        fi
        exit 0;;
    "config-manager --set-enabled crb") touch "$FIXTURE_ROOT/crb"; exit 0;;
    "install -y "*)
        shift 2
        for p do
            if [ "$FIXTURE_DISTRO" = almalinux ] && [ "$p" = @development-tools ]; then exit 95; fi
            if [ "$p" = curl ] && test -f "$FIXTURE_ROOT/pkg-curl-minimal"; then exit 96; fi
            case "$p" in
                gh|ShellCheck)
                    if [ "$FIXTURE_DISTRO" = almalinux ]; then
                        test -f "$FIXTURE_ROOT/pkg-epel-release" || exit 91
                        test -f "$FIXTURE_ROOT/crb" || exit 92
                    fi;;
            esac
            touch "$FIXTURE_ROOT/pkg-$p"
        done
        exit 0;;
esac
exit 93
""",
            "curl": "#!/bin/sh\nexit 88\n",
        }
        for name in (
            "eza",
            "delta",
            "fd",
            "bat",
            "zoxide",
            "fzf",
            "keychain",
            "glow",
            "starship",
        ):
            commands[name] = "#!/bin/sh\nexit 0\n"
        for name, content in commands.items():
            path = bindir / name
            path.write_text(content)
            path.chmod(0o755)
        config = root / "config.toml"
        config.write_text(CONFIG)
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
            input=(
                SOURCE / "home/run_onchange_before_install-packages.sh.tmpl"
            ).read_text(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(rendered.returncode, 0, rendered.stderr)
        os_release = root / "os-release"
        os_release.write_text("ID=" + distro + '\nVERSION_ID="' + version + '"\n')
        command = [
            shutil.which("bwrap"),
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
        ]
        results = []
        mutations = []
        for _ in range(2):
            results.append(
                subprocess.run(
                    command,
                    input=rendered.stdout,
                    text=True,
                    capture_output=True,
                    check=False,
                    env={
                        **os.environ,
                        "HOME": str(home),
                        "PATH": str(bindir),
                        "FIXTURE_ROOT": str(root),
                        "FIXTURE_DISTRO": distro,
                    },
                )
            )
            mutations.append(
                [
                    line
                    for line in (log.read_text().splitlines() if log.exists() else [])
                    if "group list" not in line
                ]
            )
        return root, results, mutations

    def test_fresh_alma_9_enables_epel_and_crb_before_baseline_packages(self):
        root, results, mutations = self.run_baseline()
        for result in results:
            self.assertEqual(result.returncode, 0, result.stderr)
        for package in ("gh", "ShellCheck", "dnf-plugins-core", "epel-release"):
            self.assertTrue((root / ("pkg-" + package)).exists(), package)
        self.assertEqual(
            mutations[0], mutations[1], "second apply changed system packages"
        )

    def test_fedora_baseline_group_does_not_trigger_repeated_installs(self):
        root, results, mutations = self.run_baseline("fedora", "43")
        for result in results:
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((root / "pkg-epel-release").exists())
        self.assertEqual(
            mutations[0], mutations[1], "installed group was queried as an RPM"
        )

    def test_alma_retains_existing_minimal_curl_provider(self):
        root, results, mutations = self.run_baseline(minimal_curl=True)
        for result in results:
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((root / "pkg-curl-minimal").exists())
        self.assertFalse((root / "pkg-curl").exists())
        self.assertEqual(mutations[0], mutations[1])

    def test_alma_without_sudo_skips_all_system_mutations(self):
        root, results, mutations = self.run_baseline(privileged=False)
        for result in results:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("no sudo", result.stderr)
        self.assertEqual(mutations, [[], []])
        self.assertFalse((root / "pkg-epel-release").exists())


class WslSmokeAliasTests(unittest.TestCase):
    def test_smoke_accepts_upstream_and_debian_tool_names(self):
        for aliases in (("bat", "fd"), ("batcat", "fdfind"), ("bat",), ("fd",)):
            with (
                self.subTest(aliases=aliases),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                bindir = root / "bin"
                bindir.mkdir()
                for name in ("bash", "grep"):
                    (bindir / name).symlink_to(shutil.which(name))
                for name in (
                    "git",
                    "curl",
                    "eza",
                    "rg",
                    "zoxide",
                    "fzf",
                    "tmux",
                    "delta",
                    "starship",
                    "vim",
                    "keychain",
                    "fc-list",
                ) + aliases:
                    path = bindir / name
                    output = "delta" if name == "git" else "JetBrainsMono Nerd Font"
                    path.write_text("#!/bin/sh\nprintf '%s\\n' '" + output + "'\n")
                    path.chmod(0o755)
                for relative in (
                    ".bashrc",
                    ".vimrc",
                    ".tmux.conf",
                    ".config/starship.toml",
                    ".local/share/blesh/ble.sh",
                ):
                    path = root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("# source ~/.config/bash/00-env.sh\n")
                result = subprocess.run(
                    ["/bin/bash", str(SOURCE / "scripts/smoke-test-wsl.sh")],
                    text=True,
                    capture_output=True,
                    check=False,
                    env={**os.environ, "HOME": str(root), "PATH": str(bindir)},
                )
                if len(aliases) == 2:
                    self.assertEqual(
                        result.returncode, 0, result.stdout + result.stderr
                    )
                    self.assertIn("ALL SMOKE TESTS PASSED", result.stdout)
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("MISSING:", result.stdout)
