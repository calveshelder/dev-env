import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ShellTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='neon-shell-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.env = dict(os.environ, HISTFILE=str(self.base / 'history'),
                        XDG_STATE_HOME=str(self.base / 'state'), XDG_CACHE_HOME=str(self.base / 'cache'),
                        NEON_ARENA='0', NEON_ATUIN='0', NVM_DIR=str(self.base / 'nvm'))

    def bash(self, script):
        result = subprocess.run(['bash', '--noprofile', '--norc', '-ic',
                                 'source "$1/shell/init.bash"\n' + script,
                                 'neon-test', str(ROOT)], env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('invalid keymap', result.stderr)
        return result

    def test_history_exists_private_and_init_is_idempotent(self):
        self.bash('''
[[ -f $HISTFILE ]] || exit 20
before=$PATH
source "$1/shell/init.bash"
[[ $before == "$PATH" && $_NEON_INIT_DONE == 1 ]] || exit 21
[[ $(bind -m vi-insert -X) == *tmux-sessionizer* ]] || exit 22
''')
        self.assertEqual((self.base / 'history').stat().st_mode & 0o077, 0)

    def test_nvm_is_lazy_and_loaded_once(self):
        nvm = self.base / 'nvm'
        nvm.mkdir()
        (nvm / 'nvm.sh').write_text('NEON_NVM_LOADS=$((${NEON_NVM_LOADS:-0}+1))\nnvm() { printf "nvm loaded\\n"; }\n')
        self.bash('''
[[ -z ${NEON_NVM_LOADS:-} ]] || exit 20
nvm --version
nvm --version
[[ $NEON_NVM_LOADS == 1 ]] || exit 21
''')

    def test_path_idempotence_and_literal_directory(self):
        target = self.base / 'tools space;literal'
        target.mkdir()
        self.env['NEON_TEST_PATH'] = str(target)
        self.bash('''
_neon_path_prepend "$NEON_TEST_PATH"
before=$PATH
_neon_path_prepend "$NEON_TEST_PATH"
[[ $before == "$PATH" && $PATH == "$NEON_TEST_PATH":* ]] || exit 20
''')

    def test_explicit_fzf_commands_are_preserved(self):
        self.env.update(FZF_DEFAULT_COMMAND='printf custom', FZF_CTRL_T_COMMAND='', FZF_ALT_C_COMMAND='printf dirs')
        self.bash('''
[[ $FZF_DEFAULT_COMMAND == 'printf custom' && -z $FZF_CTRL_T_COMMAND && $FZF_ALT_C_COMMAND == 'printf dirs' ]] || exit 20
''')

    def test_sources_parse(self):
        for path in (ROOT / 'shell').glob('*.bash'):
            result = subprocess.run(['bash', '-n', str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
