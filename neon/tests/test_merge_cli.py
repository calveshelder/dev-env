"""Regression coverage for the nested repo, editor launcher and existing Brew tools."""
import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('neon_merge_cli', ROOT / 'lib/neon_cli.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class MergeCLI(unittest.TestCase):
    def test_brew_only_suggests_missing_tools(self):
        found = {'brew', 'nvim', 'tmux', 'git', 'python3', 'zsh'}
        listing = subprocess.CompletedProcess([], 0, 'neovim\ntmux\npython@3.14\nfzf\n', '')
        output = io.StringIO()
        with mock.patch.object(cli.sys, 'platform', 'darwin'), \
             mock.patch.dict(cli.os.environ, {'NEON_SHELL': 'zsh'}), \
             mock.patch.object(cli.shutil, 'which', side_effect=lambda name: '/opt/homebrew/bin/' + name if name in found else None), \
             mock.patch.object(cli.subprocess, 'run', return_value=listing) as run, \
             contextlib.redirect_stdout(output):
            self.assertEqual(cli.deps('macos'), 0)
        command = next(line for line in output.getvalue().splitlines() if line.startswith('brew install '))
        packages = command.split()[2:]
        for name in ('neovim', 'tmux', 'git', 'python', 'fzf', 'bash', 'zsh'):
            self.assertNotIn(name, packages)
        self.assertIn('starship', packages)
        run.assert_called_once_with(['brew', 'list', '--formula', '-1'], capture_output=True, text=True, timeout=15)

    def test_editor_argv_is_literal_and_clean_mode_wins(self):
        with mock.patch.object(cli, 'run', return_value=17) as run:
            self.assertEqual(cli.editor(['--', 'file space;literal.go']), 17)
            self.assertEqual(run.call_args.args[0], ['nvim', '-u', str(ROOT / 'nvim/init.lua'), 'file space;literal.go'])
        with mock.patch.object(cli, 'run', return_value=0) as run:
            cli.editor(['--clean', 'file.go'])
            self.assertEqual(run.call_args.args[0], ['nvim', '--clean', 'file.go'])

    def test_nested_source_sync_sees_parent_and_refuses_dirty_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            neon = root / 'neon'
            neon.mkdir()
            (root / 'important-work.txt').write_text('keep this\n')
            with mock.patch.object(cli, 'ROOT', neon), mock.patch.object(cli, 'run') as run:
                self.assertEqual(cli.sync(True), 1)
                run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
