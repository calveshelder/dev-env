local M = {}
M.markers = { 'go.work', 'go.mod', 'pyproject.toml', 'pytest.ini', 'setup.py', 'composer.json', 'package.json', '.git' }
function M.root(bufnr)
  local name = vim.api.nvim_buf_get_name(bufnr or 0)
  if name == '' or name:match('^%w+://') then
    return vim.fs.root(vim.uv.cwd(), M.markers) or vim.uv.cwd()
  end
  return vim.fs.root(name, M.markers) or vim.fs.dirname(name)
end
function M.has(root, name) return vim.uv.fs_stat(root .. '/' .. name) ~= nil end
function M.command_available(argv, root)
  local executable = argv[1]
  if executable:find('/', 1, true) and executable:sub(1, 1) ~= '/' then executable = root .. '/' .. executable end
  return vim.fn.executable(executable) == 1
end
return M
