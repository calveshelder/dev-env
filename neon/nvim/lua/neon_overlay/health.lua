local M = {}
function M.check()
  vim.health.start('Neon / Kickstart overlay')
  vim.health.ok('Neovim ' .. tostring(vim.version()))
  vim.health.info('Kickstart: ' .. (vim.g.neon_overlay_kickstart or 'not loaded by wrapper'))
  vim.health.info('Plugin manager, plugin pins, language servers and formatting are controlled by Kickstart.')
  local overlay = require('neon_overlay')
  if #overlay.conflicts > 0 then
    vim.health.warn('Preserved existing key mappings: ' .. table.concat(overlay.conflicts, ', ') .. '. Use :NeonDeck / :NeonTest commands.')
  else vim.health.ok('No overlay shortcut collisions detected') end
  for _, tool in ipairs({ 'git', 'rg', 'fd' }) do
    if vim.fn.executable(tool) == 1 then vim.health.ok(tool .. ' available') else vim.health.warn(tool .. ' missing (some search features may need it)') end
  end
  vim.health.info('Tests only run after an explicit action. Browser Boot.dev tests are not observed.')
end
return M
