"""Behavioral installer tests; every home is a temporary --home target."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("neon_installer", Path(__file__).parents[1] / "install.py")
INSTALL = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = INSTALL
SPEC.loader.exec_module(INSTALL)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        environment = mock.patch.dict(os.environ, {key: value for key, value in os.environ.items()
                                                   if key not in ("SHELL", "ZDOTDIR")}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.base = Path(self.tmp.name)
        self.checkout = self.base / "repo"
        self.repo = self.checkout / "neon"
        self.home = self.base / "home"
        self.repo.mkdir(parents=True)
        self.home.mkdir()
        (self.checkout / ".gitmodules").write_text(
            '[submodule ".config/nvim"]\n\tpath = .config/nvim\n'
            '\turl = git@github.com:calveshelder/kickstart.nvim.git\n')
        self.kickstart = self.checkout / ".config/nvim"
        self.kickstart.mkdir(parents=True)
        (self.kickstart / "init.lua").write_text("-- Original Kickstart fixture\n")
        for name in ("bin/neon", "bin/neon-copy", "bin/tmux-sessionizer", "shell/init.bash", "shell/profile.bash", "shell/init.zsh",
                     "nvim/init.lua", "config/tmux/tmux.conf", "config/starship.toml",
                     "config/ghostty/config", "config/atuin/config.toml", "vendor/shell-arena/arena.bash"):
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# fixture\n")
        self.installer = INSTALL.Installer(self.repo, self.home)

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, relative, text):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def install(self, components={"shell", "nvim", "tmux", "starship", "arena"}, mode="merge", profile="personal", shell="bash"):
        changes = self.installer.plan(profile, components, mode, shell)
        return self.installer.apply(changes, profile)

    def snapshot(self):
        return {str(path.relative_to(self.home)): INSTALL.fingerprint(path)
                for path in self.home.rglob("*")}

    def test_plan_is_read_only_and_components_limit_scope(self):
        self.put(".bashrc", "export KEEP_ME=yes\n")
        before = self.snapshot()
        changes = self.installer.plan("personal", {"nvim"})
        self.assertEqual(before, self.snapshot())
        self.assertIn(".config/nvim", {change.relative for change in changes})
        self.assertNotIn(".bashrc", {change.relative for change in changes})
        self.assertFalse(self.installer.backups.exists())

    def test_existing_directory_is_moved_intact_and_restored(self):
        self.put(".config/nvim/init.lua", "print('my original')\n")
        self.put(".config/nvim/lua/custom.lua", "return {keep = true}\n")
        identifier = self.install({"nvim"})
        self.assertTrue((self.home / ".config/nvim").is_symlink())
        backup, manifest = self.installer.load_manifest(identifier)
        entry = next(item for item in manifest["entries"] if item["path"] == ".config/nvim")
        self.assertEqual((backup / entry["backup"] / "lua/custom.lua").read_text(), "return {keep = true}\n")
        self.installer.restore(identifier)
        self.assertFalse((self.home / ".config/nvim").is_symlink())
        self.assertEqual((self.home / ".config/nvim/init.lua").read_text(), "print('my original')\n")

    def test_second_apply_is_idempotent_without_extra_backup(self):
        self.install()
        before = self.snapshot()
        self.assertEqual(self.installer.plan("personal", {"shell", "nvim", "tmux", "starship", "arena"}), [])
        self.assertIsNone(self.install())
        self.assertEqual(before, self.snapshot())
        self.assertEqual((self.home / ".bashrc").read_text().count(INSTALL.BEGIN), 1)

    def test_merge_preserves_exports_and_migrates_only_known_sources(self):
        original = ('export KEEP_ME="hello"\n'
                    '[[ -r "$HOME/.config/dev-shell/init.bash" ]] && source "$HOME/.config/dev-shell/init.bash"\n'
                    '[[ -r "$HOME/.local/share/shell-arena/arena.bash" ]] && source "$HOME/.local/share/shell-arena/arena.bash" # shell-arena\n'
                    'source ~/company-setup.bash\n'
                    'source "$HOME/.config/dev-shell/init.bash"; echo "compound stays"\n')
        self.put(".bashrc", original)
        identifier = self.install({"shell"})
        result = (self.home / ".bashrc").read_text()
        self.assertIn('export KEEP_ME="hello"', result)
        self.assertIn('source ~/company-setup.bash\n', result)
        self.assertIn('source "$HOME/.config/dev-shell/init.bash"; echo "compound stays"', result)
        self.assertEqual(result.count("# Migrated to neon-dev:"), 2)
        self.installer.restore(identifier)
        self.assertEqual((self.home / ".bashrc").read_text(), original)

    def test_clean_mode_backs_up_startup_and_leaves_profile_untouched(self):
        rc = self.put(".bashrc", "source ~/old-and-slow.sh\nexport WORK_KEY=value\n")
        self.put(".bash_profile", "source ~/.profile\n")
        profile = self.put(".profile", "export PROFILE_UNTOUCHED=yes\n")
        before_profile = profile.read_bytes()
        identifier = self.install({"shell"}, mode="clean")
        self.assertNotIn("old-and-slow", rc.read_text())
        self.assertNotIn("WORK_KEY", rc.read_text())
        self.assertEqual(profile.read_bytes(), before_profile)
        self.installer.restore(identifier)
        self.assertIn("old-and-slow", rc.read_text())

    def test_existing_atuin_config_is_not_replaced(self):
        config = self.put(".config/atuin/config.toml", "sync_address = 'https://my-server'\n")
        self.install({"shell"})
        self.assertFalse(config.is_symlink())
        self.assertEqual(config.read_text(), "sync_address = 'https://my-server'\n")

    def test_zsh_only_preserves_bash_and_login_files(self):
        originals = {name: self.put(name, f"# keep {name}\n").read_bytes()
                     for name in (".bashrc", ".bash_profile", ".zprofile", ".zshenv", ".zlogin")}
        self.put(".zshrc", "# original zsh setup\n")
        identifier = self.install({"shell"}, mode="clean", shell="zsh")
        rc = (self.home / ".zshrc").read_text()
        self.assertIn("/shell/init.zsh", rc)
        self.assertIn("local.zsh", rc)
        self.assertNotIn("original zsh setup", rc)
        for name, original in originals.items():
            self.assertEqual((self.home / name).read_bytes(), original)
        self.assertEqual(self.installer.plan("personal", {"shell"}, "clean", "zsh"), [])
        self.installer.restore(identifier)
        self.assertEqual((self.home / ".zshrc").read_text(), "# original zsh setup\n")

    def test_zsh_merge_preserves_existing_text_and_symlink_source(self):
        source = self.checkout / "work.zshrc"
        source.write_text("# existing completion and PATH\nexport WORK=1\n")
        (self.home / ".zshrc").symlink_to(source)
        identifier = self.install({"shell"}, shell="zsh")
        self.assertFalse((self.home / ".zshrc").is_symlink())
        self.assertIn("export WORK=1", (self.home / ".zshrc").read_text())
        self.assertEqual(source.read_text(), "# existing completion and PATH\nexport WORK=1\n")
        self.installer.restore(identifier)
        self.assertEqual((self.home / ".zshrc").resolve(), source)

    def test_both_shells_restore_their_own_originals(self):
        for name in (".bashrc", ".bash_profile", ".zshrc"):
            self.put(name, f"# original {name}\n")
        identifier = self.install({"shell"}, mode="clean", shell="both")
        for name in (".bashrc", ".bash_profile", ".zshrc"):
            self.assertIn(INSTALL.BEGIN, (self.home / name).read_text())
        self.installer.restore(identifier)
        for name in (".bashrc", ".bash_profile", ".zshrc"):
            self.assertEqual((self.home / name).read_text(), f"# original {name}\n")

    def test_zsh_honors_home_local_zdotdir(self):
        with mock.patch.dict(os.environ, {"ZDOTDIR": str(self.home / ".config/zsh")}):
            identifier = self.install({"shell"}, shell="zsh")
            self.assertTrue((self.home / ".config/zsh/.zshrc").is_file())
            self.assertFalse((self.home / ".zshrc").exists())
            self.installer.restore(identifier)
            self.assertFalse((self.home / ".config/zsh/.zshrc").exists())

    def test_zsh_refuses_external_or_relative_zdotdir_without_changes(self):
        for value in (str(self.base / "outside"), "relative-dir", "", str(self.home / "../outside")):
            with self.subTest(zdotdir=value), mock.patch.dict(os.environ, {"ZDOTDIR": value}):
                before = self.snapshot()
                with self.assertRaisesRegex(INSTALL.InstallError, "ZDOTDIR"):
                    self.install({"shell"}, shell="zsh")
                self.assertEqual(self.snapshot(), before)

    def test_auto_selects_zsh_from_shell_environment(self):
        with mock.patch.dict(os.environ, {"SHELL": "/bin/zsh"}):
            changes = self.installer.plan("personal", {"shell"}, shell="auto")
        paths = {change.relative for change in changes}
        self.assertIn(".zshrc", paths)
        self.assertNotIn(".bashrc", paths)
        self.assertNotIn(".bash_profile", paths)

    def test_cli_auto_defaults_to_zsh_without_writing_in_preview(self):
        script = self.repo / "install.py"
        script.write_bytes(Path(INSTALL.__file__).read_bytes())
        environment = os.environ.copy()
        environment["SHELL"] = "/bin/zsh"
        before = self.snapshot()
        result = subprocess.run([sys.executable, str(script), "plan", "--profile", "personal",
                                 "--components", "shell", "--home", str(self.home)],
                                capture_output=True, text=True, env=environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("~/.zshrc", result.stdout)
        self.assertNotIn("~/.bashrc", result.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_tmux_only_installs_clipboard_helper_without_shell_startup(self):
        self.install({"tmux"})
        helper = self.home / ".local/bin/neon-copy"
        self.assertTrue(helper.is_symlink())
        self.assertEqual(helper.resolve(), self.repo / "bin/neon-copy")
        self.assertFalse((self.home / ".bashrc").exists())
        self.assertFalse((self.home / ".bash_profile").exists())

    def test_local_overrides_and_extra_machine_keys_survive(self):
        override = self.put(".config/neon/local.bash", "export MY_SETTING=1\n")
        self.put(".config/neon/local.lua", "return {local_setting = true}\n")
        self.put(".config/neon/machine.json", '{"profile":"personal","my_key":"keep"}\n')
        self.install({"nvim"}, profile="work")
        data = json.loads((self.home / ".config/neon/machine.json").read_text())
        self.assertEqual(data, {"schema": 1, "profile": "work", "my_key": "keep"})
        self.assertIn("NEON_PROFILE='work'", (self.home / ".config/neon/machine.bash").read_text())
        self.assertEqual(override.read_text(), "export MY_SETTING=1\n")

    def test_failed_install_rolls_back_original_files(self):
        original = self.put(".config/nvim/init.lua", "original\n")
        self.put(".bashrc", "export ORIGINAL=yes\n")
        implementation = self.installer.install_change
        counter = 0

        def fail_later(change, path):
            nonlocal counter
            counter += 1
            if change.relative == ".config/nvim":
                raise OSError("simulated disk failure")
            implementation(change, path)

        with mock.patch.object(self.installer, "install_change", side_effect=fail_later):
            with self.assertRaisesRegex(INSTALL.InstallError, "Original files restored"):
                self.install()
        self.assertGreater(counter, 1)
        self.assertEqual(original.read_text(), "original\n")
        self.assertFalse((self.home / ".config/nvim").is_symlink())
        self.assertEqual((self.home / ".bashrc").read_text(), "export ORIGINAL=yes\n")
        self.assertFalse((self.home / ".config/neon/root").exists())

    def test_restore_refuses_edited_file_before_changing_any_path(self):
        self.put(".bashrc", "export ORIGINAL=yes\n")
        identifier = self.install()
        rc = self.home / ".bashrc"
        rc.write_text(rc.read_text() + "export ADDED_AFTER_INSTALL=yes\n")
        before = self.snapshot()
        with self.assertRaisesRegex(INSTALL.InstallError, "before changing anything"):
            self.installer.restore(identifier)
        self.assertEqual(self.snapshot(), before)
        self.assertIn("ADDED_AFTER_INSTALL", rc.read_text())

    def test_restore_refuses_changed_symlink(self):
        identifier = self.install({"nvim"})
        path = self.home / ".config/nvim"
        path.unlink()
        path.symlink_to(self.repo / "config/ghostty")
        with self.assertRaisesRegex(INSTALL.InstallError, "before changing anything"):
            self.installer.restore(identifier)
        self.assertEqual(os.readlink(path), str(self.repo / "config/ghostty"))

    def test_restore_keeps_edits_inside_repo(self):
        self.put(".config/nvim/init.lua", "old home config\n")
        identifier = self.install({"nvim"})
        (self.home / ".config/nvim/init.lua").write_text("new repo config\n")
        self.installer.restore(identifier)
        self.assertEqual((self.home / ".config/nvim/init.lua").read_text(), "old home config\n")
        self.assertEqual((self.kickstart / "init.lua").read_text(), "new repo config\n")

    def test_symlink_ancestors_are_rejected(self):
        elsewhere = self.base / "elsewhere"
        elsewhere.mkdir()
        (self.home / ".config").symlink_to(elsewhere)
        with self.assertRaisesRegex(INSTALL.InstallError, "symlink directory"):
            self.installer.plan("personal", {"nvim"})
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_symlinked_startup_is_backed_up_without_modifying_source(self):
        original = self.base / "external.bashrc"
        original.write_text("external remains\n")
        (self.home / ".bashrc").symlink_to(original)
        identifier = self.install({"shell"})
        self.assertFalse((self.home / ".bashrc").is_symlink())
        self.assertIn("external remains", (self.home / ".bashrc").read_text())
        self.assertEqual(original.read_text(), "external remains\n")
        self.installer.restore(identifier)
        self.assertTrue((self.home / ".bashrc").is_symlink())
        self.assertEqual((self.home / ".bashrc").resolve(), original)

    def test_clean_can_replace_and_restore_broken_startup_link(self):
        path = self.home / ".bashrc"
        path.symlink_to("missing-startup")
        with self.assertRaisesRegex(INSTALL.InstallError, "Cannot merge unreadable"):
            self.installer.plan("personal", {"shell"})
        identifier = self.install({"shell"}, mode="clean")
        self.assertTrue(path.is_file())
        self.assertFalse(path.is_symlink())
        self.installer.restore(identifier)
        self.assertTrue(path.is_symlink())
        self.assertEqual(os.readlink(path), "missing-startup")

    def test_plan_rejects_malformed_markers(self):
        self.put(".bashrc", INSTALL.BEGIN + "\n")
        with self.assertRaisesRegex(INSTALL.InstallError, "Malformed"):
            self.installer.plan("personal", {"shell"})

    def test_installer_cannot_move_its_own_repo(self):
        # Placing the checkout at ~/.config/nvim would make a replacement self-destructive.
        home = self.base / "nested-home"
        home.mkdir()
        (home / ".config").mkdir()
        self.checkout.rename(home / ".config/nvim")
        installer = INSTALL.Installer(home / ".config/nvim/neon", home)
        with self.assertRaisesRegex(INSTALL.InstallError, "would move the repository"):
            installer.plan("personal", {"nvim"})

    def test_missing_submodule_fails_before_home_changes(self):
        (self.kickstart / "init.lua").unlink()
        before = self.snapshot()
        with self.assertRaisesRegex(INSTALL.InstallError, "git submodule update --init --recursive"):
            self.install({"nvim"})
        self.assertEqual(self.snapshot(), before)
        self.install({"shell"})
        self.assertFalse((self.home / ".config/nvim").exists())

    def test_submodule_declaration_is_required(self):
        manifest = self.checkout / ".gitmodules"
        for content in ("", '[submodule "other"]\npath = .config/other\nurl = example\n',
                        '[submodule "nvim"]\npath = .config/nvim\n'):
            with self.subTest(content=content):
                manifest.write_text(content)
                with self.assertRaisesRegex(INSTALL.InstallError, "Expected one .gitmodules entry"):
                    self.installer.plan("personal", {"nvim"})
        manifest.unlink()
        with self.assertRaisesRegex(INSTALL.InstallError, "Cannot read.*.gitmodules"):
            self.installer.plan("personal", {"nvim"})

    def test_nvim_link_targets_kickstart_and_preserves_repository_sources(self):
        manifest = self.checkout / ".gitmodules"
        original_manifest = manifest.read_bytes()
        original_init = (self.kickstart / "init.lua").read_bytes()
        self.install({"nvim"})
        self.assertEqual((self.home / ".config/nvim").resolve(), self.kickstart)
        self.assertEqual((self.home / ".config/neon/root").resolve(), self.repo)
        self.assertEqual(manifest.read_bytes(), original_manifest)
        self.assertEqual((self.kickstart / "init.lua").read_bytes(), original_init)

    def test_repo_at_home_refuses_to_move_its_actual_submodule(self):
        # A dotfiles checkout can be at HOME; replacing its submodule itself
        # would strand the linked config and alter the user's Git checkout.
        self.installer = INSTALL.Installer(self.repo, self.checkout)
        before_init = (self.kickstart / "init.lua").read_bytes()
        with self.assertRaisesRegex(INSTALL.InstallError, "would move the repository"):
            self.installer.plan("personal", {"nvim"})
        self.assertEqual((self.kickstart / "init.lua").read_bytes(), before_init)

    def test_existing_home_symlink_to_submodule_is_left_in_place(self):
        target = self.home / ".config/nvim"
        target.parent.mkdir()
        target.symlink_to(self.kickstart)
        changes = self.installer.plan("personal", {"nvim"})
        self.assertNotIn(".config/nvim", [change.relative for change in changes])
        self.installer.apply(changes, "personal")
        self.assertEqual(target.resolve(), self.kickstart)

    def test_broken_existing_symlink_is_backed_up(self):
        target = self.home / ".config/starship.toml"
        target.parent.mkdir()
        target.symlink_to("missing-old-file.toml")
        identifier = self.install({"starship"})
        self.installer.restore(identifier)
        self.assertTrue(target.is_symlink())
        self.assertEqual(os.readlink(target), "missing-old-file.toml")

    def test_relative_and_foreign_backup_ids_are_rejected(self):
        with self.assertRaises(INSTALL.InstallError):
            self.installer.restore("../../somewhere")
        identifier = self.install({"nvim"})
        backup, manifest = self.installer.load_manifest(identifier)
        manifest["home"] = "/another-home"
        INSTALL.write_json(backup / "manifest.json", manifest)
        with self.assertRaisesRegex(INSTALL.InstallError, "different home"):
            self.installer.restore(identifier)

    def test_real_bash_can_source_generated_clean_startup(self):
        self.install({"shell"}, mode="clean")
        # Syntax checking reads both actual generated files and does not repurpose HOME.
        for filename in (".bashrc", ".bash_profile", ".config/neon/machine.bash"):
            result = subprocess.run(["bash", "-n", str(self.home / filename)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_changed_file_between_plan_and_apply_is_preserved(self):
        rc = self.put(".bashrc", "export BEFORE=1\n")
        changes = self.installer.plan("personal", {"shell"}, "clean")
        rc.write_text("export EDITED_AFTER_PLAN=1\n")
        with self.assertRaisesRegex(INSTALL.InstallError, "changed after planning"):
            self.installer.apply(changes, "personal")
        self.assertEqual(rc.read_text(), "export EDITED_AFTER_PLAN=1\n")
        self.assertFalse((self.home / ".config/neon/root").exists())

    def test_mutation_lock_rejects_second_installer(self):
        other = INSTALL.Installer(self.repo, self.home)
        with self.installer.lock():
            with self.assertRaisesRegex(INSTALL.InstallError, "Another Neon"):
                with other.lock():
                    self.fail("A second mutation must not obtain the lock")

    def test_restore_failure_reinstates_current_installation(self):
        self.put(".config/neon/machine.json", '{"profile":"work"}\n')
        self.put(".config/nvim/init.lua", "old nvim\n")
        identifier = self.install({"nvim"})
        backup, manifest = self.installer.load_manifest(identifier)
        entry = next(item for item in manifest["entries"] if item["path"] == ".config/neon/machine.json")
        fail_at = backup / entry["backup"]
        original_replace = os.replace
        fired = False

        def fail_once(source, target):
            nonlocal fired
            if Path(source) == fail_at and not fired:
                fired = True
                raise OSError("simulated restore failure")
            return original_replace(source, target)

        with mock.patch.object(INSTALL.os, "replace", side_effect=fail_once):
            with self.assertRaisesRegex(INSTALL.InstallError, "Restore failed"):
                self.installer.restore(identifier)
        self.assertTrue(fired)
        self.assertTrue((self.home / ".config/nvim").is_symlink())
        self.assertEqual(json.loads((self.home / ".config/neon/machine.json").read_text())["profile"], "personal")
        self.assertEqual(self.installer.load_manifest(identifier)[1]["status"], "applied")
        self.installer.restore(identifier)
        self.assertEqual((self.home / ".config/nvim/init.lua").read_text(), "old nvim\n")

    def test_cli_home_option_does_not_change_environment_or_write_during_plan(self):
        script = self.repo / "install.py"
        script.write_bytes(Path(INSTALL.__file__).read_bytes())
        original_home = os.environ.get("HOME")
        before = self.snapshot()
        result = subprocess.run([sys.executable, str(script), "plan", "--profile", "personal",
                                 "--components", "nvim", "--home", str(self.home)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No files were written", result.stdout)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(os.environ.get("HOME"), original_home)


if __name__ == "__main__":
    unittest.main()
