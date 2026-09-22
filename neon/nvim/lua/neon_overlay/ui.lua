local M = {}
local focus_state, hud_state
local function escape(text) return tostring(text):gsub('%%', '%%%%'):gsub('[%c]', '') end

function M.highlights()
  local work = vim.env.NEON_PROFILE == 'work'
  vim.api.nvim_set_hl(0, 'NeonOverlayMode', { fg = '#090E17', bg = work and '#91D7AA' or '#47EBFF', bold = true })
  vim.api.nvim_set_hl(0, 'NeonOverlayAccent', { fg = work and '#91D7AA' or '#FF72D5', bg = '#141D2C', bold = true })
  vim.api.nvim_set_hl(0, 'NeonOverlayDim', { fg = '#8694AF', bg = '#141D2C' })
end

function M.statusline()
  local mode = vim.api.nvim_get_mode().mode:sub(1, 1)
  local names = { n = 'NORMAL', i = 'INSERT', v = 'VISUAL', V = 'VISUAL', c = 'COMMAND', R = 'REPLACE', t = 'TERMINAL' }
  local counts = vim.diagnostic.count(0)
  local errors = counts[vim.diagnostic.severity.ERROR] or 0
  local warnings = counts[vim.diagnostic.severity.WARN] or 0
  local branch = vim.b.gitsigns_head
  return '%#NeonOverlayMode# NEON / ' .. (names[mode] or 'VISUAL') .. ' %#StatusLine# %f %m%r'
    .. (branch and ' %#NeonOverlayDim#[' .. escape(branch) .. ']' or '')
    .. (errors > 0 and (' %#DiagnosticError#E:' .. errors) or '')
    .. (warnings > 0 and (' %#DiagnosticWarn#W:' .. warnings) or '')
    .. '%=%#NeonOverlayAccent# ' .. escape(require('neon_overlay.tasks').status()) .. ' %#NeonOverlayDim# %y  %l:%c  %p%% '
end

function M.hud()
  if hud_state then
    vim.go.statusline = hud_state.global
    for _, window in ipairs(vim.api.nvim_list_wins()) do
      vim.wo[window].statusline = hud_state.windows[window] or hud_state.global
    end
    hud_state = nil
  else
    hud_state = { global = vim.go.statusline, windows = {} }
    for _, window in ipairs(vim.api.nvim_list_wins()) do hud_state.windows[window] = vim.wo[window].statusline end
    local expression = "%!v:lua.require'neon_overlay.ui'.statusline()"
    vim.go.statusline = expression
    for _, window in ipairs(vim.api.nvim_list_wins()) do vim.wo[window].statusline = expression end
  end
  vim.cmd('redrawstatus')
end

function M.focus()
  if not focus_state then
    focus_state = { number = vim.wo.number, relativenumber = vim.wo.relativenumber,
      winbar = vim.wo.winbar, laststatus = vim.o.laststatus,
      virtual_text = vim.diagnostic.config().virtual_text, window = vim.api.nvim_get_current_win() }
    vim.wo.number, vim.wo.relativenumber, vim.wo.winbar = false, false, ''
    vim.o.laststatus = 0
    vim.diagnostic.config({ virtual_text = false })
    vim.notify('FOCUS / :NeonFocus restores your view')
  else
    vim.o.laststatus = focus_state.laststatus
    vim.diagnostic.config({ virtual_text = focus_state.virtual_text })
    if vim.api.nvim_win_is_valid(focus_state.window) then
      for _, key in ipairs({ 'number', 'relativenumber', 'winbar' }) do vim.wo[focus_state.window][key] = focus_state[key] end
    end
    focus_state = nil
    vim.notify('LINK RESTORED')
  end
end

local function search(name)
  local ok, builtin = pcall(require, 'telescope.builtin')
  if not ok then return vim.notify('Telescope is unavailable. Check your Kickstart plugin installation and :messages.', vim.log.levels.WARN) end
  builtin[name]({ cwd = require('neon_overlay.project').root() })
end

function M.deck()
  pcall(require, 'telescope')
  local tasks = require('neon_overlay.tasks')
  local items = {
    { 'SEARCH / project files', function() search('find_files') end },
    { 'SCAN / project text', function() search('live_grep') end },
    { 'TEST / choose a check', tasks.choose },
    { 'REPLAY / last test', tasks.repeat_last },
    { 'OUTPUT / last test', tasks.output },
    { 'STOP / running test process', tasks.stop },
    { 'FOCUS / toggle quiet view', M.focus },
    { 'HUD / toggle Neon or Kickstart statusline', M.hud },
    { 'HELP / existing keymaps', function() search('keymaps') end },
    { 'KICKSTART / edit the original init.lua', function() vim.cmd.edit(vim.fn.fnameescape(vim.g.neon_overlay_kickstart)) end },
    { 'HEALTH / overlay and shortcut conflicts', function() vim.cmd('checkhealth neon_overlay') end },
  }
  vim.ui.select(items, { prompt = 'NEON COMMAND DECK', format_item = function(item) return item[1] end }, function(item)
    if item then item[2]() end
  end)
end

function M.setup()
  local overlay = require('neon_overlay')
  M.highlights()
  vim.api.nvim_create_autocmd('ColorScheme', { group = vim.api.nvim_create_augroup('NeonOverlayColors', { clear = true }), callback = M.highlights })
  overlay.command('NeonDeck', M.deck, 'Open Neon command deck')
  overlay.command('NeonFocus', M.focus, 'Toggle a quiet editing view')
  overlay.command('NeonHud', M.hud, 'Toggle Neon and original Kickstart statusline')
  if overlay.options.keymaps then
    overlay.map('<leader>a', M.deck, 'Neon command deck')
    overlay.map('<leader>uz', M.focus, 'Neon focus view')
    overlay.map('<leader>uh', M.hud, 'Toggle Neon HUD')
  end
  if overlay.options.hud then M.hud() end
end
return M
