-- Explicit, asynchronous tests. Commands are argv lists, never shell strings.
-- No project code is run until you choose a command or repeat your last test.
local M = {}
local active, last, result
local lines, partial = {}, { stdout = '', stderr = '' }
local output_buffer
local limit = 6000
local truncated = false

function M.status()
  if active then return 'TEST / RUNNING' end
  if not result then return 'READY' end
  if result.signal and result.signal ~= 0 then return 'TEST / STOPPED ' .. result.seconds .. 's' end
  return (result.code == 0 and 'TEST / PASS ' or 'TEST / EXIT ' .. result.code .. ' ') .. result.seconds .. 's'
end

function M.candidates(root)
  local project = require('neon_overlay.project')
  local choices = {}
  local function add(label, argv) choices[#choices + 1] = { label = label, argv = argv, cwd = root } end
  if project.has(root, 'go.mod') then
    add('Go: all packages · go test ./...', { 'go', 'test', './...' })
    add('Go: race check · go test -race ./...', { 'go', 'test', '-race', './...' })
  end
  if project.has(root, 'pyproject.toml') or project.has(root, 'pytest.ini') or project.has(root, 'setup.py') then
    local python = project.has(root, '.venv/bin/python') and (root .. '/.venv/bin/python') or 'python3'
    add('Python: pytest · ' .. python .. ' -m pytest', { python, '-m', 'pytest' })
  end
  if project.has(root, 'package.json') then
    local manager = project.has(root, 'pnpm-lock.yaml') and 'pnpm' or (project.has(root, 'yarn.lock') and 'yarn' or 'npm')
    add('JavaScript: package test script · ' .. manager .. ' test', { manager, 'test' })
  end
  if project.has(root, 'composer.json') then
    if project.has(root, 'vendor/bin/phpunit') then add('PHP: project PHPUnit · vendor/bin/phpunit', { './vendor/bin/phpunit' }) end
    if project.has(root, '.lando.yml') then add('PHP: Lando PHPUnit · lando phpunit', { 'lando', 'phpunit' }) end
  end
  return choices
end

local function clean(text)
  return text:gsub('\27%[[0-9;?]*[ -/]*[@-~]', ''):gsub('[%z\1-\8\11\12\14-\31\127]', '')
end

local function append(text)
  if #lines >= limit then truncated = true; return end
  lines[#lines + 1] = clean(text):sub(1, 16000)
end

local function consume(stream, data)
  if not data then return end
  local text = partial[stream] .. data
  local start = 1
  while true do
    local finish = text:find('\n', start, true)
    if not finish then break end
    append(text:sub(start, finish - 1))
    start = finish + 1
  end
  partial[stream] = text:sub(start, start + 16000)
end

function M.output()
  if not last then return vim.notify('No tests yet. Space rt chooses one.') end
  if not output_buffer or not vim.api.nvim_buf_is_valid(output_buffer) then
    output_buffer = vim.api.nvim_create_buf(false, true)
    vim.bo[output_buffer].bufhidden = 'hide'
    vim.bo[output_buffer].filetype = 'neon-test'
    vim.keymap.set('n', 'q', '<cmd>close<CR>', { buffer = output_buffer, desc = 'Close test output' })
  end
  local content = { 'NEON / TEST OUTPUT', table.concat(last.argv, ' '), 'Project: ' .. last.cwd, M.status(), '' }
  vim.list_extend(content, lines)
  if truncated then content[#content + 1] = '[Output limited to 6000 lines. Run in your terminal for complete output.]' end
  vim.bo[output_buffer].modifiable = true
  vim.api.nvim_buf_set_lines(output_buffer, 0, -1, false, content)
  vim.bo[output_buffer].modifiable = false
  local window = vim.fn.bufwinid(output_buffer)
  if window ~= -1 then vim.api.nvim_set_current_win(window)
  else vim.cmd('botright 12split'); vim.api.nvim_win_set_buf(0, output_buffer) end
end

local function quickfix()
  local items = {}
  for _, text in ipairs(lines) do
    local file, row, column, message = text:match('^%s*(.-):(%d+):(%d+):%s*(.*)$')
    if not file then file, row, message = text:match('^%s*(.-):(%d+):%s*(.*)$') end
    if file and not file:find('%s') then
      items[#items + 1] = { filename = file:sub(1, 1) == '/' and file or (last.cwd .. '/' .. file),
        lnum = tonumber(row), col = tonumber(column) or 1, text = message }
    end
  end
  -- Keep existing quickfix history; this test gets its own list, even on success.
  vim.fn.setqflist({}, ' ', { title = 'Neon test: ' .. table.concat(last.argv, ' '), items = items })
end

function M.run(choice)
  if active then return vim.notify('A test is already running. Space rs stops its process.', vim.log.levels.WARN) end
  if not require('neon_overlay.project').command_available(choice.argv, choice.cwd) then
    return vim.notify('Not executable: ' .. choice.argv[1] .. '. Install it for this project first.', vim.log.levels.WARN)
  end
  for _, buffer in ipairs(vim.api.nvim_list_bufs()) do
    if vim.bo[buffer].modified and require('neon_overlay.project').root(buffer) == choice.cwd then
      return vim.notify('Save your modified project buffers first; tests use files on disk.', vim.log.levels.WARN)
    end
  end
  last = vim.deepcopy(choice)
  lines, partial, result, truncated = {}, { stdout = '', stderr = '' }, nil, false
  local started = vim.uv.hrtime()
  vim.notify('TEST / ' .. table.concat(choice.argv, ' ') .. '\n' .. choice.cwd)
  local ok, process = pcall(vim.system, choice.argv, {
    cwd = choice.cwd, text = true,
    stdout = function(_, data) consume('stdout', data) end,
    stderr = function(_, data) consume('stderr', data) end,
  }, function(completed)
    vim.schedule(function()
      for _, tail in pairs(partial) do if tail ~= '' then append(tail) end end
      active = nil
      local code = completed.signal ~= 0 and (128 + completed.signal) or completed.code
      result = { code = code, signal = completed.signal, seconds = string.format('%.1f', (vim.uv.hrtime() - started) / 1e9) }
      quickfix()
      vim.cmd('redrawstatus')
      vim.notify(M.status() .. ' / Space ro: output · Space rr: repeat', code == 0 and vim.log.levels.INFO or vim.log.levels.WARN)
      vim.api.nvim_exec_autocmds('User', { pattern = 'NeonTestFinished', data = { code = code, cwd = choice.cwd } })
    end)
  end)
  if ok then active = process
  else
    result = { code = 127, signal = 0, seconds = '0.0' }
    append('Could not start test: ' .. tostring(process))
    vim.notify(lines[#lines], vim.log.levels.ERROR)
  end
end

function M.choose()
  local root = require('neon_overlay.project').root()
  local choices = M.candidates(root)
  if #choices == 0 then return vim.notify('No supported test command found in ' .. root .. '. Run your project command in the terminal.') end
  vim.ui.select(choices, { prompt = 'RUN TEST / ' .. root, format_item = function(item) return item.label end }, function(item)
    if item then M.run(item) end
  end)
end

function M.repeat_last()
  if not last then return M.choose() end
  if require('neon_overlay.project').root() ~= last.cwd then
    vim.ui.select({ 'Run in ' .. last.cwd, 'Cancel' }, { prompt = 'Last test belongs to another project' }, function(_, index)
      if index == 1 then M.run(last) end
    end)
  else M.run(last) end
end

function M.stop()
  if active then active:kill(15); vim.notify('Stop requested for test process.') end
end

function M.setup()
  local overlay = require('neon_overlay')
  local commands = { NeonTest = M.choose, NeonTestLast = M.repeat_last, NeonTestOutput = M.output, NeonTestStop = M.stop }
  for name, fn in pairs(commands) do overlay.command(name, fn, 'Neon test runner') end
  if overlay.options.keymaps then
    for lhs, item in pairs({ rt = { M.choose, 'Choose a test' }, rr = { M.repeat_last, 'Repeat last test' },
      ro = { M.output, 'Show last test output' }, rs = { M.stop, 'Stop test process' } }) do
      overlay.map('<leader>' .. lhs, item[1], item[2])
    end
  end
  vim.api.nvim_create_autocmd('VimLeavePre', { group = vim.api.nvim_create_augroup('NeonOverlayTests', { clear = true }), callback = M.stop })
end
return M
