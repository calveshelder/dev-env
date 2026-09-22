import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('neon_cli', ROOT / 'lib/neon_cli.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class CLITests(unittest.TestCase):
    def test_nested_go_module_wins_over_repo_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            subprocess.run(['git', 'init', '-q', str(base)], check=True)
            project = base / 'challenges/pokedex'
            project.mkdir(parents=True)
            (project / 'go.mod').write_text('module example.test/pokedex\n')
            nested = project / 'internal'
            nested.mkdir()
            self.assertEqual(cli.project_root(nested), project)

    def test_custom_check_preserves_argv_and_exit_status(self):
        with mock.patch.object(cli, 'project_root', return_value=Path('/tmp')), mock.patch.object(cli, 'run', return_value=7) as run:
            result = cli.tests(argparse.Namespace(command=['--', 'printf', '$(not-a-command); space']))
        self.assertEqual(result, 7)
        run.assert_called_once_with(['printf', '$(not-a-command); space'], cwd=Path('/tmp'))

    def test_no_automatic_test_in_noninteractive_use(self):
        with mock.patch.object(cli, 'project_root', return_value=Path('/tmp')), \
             mock.patch.object(cli, 'test_options', return_value=[('Go', ['go', 'test', './...'])]), \
             mock.patch.object(cli.sys.stdin, 'isatty', return_value=False), mock.patch.object(cli, 'run') as run:
            self.assertEqual(cli.tests(argparse.Namespace(command=[])), 2)
        run.assert_not_called()

    def test_zero_choice_cannot_select_last_test(self):
        with mock.patch.object(cli, 'project_root', return_value=Path('/tmp')), \
             mock.patch.object(cli, 'test_options', return_value=[('Go', ['go', 'test', './...'])]), \
             mock.patch.object(cli.sys.stdin, 'isatty', return_value=True), mock.patch('builtins.input', return_value='0'), \
             mock.patch.object(cli, 'run') as run:
            self.assertEqual(cli.tests(argparse.Namespace(command=[])), 2)
        run.assert_not_called()

    def test_venv_interpreter_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'pyproject.toml').touch()
            (root / '.venv/bin').mkdir(parents=True)
            (root / '.venv/bin/python').touch()
            self.assertEqual(cli.test_options(root)[0][1][0], str(root / '.venv/bin/python'))

    def test_launcher_resolves_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            link = Path(tmp) / 'neon'
            link.symlink_to(ROOT / 'bin/neon')
            result = subprocess.run([sys.executable, str(link), '--help'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('portable command deck', result.stdout)

    def test_afplay_and_paplay_volume_arguments(self):
        spec = importlib.util.spec_from_file_location('neon_audio', ROOT / 'vendor/shell-arena/arena_audio.py')
        audio = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audio)
        self.assertEqual(audio.player_command('/usr/bin/afplay', Path('/a b.wav'), 40), ['/usr/bin/afplay', '-v', '0.4', '/a b.wav'])
        self.assertEqual(audio.player_command('/usr/bin/paplay', Path('/a b.wav'), 25), ['/usr/bin/paplay', '--volume=16384', '/a b.wav'])


if __name__ == '__main__':
    unittest.main()
