"""Exercise the native Zsh integration without changing the user's HOME."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ZSH = shutil.which("zsh")


@unittest.skipUnless(ZSH, "native Zsh executable is unavailable")
class ZshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="neon-zsh-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.env = dict(
            os.environ,
            PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
            HISTFILE=str(self.base / "history"),
            XDG_STATE_HOME=str(self.base / "state"),
            XDG_CACHE_HOME=str(self.base / "cache"),
            NEON_ARENA="0", NEON_ATUIN="0", NVM_DIR=str(self.base / "nvm"),
            NEON_TOOL_LOG=str(self.base / "tool-log"),
        )
        for name in ("_NEON_ZSH_INIT_DONE", "NVM_BIN"):
            self.env.pop(name, None)

    def zsh(self, script, before="", interactive=True):
        result = subprocess.run(
            [ZSH, "-f", "-ic" if interactive else "-c",
             before + '\nsource "$1/shell/init.zsh"\n' + script,
             "neon-test", str(ROOT)],
            env=self.env, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for error in ("bad substitution", "no such keymap", "command not found", "parse error"):
            self.assertNotIn(error, result.stderr)
        return result

    def tool(self, name, output):
        path = self.bin / name
        path.write_text(
            '#!/bin/sh\nprintf "%s %s\\n" "' + name + '" "$*" >> "$NEON_TOOL_LOG"\n'
            + "cat <<'NEON_TEST_TOOL_OUTPUT'\n" + output + "\nNEON_TEST_TOOL_OUTPUT\n"
        )
        path.chmod(0o755)

    def test_history_private_path_idempotent_and_native_keymaps(self):
        self.zsh('''
[[ -f $HISTFILE && $NEON_ROOT == $1 ]] || exit 20
before=$PATH
source "$1/shell/init.zsh"
[[ $before == $PATH && $_NEON_ZSH_INIT_DONE == 1 ]] || exit 21
[[ $(bindkey -M emacs '^F') == *neon-project-picker* ]] || exit 22
[[ $(bindkey -M viins '^F') == *neon-project-picker* ]] || exit 23
[[ $(bindkey -M main '^F') == *neon-project-picker* ]] || exit 24
[[ $(bindkey -lL main) == 'bindkey -A viins main' ]] || exit 25
''', before="bindkey -v")
        self.assertEqual((self.base / "history").stat().st_mode & 0o077, 0)

    def test_existing_hooks_and_viminit_survive(self):
        self.env["VIMINIT"] = "let g:user_init=1"
        self.zsh('''
[[ $VIMINIT == 'let g:user_init=1' ]] || exit 20
[[ ${precmd_functions[(Ie)user_prompt]} -gt 0 ]] || exit 21
[[ ${preexec_functions[(Ie)user_preexec]} -gt 0 ]] || exit 22
false
user_prompt
[[ $user_status == 1 ]] || exit 23
''', before='''
autoload -Uz add-zsh-hook
user_prompt() { user_status=$?; }
user_preexec() { :; }
add-zsh-hook precmd user_prompt
add-zsh-hook preexec user_preexec
''')

    def test_integrations_receive_zsh_and_initialize_once(self):
        self.env["NEON_ATUIN"] = "1"
        self.tool("fzf", 'fzf-file-widget() { :; }; zle -N fzf-file-widget')
        self.tool("atuin", '_atuin_preexec() { :; }')
        self.tool("zoxide", '__zoxide_z() { :; }')
        self.tool("starship", 'prompt_starship_precmd() { :; }; PROMPT="stub prompt> "')
        self.zsh('''
source "$1/shell/init.zsh"
[[ $PROMPT == 'stub prompt> ' ]] || exit 20
''')
        self.assertEqual((self.base / "tool-log").read_text().splitlines(), [
            "fzf --zsh", "atuin init zsh --disable-up-arrow",
            "zoxide init zsh", "starship init zsh",
        ])

    def test_already_loaded_integrations_are_not_registered_twice(self):
        self.env["NEON_ATUIN"] = "1"
        for name in ("fzf", "atuin", "zoxide", "starship"):
            self.tool(name, "print -u2 DUPLICATE_INIT")
        self.zsh('[[ $PROMPT == "previous prompt> " ]] || exit 20', before='''
fzf-file-widget() { :; }; zle -N fzf-file-widget
_atuin_preexec() { :; }
__zoxide_z() { :; }
prompt_starship_precmd() { :; }
PROMPT='previous prompt> '
''')
        self.assertFalse((self.base / "tool-log").exists())

    def test_nvm_is_lazy_and_existing_node_function_is_retained(self):
        nvm = self.base / "nvm"
        nvm.mkdir()
        (nvm / "nvm.sh").write_text(
            'NEON_NVM_LOADS=$((${NEON_NVM_LOADS:-0}+1))\n'
            'nvm() { print "nvm loaded"; }\n'
        )
        self.zsh('''
[[ -z ${NEON_NVM_LOADS:-} ]] || exit 20
[[ $(node) == 'my existing node' ]] || exit 21
nvm --version
nvm --version
[[ $NEON_NVM_LOADS == 1 ]] || exit 22
[[ $(node) == 'my existing node' ]] || exit 23
''', before="node() { print 'my existing node'; }")

    def test_preexisting_nvm_is_preserved(self):
        nvm = self.base / "nvm"
        nvm.mkdir()
        (nvm / "nvm.sh").write_text("print -u2 SHOULD_NOT_LOAD\n")
        self.zsh('[[ $(nvm) == existing ]] || exit 20', before="nvm() { print existing; }")

    def test_path_spaces_and_explicit_empty_fzf_commands(self):
        directory = self.base / "my tools;literal"
        directory.mkdir()
        self.env.update(NEON_TEST_PATH=str(directory), FZF_DEFAULT_COMMAND="printf custom",
                        FZF_CTRL_T_COMMAND="", FZF_ALT_C_COMMAND="printf directories")
        self.zsh('''
_neon_path_prepend "$NEON_TEST_PATH"
before=$PATH
_neon_path_prepend "$NEON_TEST_PATH"
[[ $before == $PATH && $PATH == "$NEON_TEST_PATH":* ]] || exit 20
[[ $FZF_DEFAULT_COMMAND == 'printf custom' && -z $FZF_CTRL_T_COMMAND ]] || exit 21
[[ $FZF_ALT_C_COMMAND == 'printf directories' ]] || exit 22
''')

    def test_noninteractive_shell_does_not_initialize(self):
        self.zsh('[[ -z ${_NEON_ZSH_INIT_DONE:-} ]] || exit 20', interactive=False)
        self.assertFalse((self.base / "history").exists())

    def test_prompt_opt_out_and_completion_initialized_once(self):
        self.env["NEON_STARSHIP"] = "0"
        self.tool("starship", "print -u2 SHOULD_NOT_LOAD")
        self.zsh('''
[[ $PROMPT == 'mine> ' ]] || exit 20
[[ $(compdef) == existing-completion ]] || exit 21
''', before="PROMPT='mine> '; compdef() { print existing-completion; }")
        self.assertFalse((self.base / "tool-log").exists())

    def test_sources_parse(self):
        for path in (ROOT / "shell").glob("*.zsh"):
            result = subprocess.run([ZSH, "-n", str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
