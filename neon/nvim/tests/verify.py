#!/usr/bin/env python3
"""Exercise real Neovim startup and the additive overlay without plugin downloads."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

PARSER = argparse.ArgumentParser()
PARSER.add_argument('--nvim', default=shutil.which('nvim'))
ARGS, UNITTEST_ARGS = PARSER.parse_known_args()
if not ARGS.nvim:
    PARSER.error('Neovim is required; pass --nvim /path/to/nvim')
SOURCE = Path(__file__).resolve().parents[1]
SHELL_INIT = SOURCE.parent / 'shell/init.bash'
EXPORTED_VIMINIT = re.search(r"export VIMINIT='([^']+)'", SHELL_INIT.read_text()).group(1)


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='neon-overlay-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'dev env'
        self.overlay = self.repo / 'neon/nvim'
        shutil.copytree(SOURCE, self.overlay, ignore=shutil.ignore_patterns('__pycache__'))
        # Redirect only the cloned test fallback's home candidates. Never alter
        # HOME or source the developer's real Vim configuration during checks.
        fallback = self.overlay / 'vim-fallback.vim'
        fallback.write_text(fallback.read_text().replace("expand('~/", "expand('$NEON_TEST_VIM_HOME/"))
        self.kickstart = self.repo / '.config/nvim'
        self.kickstart.mkdir(parents=True)
        (self.kickstart / 'lua').mkdir()
        (self.kickstart / 'lua/existing_module.lua').write_text('return { intact = true }\n')
        (self.kickstart / 'lazy-lock.json').write_text('{"original": true}\n')
        (self.kickstart / 'init.lua').write_text('''
vim.g.kickstart_ran = (vim.g.kickstart_ran or 0) + 1
vim.g.original_module = require('existing_module').intact
vim.g.original_lockfile = vim.fn.stdpath('config') .. '/lazy-lock.json'
vim.g.mapleader = ' '
vim.o.statusline = 'ORIGINAL KICKSTART STATUSLINE'
vim.wo.number, vim.wo.relativenumber = true, true
vim.o.laststatus = 2
vim.wo.winbar = 'original winbar'
vim.diagnostic.config({ virtual_text = { spacing = 5 } })
vim.keymap.set('n', '<leader>rt', '<cmd>let g.existing_mapping = 1<CR>')
vim.keymap.set('n', '<leader>ab', '<cmd>let g.existing_prefix = 1<CR>')
vim.g.kickstart_formatter = 'unchanged'
''')
        self.config = self.root / 'xdg-config'
        self.config.mkdir()
        (self.config / 'nvim').symlink_to(self.kickstart, target_is_directory=True)
        self.env = os.environ.copy()
        self.env.pop('NVIM_APPNAME', None)
        self.env.update({
            'XDG_CONFIG_HOME': str(self.config),
            'XDG_DATA_HOME': str(self.root / 'data'),
            'XDG_STATE_HOME': str(self.root / 'state'),
            'XDG_CACHE_HOME': str(self.root / 'cache'),
            'NEON_ROOT': str(self.repo / 'neon'),
            'NEON_TEST_ROOT': str(self.root),
            'NEON_TEST_VIM_HOME': str(self.root / 'vim-home'),
            'VIMINIT': EXPORTED_VIMINIT,
        })

    def run_lua(self, body, *nvim_args, environment=None):
        script = self.root / 'assertions.lua'
        script.write_text(body)
        self.env['NEON_TEST_SCRIPT'] = str(script)
        if environment:
            self.env.update(environment)
        driver = "lua local ok, err = pcall(dofile, vim.env.NEON_TEST_SCRIPT); if not ok then print(err); vim.cmd('cquit 1') else print('OVERLAY_ASSERTIONS_OK'); vim.cmd('qa!') end"
        result = subprocess.run([ARGS.nvim, '--headless', '-i', 'NONE', '-n', *nvim_args, '-c', driver],
                                env=self.env, cwd=self.root, text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('OVERLAY_ASSERTIONS_OK', result.stdout + result.stderr)
        self.assertNotIn('Error detected while processing', result.stdout + result.stderr)

    def test_startup_preserves_kickstart_and_conflicting_mappings(self):
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.kickstart.rglob('*') if p.is_file()}
        self.run_lua('''
assert(vim.g.kickstart_ran == 1)
assert(vim.g.original_module == true)
assert(vim.g.original_lockfile == vim.fn.stdpath('config') .. '/lazy-lock.json')
assert(vim.env.MYVIMRC == vim.fn.stdpath('config') .. '/init.lua')
assert(vim.g.kickstart_formatter == 'unchanged')
assert(vim.fn.exists(':NeonDeck') == 2)
assert(vim.fn.exists(':NeonTest') == 2)
assert(vim.fn.maparg(' rt', 'n'):find('existing_mapping', 1, true))
assert(vim.fn.maparg(' ab', 'n'):find('existing_prefix', 1, true))
assert(vim.fn.maparg(' a', 'n') == '')
assert(vim.fn.maparg(' uz', 'n', false, true).callback ~= nil)
local conflicts = require('neon_overlay').conflicts
assert(vim.tbl_contains(conflicts, '<leader>rt'))
assert(vim.tbl_contains(conflicts, '<leader>a'))
assert(vim.o.statusline:find('neon_overlay', 1, true))
vim.cmd('NeonHud')
assert(vim.o.statusline == 'ORIGINAL KICKSTART STATUSLINE')
vim.cmd('NeonHud')
assert(vim.o.statusline:find('neon_overlay', 1, true))
local deck
vim.ui.select = function(items, _, callback) deck = items; callback(nil) end
vim.cmd('NeonDeck')
assert(#deck >= 10)
''')
        after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in self.kickstart.rglob('*') if p.is_file()}
        self.assertEqual(before, after, 'Overlay modified the submodule')

    def test_focus_restores_original_window_and_diagnostics(self):
        self.run_lua('''
local original = vim.api.nvim_get_current_win()
vim.cmd('NeonFocus')
assert(vim.wo.number == false and vim.o.laststatus == 0)
assert(vim.diagnostic.config().virtual_text == false)
vim.cmd('vsplit')
vim.cmd('NeonFocus')
assert(vim.wo[original].number == true and vim.wo[original].relativenumber == true)
assert(vim.wo[original].winbar == 'original winbar')
assert(vim.o.laststatus == 2)
assert(vim.diagnostic.config().virtual_text.spacing == 5)
''')

    def test_task_execution_quickfix_unsaved_guard_and_stop(self):
        project = self.root / 'project'
        project.mkdir()
        (project / 'go.mod').write_text('module example.com/test\n')
        (project / 'main.go').write_text('package main\n')
        (project / 'runner.py').write_text('print("main.go:3:7: intentional failure")\nraise SystemExit(1)\n')
        (project / 'slow.py').write_text('import time\ntime.sleep(10)\n')
        self.env['NEON_TEST_PYTHON'] = shutil.which('python3') or 'python3'
        self.run_lua('''
local root = vim.env.NEON_TEST_ROOT .. '/project'
vim.cmd.edit(vim.fn.fnameescape(root .. '/main.go'))
local tasks = require('neon_overlay.tasks')
assert(require('neon_overlay.project').root() == root)
assert(#tasks.candidates(root) == 2)
local choice = { argv = { vim.env.NEON_TEST_PYTHON, root .. '/runner.py' }, cwd = root }
vim.api.nvim_buf_set_lines(0, 0, -1, false, { 'unsaved' })
tasks.run(choice)
assert(tasks.status() == 'READY')
vim.bo.modified = false
tasks.run(choice)
assert(vim.wait(5000, function() return tasks.status():find('TEST / EXIT 1 ', 1, true) ~= nil end))
local items = vim.fn.getqflist()
assert(#items == 1 and items[1].lnum == 3 and items[1].col == 7)
assert(vim.api.nvim_buf_get_name(items[1].bufnr) == root .. '/main.go')
tasks.output()
assert(table.concat(vim.api.nvim_buf_get_lines(0, 0, -1, false), '\\n'):find('intentional failure', 1, true))
vim.cmd('close')
tasks.run({ argv = { vim.env.NEON_TEST_PYTHON, root .. '/slow.py' }, cwd = root })
tasks.stop()
assert(vim.wait(5000, function() return tasks.status():find('STOPPED', 1, true) ~= nil end))
''')

    def test_custom_app_loads_its_own_config_without_overlay(self):
        custom = self.config / 'another-app'
        custom.mkdir()
        (custom / 'init.lua').write_text('vim.g.custom_app_loaded = true\n')
        self.run_lua('''
assert(vim.g.custom_app_loaded == true)
assert(vim.g.kickstart_ran == nil)
assert(vim.fn.exists(':NeonDeck') == 0)
''', environment={'NVIM_APPNAME': 'another-app'})

    def test_different_config_loads_without_overlay(self):
        (self.config / 'nvim').unlink()
        (self.config / 'nvim').mkdir()
        (self.config / 'nvim/init.lua').write_text('vim.g.different_config_loaded = true\n')
        self.run_lua('''
assert(vim.g.different_config_loaded == true)
assert(vim.g.kickstart_ran == nil)
assert(vim.fn.exists(':NeonDeck') == 0)
''')

    def test_explicit_clean_and_u_none_bypass_viminit(self):
        for option in [('--clean',), ('-u', 'NONE')]:
            with self.subTest(option=option):
                self.run_lua('''
assert(vim.g.kickstart_ran == nil)
assert(vim.fn.exists(':NeonDeck') == 0)
''', *option)

    def test_explicit_overlay_launcher_overrides_an_existing_viminit(self):
        self.run_lua('''
assert(vim.g.kickstart_ran == 1)
assert(vim.fn.exists(':NeonDeck') == 2)
assert(vim.g.unrelated_viminit == nil)
''', '-u', str(self.overlay / 'init.lua'), environment={'VIMINIT': 'let g:unrelated_viminit = 1'})

    def test_plain_vim_branch_sources_xdg_vimrc_and_ignores_exinit(self):
        # Execute the exact exported Ex expression, selecting its non-Nvim
        # branch in Neovim's Vimscript engine. No HOME substitution is needed.
        vimdir = self.config / 'vim'
        vimdir.mkdir()
        (vimdir / 'vimrc').write_text('let g:plain_vim_loaded = 1\n')
        self.run_lua('''
assert(vim.g.plain_vim_loaded == 1)
assert(vim.g.exinit_loaded == nil)
assert(vim.fn.exists(':NeonDeck') == 0)
assert(vim.env.MYVIMRC == vim.env.XDG_CONFIG_HOME .. '/vim/vimrc')
''', environment={'VIMINIT': EXPORTED_VIMINIT.replace('has("nvim")', '0'),
                 'EXINIT': 'let g:exinit_loaded = 1'})

    def test_plain_vim_branch_uses_exinit_when_no_vimrc_exists(self):
        self.run_lua('''
assert(vim.g.exinit_loaded == 1)
assert(vim.fn.exists(':NeonDeck') == 0)
''', environment={'VIMINIT': EXPORTED_VIMINIT.replace('has("nvim")', '0'),
                 'EXINIT': 'let g:exinit_loaded = 1'})


if __name__ == '__main__':
    unittest.main(argv=[__file__, *UNITTEST_ARGS])
