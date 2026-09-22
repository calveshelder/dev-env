-- Parent-repository overlay. Your Kickstart submodule remains the real config.
-- Loaded by VIMINIT in the Neon shell, or explicitly with nvim -u THIS_FILE.
local source = debug.getinfo(1, 'S').source:sub(2)
local uv = vim.uv or vim.loop
local here = vim.fn.fnamemodify(uv.fs_realpath(source) or source, ':h')
local repo = vim.fn.fnamemodify(here, ':h:h')
local config = vim.fn.stdpath('config')
local original = config .. '/init.lua'
local app = vim.env.NVIM_APPNAME
local custom_app = app ~= nil and app ~= '' and app ~= 'nvim'
local expected = repo .. '/.config/nvim/init.lua'
local matching = uv.fs_realpath(original) ~= nil
  and uv.fs_realpath(original) == uv.fs_realpath(expected)

if uv.fs_stat(original) then
  if uv.fs_realpath(original) == uv.fs_realpath(source) then
    error('Neon: ~/.config/nvim must point to the Kickstart submodule, not neon/nvim.')
  end
  vim.env.MYVIMRC = original
  dofile(original)
elseif uv.fs_stat(config .. '/init.vim') then
  vim.env.MYVIMRC = config .. '/init.vim'
  vim.cmd.source(vim.fn.fnameescape(config .. '/init.vim'))
elseif not custom_app then
  vim.schedule(function()
    vim.notify('Neon: Kickstart init.lua is missing. In dev-env, run git submodule update --init --recursive, then run the Neon installer.', vim.log.levels.WARN)
  end)
end

-- VIMINIT has startup precedence even for custom apps. Load their own config
-- above, then leave them alone. The same applies to another installed config.
if custom_app or not matching then return end
if vim.fn.has('nvim-0.11') ~= 1 then
  vim.schedule(function() vim.notify('Neon overlay needs Neovim 0.11 or newer. Your Kickstart config was still loaded.', vim.log.levels.WARN) end)
  return
end
vim.g.neon_overlay_root = here
vim.g.neon_overlay_kickstart = original
vim.opt.runtimepath:append(here)
require('neon_overlay').setup()
