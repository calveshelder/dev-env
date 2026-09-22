local M = {}
local configured = false
M.conflicts = {}

-- Do not steal a mapped key or an existing prefix from your Kickstart fork.
function M.map(lhs, callback, description)
  if vim.fn.mapcheck(lhs, 'n') ~= '' or next(vim.fn.maparg(lhs, 'n', false, true)) ~= nil then
    M.conflicts[#M.conflicts + 1] = lhs
    return false
  end
  vim.keymap.set('n', lhs, callback, { silent = true, desc = description })
  return true
end

function M.command(name, callback, description)
  if vim.fn.exists(':' .. name) == 2 then return false end
  vim.api.nvim_create_user_command(name, callback, { desc = description })
  return true
end

function M.setup()
  if configured then return end
  configured = true
  M.options = { hud = true, keymaps = true }
  local local_file = vim.fn.expand('~/.config/neon/local.lua')
  if vim.uv.fs_stat(local_file) then
    local ok, options = pcall(dofile, local_file)
    if ok and type(options) == 'table' then
      M.options = vim.tbl_extend('force', M.options, options)
    elseif not ok then
      vim.schedule(function() vim.notify('Neon local.lua: ' .. tostring(options), vim.log.levels.ERROR) end)
    end
  end
  require('neon_overlay.tasks').setup()
  require('neon_overlay.ui').setup()
  M.command('NeonHealth', function() vim.cmd('checkhealth neon_overlay') end, 'Check the additive Neon overlay')
end
return M
