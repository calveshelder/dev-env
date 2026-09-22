"""Exercise native Zsh hooks and the shared Arena store with no real user state."""
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ZSH = shutil.which('zsh')


@unittest.skipUnless(ZSH, 'native zsh executable is required')
class ZshArenaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='neon-zsh-arena-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.env = dict(os.environ, NEON_ROOT=str(ROOT), NEON_ARENA_QUIET='1',
                        XDG_STATE_HOME=str(self.base / 'state'),
                        HISTFILE=str(self.base / 'history'), TERM='dumb')

    def zsh(self, script, interactive_input=False):
        script = 'source "$NEON_ROOT/shell/arena.zsh"\n' + script
        args = [ZSH, '-f', '-i']
        if not interactive_input:
            args += ['-c', script]
        result = subprocess.run(args, input=script if interactive_input else None,
                                env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('read-only variable', result.stderr)
        return result

    def counters(self):
        with sqlite3.connect(self.base / 'state/shell-arena/stats.sqlite3') as db:
            return dict(db.execute('SELECT key, value FROM counters'))

    def test_quest_award_shares_existing_store_and_cannot_repeat(self):
        self.zsh('''
arena quest 'Understand a test'
arena predict
arena check false && exit 20
arena recall && exit 21
arena check true || exit 22
arena recall || exit 23
arena finish || exit 24
arena finish && exit 25
[[ $_ARENA_XP == 100 && $_ARENA_WINS == 1 ]] || exit 26
''')
        self.assertEqual(self.counters()['xp'], 100)
        self.assertEqual(self.counters()['wins'], 1)
        # A second Zsh session sees the same saved totals, as does Bash's Python backend.
        self.zsh('[[ $_ARENA_XP == 100 && $_ARENA_WINS == 1 ]] || exit 27')

    def test_real_hooks_preserve_status_pipeline_and_following_hooks(self):
        result = self.zsh('''
_test_next_hook() { printf 'HOOK=%s PIPE=%s LAST=%s\\n' "$?" "${pipestatus[*]}" "$_ARENA_LAST"; return 0; }; add-zsh-hook precmd _test_next_hook
false
printf 'ACTUAL=%s PIPE=%s\\n' "$?" "${pipestatus[*]}"
(exit 7) | true
printf 'ACTUAL=%s PIPE=%s\\n' "$?" "${pipestatus[*]}"
exit
''', interactive_input=True)
        self.assertIn('HOOK=1 PIPE=1 LAST=RETRY (1)', result.stdout)
        self.assertIn('ACTUAL=1 PIPE=1', result.stdout)
        self.assertIn('HOOK=0 PIPE=7 0 LAST=CLEAR', result.stdout)
        self.assertIn('ACTUAL=0 PIPE=7 0', result.stdout)

    def test_repeated_source_keeps_hooks_and_enter_widget(self):
        self.zsh('''
_other_hook() { return 0; }
add-zsh-hook precmd _other_hook
_my_accept_line() { zle .accept-line; }
zle -N accept-line _my_accept_line
before=$(zle -l -L accept-line)
source "$NEON_ROOT/shell/arena.zsh"
after=$(zle -l -L accept-line)
[[ $before == "$after" ]] || exit 20
arena_hooks=( "${(@M)preexec_functions:#_arena_preexec}" )
[[ ${#arena_hooks[@]} == 1 ]] || exit 21
arena_hooks=( "${(@M)precmd_functions:#_arena_precmd}" )
[[ ${#arena_hooks[@]} == 1 ]] || exit 22
[[ ${precmd_functions[(I)_other_hook]} -gt 0 ]] || exit 23
[[ ${zshexit_functions[(I)_arena_audio_stop]} -gt 0 ]] || exit 24
''')

    def test_work_quiet_refresh_never_changes_saved_preferences(self):
        self.zsh('''
arena status
arena hud off
[[ $_ARENA_MUTED == 1 && $_ARENA_VIBE == 2 ]] || exit 20
[[ -z $_ARENA_AUDIO_PID ]] || exit 21
''')
        values = self.counters()
        self.assertEqual(values['muted'], 0)
        self.assertEqual(values['vibe'], 1)
        self.assertEqual(values['hud'], 0)

    def test_ops_do_not_award_xp_or_spawn_state_interpreters(self):
        self.zsh('''
python3() { print -u2 'UNEXPECTED_PYTHON'; return 99; }
_arena_preexec
true
_arena_precmd
_arena_preexec
false
_arena_precmd
[[ $_ARENA_OPS == 2 && $_ARENA_XP == 0 && $_ARENA_LAST == 'RETRY (1)' ]] || exit 20
''')
        self.assertEqual(self.counters()['xp'], 0)

    def test_audio_fifo_launch_result_and_cleanup_with_fake_backend(self):
        self.env['NEON_ARENA_QUIET'] = '0'
        executables = self.base / 'bin'
        executables.mkdir()
        # Backend selection remains inside arena_audio.py (afplay on macOS).
        for name in ('paplay', 'afplay'):
            player = executables / name
            player.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$NEON_AUDIO_LOG"\n')
            player.chmod(0o755)
        self.env['PATH'] = str(executables) + os.pathsep + self.env['PATH']
        self.env['NEON_AUDIO_LOG'] = str(self.base / 'audio.log')
        self.zsh('''
[[ -n $_ARENA_AUDIO_PID && -p $_ARENA_AUDIO_RUN/events ]] || exit 20
old_run=$_ARENA_AUDIO_RUN
sleep 0.2
_arena_preexec
sleep 0.2
true
_arena_precmd
sleep 0.2
_arena_audio_stop
[[ ! -e $old_run && -z $_ARENA_AUDIO_FD && -z $_ARENA_AUDIO_PID ]] || exit 21
''')
        played = (self.base / 'audio.log').read_text()
        self.assertIn('/cyber/boot.wav', played)
        self.assertIn('/cyber/launch.wav', played)
        self.assertIn('/cyber/ok2.wav', played)

    def test_hud_is_bounded_and_sanitizes_directory_controls(self):
        # Invoke the renderer directly to avoid needing a tty; ordinary hooks draw only on a tty.
        literal = self.base / 'project\x1b[31m'
        literal.mkdir()
        self.env['ARENA_TEST_PROJECT'] = str(literal)
        result = self.zsh('''
cd -- "$ARENA_TEST_PROJECT"
COLUMNS=80
_arena_neon_draw
COLUMNS=25
_arena_neon_draw
''')
        self.assertNotIn('\x1b', result.stderr)
        lines = [line for line in result.stderr.splitlines() if line.strip()]
        self.assertEqual(len(lines), 3, result.stderr)
        self.assertLessEqual(len(lines[0]), 79)
        self.assertLessEqual(len(lines[1]), 79)
        self.assertLessEqual(len(lines[2]), 24)


if __name__ == '__main__':
    unittest.main()
