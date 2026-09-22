"""Offline state and Bash hook-contract tests; no live WSLg required."""
import concurrent.futures
import json
import os
import re
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


class ArenaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="arena-tests-")
        self.addCleanup(self.tmp.cleanup)
        self.env = dict(os.environ, XDG_STATE_HOME=self.tmp.name, HISTFILE="/dev/null")
        self.state("set", "muted", "1")

    def state(self, *args, check=True):
        return subprocess.run(
            ["python3", str(ROOT / "arena_state.py"), *args], env=self.env,
            capture_output=True, text=True, check=check, timeout=10,
        )

    def bash(self, body, check=True):
        prefix = '''
bash_preexec_imported=defined
preexec_functions=(existing_preexec)
precmd_functions=(existing_precmd)
PROMPT_COMMAND=':'
PS1='original> '
source "$1/arena.bash"
'''
        result = subprocess.run(
            ["bash", "--noprofile", "--norc", "-ic", prefix + body,
             "arena-test", str(ROOT)], env=self.env, capture_output=True,
            text=True, timeout=10,
        )
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_source_is_idempotent_preserves_existing_hooks(self):
        self.bash('''
source "$1/arena.bash"
[[ ${#preexec_functions[@]} == 2 && ${#precmd_functions[@]} == 2 ]] || exit 21
[[ ${preexec_functions[0]} == existing_preexec ]] || exit 22
[[ ${precmd_functions[0]} == existing_precmd ]] || exit 23
[[ $PROMPT_COMMAND == : && $PS1 == 'original> ' ]] || exit 24
[[ -z $(trap -p DEBUG) ]] || exit 25
''')

    def test_relative_source_survives_cd(self):
        result = self.bash('''
cd /tmp
arena quest 'test paths' && arena predict && arena check true && arena recall && arena finish
''')
        self.assertIn("+100 XP", result.stdout)

    def test_quest_workflow_and_no_double_reward(self):
        self.bash('''
arena quest 'a goal' && arena predict && arena check true && arena recall && arena finish || exit 20
arena finish >/dev/null && exit 21
[[ $_ARENA_ACTIVE == 0 && $_ARENA_XP == 100 ]] || exit 22
''')
        self.assertTrue(self.state("read").stdout.startswith("100 1 "))

    def test_failed_check_preserves_exit_code_and_clears_stages(self):
        self.bash('''
arena quest 'a goal'; arena predict; arena check true; arena recall
arena check bash -c 'exit 7'
rc=$?
[[ $rc == 7 && $_ARENA_BITS == 1 && $_ARENA_XP == 0 ]] || exit 21
arena finish >/dev/null && exit 22
exit 0
''')

    def test_stages_are_ordered_and_goal_cannot_be_overwritten(self):
        self.bash('''
arena recall >/dev/null && exit 21
arena quest first
arena quest second >/dev/null && exit 22
[[ $_ARENA_LABEL == first ]] || exit 23
arena check true >/dev/null && exit 24
arena predict
arena recall >/dev/null && exit 25
arena abandon
[[ $_ARENA_ACTIVE == 0 && $_ARENA_BITS == 0 ]] || exit 26
''')

    def test_nonzero_and_cancel_precmd_statuses(self):
        self.bash('''
_arena_preexec
false
_arena_precmd
[[ $_ARENA_LAST == 'RETRY (1)' ]] || exit 21
_arena_preexec
(exit 130)
_arena_precmd
[[ $_ARENA_LAST == CANCELLED ]] || exit 22
''')

    def test_preexec_no_command_execution_and_zero_return_extdebug(self):
        self.bash('''
shopt -s extdebug
_arena_preexec 'touch /this-would-be-wrong'
[[ $? == 0 && $_ARENA_PENDING == 1 ]] || exit 21
''')

    def test_control_characters_removed(self):
        self.bash(r'''
arena quest $'hello\e[31m\nworld\t'
[[ $_ARENA_LABEL != *$'\e'* && $_ARENA_LABEL != *$'\n'* && $_ARENA_LABEL != *$'\t'* ]] || exit 21
arena abandon
arena quest $'\e\t\n' >/dev/null && exit 22
exit 0
''')

    def test_focus_rejects_invalid_and_accepts_leading_zero(self):
        self.bash('''
arena focus 08
[[ $_ARENA_FOCUS_END -gt $SECONDS ]] || exit 21
arena focus '1+1' >/dev/null && exit 22
arena focus 0 >/dev/null && exit 23
arena focus 91 >/dev/null && exit 24
exit 0
''')

    def test_off_disables_effects_not_other_hooks(self):
        self.bash('''
arena off
_ARENA_PENDING=0
_arena_preexec
[[ $_ARENA_ENABLED == 0 && $_ARENA_PENDING == 0 ]] || exit 21
[[ ${#preexec_functions[@]} == 2 ]] || exit 22
arena on
[[ $_ARENA_ENABLED == 1 && $_ARENA_MUTED == 1 ]] || exit 23
''')

    def test_concurrent_awards(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda _: self.state("award"), range(12)))
        self.assertTrue(self.state("read").stdout.startswith("1200 12 "))

    def test_corrupt_state_not_evaluated_or_reset(self):
        dbpath = Path(self.tmp.name) / "shell-arena/stats.sqlite3"
        with sqlite3.connect(dbpath) as db:
            db.execute("UPDATE counters SET value=? WHERE key='xp'", ("garbage",))
        self.assertNotEqual(self.state("award", check=False).returncode, 0)
        with sqlite3.connect(dbpath) as db:
            self.assertEqual(db.execute("SELECT value FROM counters WHERE key='xp'").fetchone()[0], "garbage")

    def test_theme_json(self):
        scheme = json.loads((ROOT / "windows-terminal-scheme.json").read_text())
        self.assertEqual(scheme["name"], "Shell Arena")
        for key, val in scheme.items():
            if key != "name":
                self.assertRegex(val, r"^#[0-9A-Fa-f]{6}$")

    def test_v2_migration_preserves_v1_counters_and_preferences(self):
        dbpath = Path(self.tmp.name) / 'shell-arena/stats.sqlite3'
        with sqlite3.connect(dbpath) as db:
            db.execute("DELETE FROM counters WHERE key IN ('vibe', 'volume')")
            db.execute("UPDATE counters SET value=700 WHERE key='xp'")
            db.execute("UPDATE counters SET value=7 WHERE key='wins'")
        self.assertEqual(self.state('read').stdout.strip(), '700 7 1 1 1 1 60')

    def test_vibe_and_volume_persist_and_validate(self):
        self.bash('''
arena vibe ghost && arena volume 025 || exit 20
[[ $_ARENA_VIBE == 2 && $_ARENA_VOLUME == 25 && $_ARENA_MUTED == 1 ]] || exit 21
arena vibe bogus >/dev/null && exit 22
arena volume 101 >/dev/null && exit 23
arena volume '2+3' >/dev/null && exit 24
exit 0
''')
        self.assertTrue(self.state('read').stdout.strip().endswith('2 25'))
        self.assertNotEqual(self.state('set', 'vibe', '3', check=False).returncode, 0)
        self.assertNotEqual(self.state('set', 'volume', '-1', check=False).returncode, 0)

    def test_passive_recovery_and_long_command_no_xp(self):
        self.bash('''
_arena_sound() { _TEST_CUE=$1; }
_arena_preexec; false; _arena_precmd
[[ $_TEST_CUE == error ]] || exit 21
_arena_preexec; true; _arena_precmd
[[ $_ARENA_LAST == RECOVERED* && $_TEST_CUE == recover ]] || exit 22
_arena_preexec; _ARENA_STARTED=$((SECONDS - 12)); true; _arena_precmd
[[ $_ARENA_LAST == 'JOB DONE 12s' && $_TEST_CUE == complete ]] || exit 23
[[ $_ARENA_OPS == 3 && $_ARENA_XP == 0 ]] || exit 24
_arena_precmd
[[ $_ARENA_OPS == 3 ]] || exit 25
''')

    def test_cancel_is_not_recovery_and_classic_keeps_original_status(self):
        self.bash('''
_arena_preexec; (exit 130); _arena_precmd
_arena_preexec; true; _arena_precmd
[[ $_ARENA_LAST == CLEAR* ]] || exit 21
arena vibe classic
_arena_preexec; false; _arena_precmd
_arena_preexec; true; _arena_precmd
[[ $_ARENA_LAST == CLEAR* ]] || exit 22
''')

    def test_neon_hud_width_and_no_color(self):
        for width in (1, 10, 40, 70, 100):
            output = self.bash(f'NO_COLOR=1; COLUMNS={width}; _arena_neon_draw').stderr
            lines = [line for line in output.splitlines() if 'ARENA' in line or ' OPS / ' in line]
            self.assertEqual(len(lines), 0 if width == 1 else 2 if width >= 70 else 1)
            for line in lines:
                self.assertNotIn('\x1b', line)
                self.assertLessEqual(len(line), width - 1)

    def test_neon_hud_has_no_animation_or_cursor_control(self):
        output = self.bash('unset NO_COLOR; TERM=xterm-256color; COLUMNS=100; _arena_neon_draw').stderr
        self.assertIn('SHELL ARENA / CYBER', output)
        stripped = re.sub(r'\x1b\[[0-9;]*m', '', output)
        self.assertNotIn('\x1b', stripped)


if __name__ == "__main__":
    unittest.main()
