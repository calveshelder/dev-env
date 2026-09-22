"""Regression checks for literal paths, persistent sessions and clipboard routing."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

def load_script(name):
    loader = importlib.machinery.SourceFileLoader(name.replace('-', '_'), str(ROOT / 'bin' / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module

picker = load_script('tmux-sessionizer')
clipboard = load_script('neon-copy')

class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='neon terminal ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_same_basename_is_distinct_and_symlink_reuses_session(self):
        first, second = self.root / 'work/api', self.root / 'personal/api'
        first.mkdir(parents=True)
        second.mkdir(parents=True)
        alias = self.root / 'alias'
        alias.symlink_to(first, target_is_directory=True)
        self.assertNotEqual(picker.session_name(first), picker.session_name(second))
        self.assertEqual(picker.session_name(first), picker.session_name(picker.safe_directory(alias)))

    def test_roots_are_literal_deduplicated_and_not_evaluated(self):
        project = self.root / "work ; $(touch nope) ' space"
        project.mkdir()
        config = self.root / 'projects'
        config.write_text(f'# comment\n{project}\n{project}\n\n$HOME/code\nrelative\n/no/such/neon/folder\n')
        self.assertEqual(picker.project_roots(config), [project])
        self.assertFalse((self.root / 'nope').exists())

    def test_discovery_is_bounded_and_skips_dependencies(self):
        actual = self.root / 'code/actual'
        actual.mkdir(parents=True)
        (actual / 'go.mod').touch()
        (actual / 'src').mkdir()
        grouped = self.root / 'code/challenges/pokedex'
        grouped.mkdir(parents=True)
        (grouped / 'too-deep').mkdir()
        (self.root / 'code/node_modules/not-a-project').mkdir(parents=True)
        (self.root / 'code/.cache').mkdir()
        (self.root / 'code/alias').symlink_to(actual, target_is_directory=True)
        found = picker.discover_projects([self.root / 'code', self.root / 'code'])
        self.assertEqual(set(found), {actual, grouped.parent, grouped})
        self.assertEqual(len(found), len(set(found)))

    def test_control_characters_rejected(self):
        path = self.root / 'unsafe\nlabel'
        path.mkdir()
        with self.assertRaisesRegex(ValueError, 'control'):
            picker.safe_directory(path)

    def test_fzf_uses_nul_records_and_literal_selection(self):
        path = self.root / "hello '; echo gotcha"
        path.mkdir()
        result = subprocess.CompletedProcess([], 0, str(path).encode() + b'\0')
        with mock.patch.object(picker.shutil, 'which', return_value='/usr/bin/fzf'), mock.patch.object(picker.subprocess, 'run', return_value=result) as run:
            self.assertEqual(picker.choose_project([path]), path)
        self.assertIn('--read0', run.call_args.args[0])
        self.assertEqual(run.call_args.kwargs['input'], str(path).encode() + b'\0')
        self.assertNotIn('shell', run.call_args.kwargs)

    def test_fzf_cancel_and_missing_dependency(self):
        with mock.patch.object(picker.shutil, 'which', return_value='/usr/bin/fzf'), mock.patch.object(picker.subprocess, 'run', return_value=subprocess.CompletedProcess([], 130, b'')):
            self.assertIsNone(picker.choose_project([self.root]))
        with mock.patch.object(picker.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, '/path/to/project'):
                picker.choose_project([self.root])

class TmuxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='neon tmux ')
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "api ; $(echo no) ' spaces"
        self.path.mkdir()
        (self.path / '.tmux-sessionizer').write_text('touch MUST_NOT_RUN\n')

    def connect(self, exists=False, inside=False, nvim=True):
        calls = []
        def capture(tmux, *args):
            calls.append((tmux, *args))
            rc = 0 if exists or args[0] != 'has-session' else 1
            out = '$7:@22\n' if args[0] == 'new-session' else ''
            return subprocess.CompletedProcess([tmux, *args], rc, out, '')
        def which(name):
            return None if name == 'nvim' and not nvim else '/usr/bin/' + name
        with mock.patch.object(picker.shutil, 'which', side_effect=which), mock.patch.object(picker, 'tmux_capture', side_effect=capture), mock.patch.object(picker.subprocess, 'call', return_value=0) as attach:
            self.assertEqual(picker.connect_project(self.path, inside_tmux=inside), 0)
        return calls, attach.call_args.args[0]

    def test_new_workspace_exact_argv_no_hydration_no_detach(self):
        calls, attachment = self.connect()
        new = next(c for c in calls if c[1] == 'new-session')
        run = next(c for c in calls if c[1] == 'new-window')
        self.assertEqual(new[new.index('-c') + 1], str(self.path))
        self.assertEqual(run[run.index('-c') + 1], str(self.path))
        self.assertIn('edit', new)
        self.assertIn('run', run)
        keys = [c for c in calls if c[1] == 'send-keys']
        self.assertEqual(keys[0][-1], 'nvim .')
        self.assertIn('@22', keys[0])
        self.assertEqual(keys[1][-1], 'Enter')
        commands = ' '.join(word for call in calls for word in call)
        self.assertNotIn('source', commands)
        self.assertNotIn('.tmux-sessionizer', commands)
        self.assertEqual(attachment[1], 'attach-session')
        self.assertTrue(attachment[-1].startswith('=neon-'))
        self.assertNotIn('-d', attachment)

    def test_existing_session_unchanged_and_switches_inside_tmux(self):
        calls, attachment = self.connect(exists=True, inside=True)
        self.assertEqual([c[1] for c in calls], ['has-session'])
        self.assertEqual(attachment[1], 'switch-client')
        self.assertNotIn('-d', attachment)

    def test_missing_nvim_leaves_edit_shell(self):
        calls, _ = self.connect(nvim=False)
        self.assertNotIn('send-keys', [c[1] for c in calls])
        self.assertIn('new-window', [c[1] for c in calls])

    def test_cancel_does_not_open_tmux(self):
        with mock.patch.object(picker, 'project_roots', return_value=[]), mock.patch.object(picker, 'choose_project', return_value=None), mock.patch.object(picker, 'connect_project') as connect:
            self.assertEqual(picker.main([]), 0)
            connect.assert_not_called()

class ClipboardTests(unittest.TestCase):
    def choose(self, system='Linux', release='normal', env=None, installed=()):
        return clipboard.choose_backend(system=system, release=release, env=env or {}, which=lambda n: '/bin/' + n if n in installed else None)

    def test_wsl_priority_requires_real_kernel(self):
        tools = ('clip.exe', 'wl-copy', 'xclip')
        env = {'DISPLAY': ':0', 'WAYLAND_DISPLAY': 'wayland-0'}
        self.assertEqual(self.choose(release='6.1-microsoft-standard-WSL2', env=env, installed=tools)[0], 'wsl')
        self.assertEqual(self.choose(env={**env, 'WSL_DISTRO_NAME': 'fake'}, installed=tools)[0], 'wayland')

    def test_desktop_selection_and_missing_backend(self):
        self.assertEqual(self.choose(system='Darwin', installed=('pbcopy',))[0], 'macos')
        self.assertEqual(self.choose(env={'WAYLAND_DISPLAY': 'wayland-0'}, installed=('wl-copy',))[0], 'wayland')
        self.assertEqual(self.choose(env={'DISPLAY': ':0'}, installed=('xclip',))[0], 'x11')
        self.assertIsNone(self.choose(installed=('clip.exe', 'pbcopy', 'wl-copy', 'xclip')))

    def test_windows_unicode_encoding(self):
        data = 'Olá Helder — ◈'.encode()
        self.assertEqual(clipboard.encode_payload('wsl', data).decode('utf-16le'), data.decode())
        self.assertEqual(clipboard.encode_payload('wayland', data), data)
        with self.assertRaises(clipboard.ClipboardError):
            clipboard.encode_payload('wsl', b'\xff')

    def test_endpoint_failure_no_silent_fallback(self):
        with mock.patch.object(clipboard.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)) as run:
            with self.assertRaisesRegex(clipboard.ClipboardError, 'exit 1'):
                clipboard.copy_bytes(b'private text', ('x11', ['/bin/xclip', '-in']))
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.kwargs['input'], b'private text')
        self.assertNotIn('shell', run.call_args.kwargs)

    def test_hung_endpoint_has_bounded_timeout(self):
        with mock.patch.object(clipboard.subprocess, 'run', side_effect=subprocess.TimeoutExpired('xclip', 5)):
            with self.assertRaisesRegex(clipboard.ClipboardError, 'timed out'):
                clipboard.copy_bytes(b'text', ('x11', ['/bin/xclip']))

    def test_missing_endpoint_does_not_spawn(self):
        with mock.patch.object(clipboard, 'choose_backend', return_value=None), mock.patch.object(clipboard.subprocess, 'run') as run:
            with self.assertRaisesRegex(clipboard.ClipboardError, 'No clipboard endpoint'):
                clipboard.copy_bytes(b'text')
            run.assert_not_called()

    def test_macos_utf8_locale_child_only(self):
        with mock.patch.dict(clipboard.os.environ, {'LC_ALL': 'C'}), mock.patch.object(clipboard.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            clipboard.copy_bytes(b'text', ('macos', ['/usr/bin/pbcopy']))
            self.assertEqual(clipboard.os.environ['LC_ALL'], 'C')
        self.assertNotIn('LC_ALL', run.call_args.kwargs['env'])
        self.assertEqual(run.call_args.kwargs['env']['LC_CTYPE'], 'UTF-8')

class PaletteTests(unittest.TestCase):
    def test_windows_and_ghostty_palette_match(self):
        palette = json.loads((ROOT / 'config/windows-terminal/Shell-Arena.json').read_text())
        self.assertEqual(palette['name'], 'Shell Arena')
        self.assertEqual(palette['background'], '#090E17')
        self.assertEqual(palette['cyan'], '#47EBFF')
        ghostty = (ROOT / 'config/ghostty/config').read_text().lower()
        for key in ('background', 'foreground', 'cyan', 'yellow', 'purple'):
            self.assertIn(palette[key].lower(), ghostty)

@unittest.skipUnless(os.environ.get('NEON_TEST_TMUX'), 'Set NEON_TEST_TMUX for a real isolated tmux integration check')
class RealTmuxTests(unittest.TestCase):
    def test_configuration_and_real_project_lifecycle(self):
        binary = os.environ['NEON_TEST_TMUX']
        with tempfile.TemporaryDirectory(prefix='neon-tmux-qa-') as temp:
            root = Path(temp)
            socket = str(root / 'socket')
            def tmux(*args):
                return subprocess.run([binary, '-S', socket, *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
            created = tmux('-f', '/dev/null', 'new-session', '-d', '-s', 'qa-control', '/bin/bash', '--noprofile', '--norc')
            self.assertEqual(created.returncode, 0, created.stderr)
            try:
                parsed = tmux('source-file', str(ROOT / 'config/tmux/tmux.conf'))
                self.assertEqual(parsed.returncode, 0, parsed.stderr)
                self.assertEqual(tmux('show-options', '-gv', 'prefix').stdout.strip(), 'C-a')
                tmux('set-option', '-g', 'default-command', '/bin/bash --noprofile --norc')
                first = root / "work ; echo 'quoted'/api"
                second = root / 'personal/api'
                first.mkdir(parents=True)
                second.mkdir(parents=True)
                (first / '.tmux-sessionizer').write_text('touch MUST_NOT_RUN\n')
                def capture(_binary, *args):
                    return tmux(*args)
                with mock.patch.object(picker.shutil, 'which', side_effect=lambda name: binary if name == 'tmux' else None), mock.patch.object(picker, 'tmux_capture', side_effect=capture), mock.patch.object(picker.subprocess, 'call', return_value=0):
                    self.assertEqual(picker.connect_project(first, inside_tmux=False), 0)
                    self.assertEqual(picker.connect_project(second, inside_tmux=True), 0)
                    self.assertEqual(picker.connect_project(first, inside_tmux=False), 0)
                for project in (first, second):
                    windows = tmux('list-windows', '-t', '=' + picker.session_name(project), '-F', '#{window_index}:#{window_name}:#{pane_current_path}')
                    self.assertEqual(windows.returncode, 0, windows.stderr)
                    self.assertEqual(windows.stdout.splitlines(), [f'1:edit:{project}', f'2:run:{project}'])
                sessions = tmux('list-sessions', '-F', '#{session_name}').stdout.splitlines()
                self.assertEqual(len(sessions), 3)
                self.assertFalse((first / 'MUST_NOT_RUN').exists())
            finally:
                # Only the unique server created above is stopped.
                tmux('kill-server')

if __name__ == '__main__':
    unittest.main()
