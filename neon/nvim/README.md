# Neon beside your Kickstart fork

Your real Neovim configuration remains `.config/nvim`, the Git submodule pointing
at your `calveshelder/kickstart.nvim` fork. Neon does **not** replace `init.lua`,
your plugin manager, plugin pins, LSP configuration, formatting, or theme.

The parent repository owns this small overlay. The installer links
`~/.config/nvim` to the submodule as before. The Neon Bash/Zsh integration exports
`VIMINIT` only if you did not already set it. Neovim then loads this wrapper,
which runs the real Kickstart `init.lua` first and adds the overlay afterward.
`stdpath('config')`, your runtime paths and the plugin manager's default lockfile
still point to Kickstart. No file is written into the submodule by the overlay.
Normal Kickstart plugin installation/updates can still change its lockfile;
those are changes in your fork, as usual.

Your current dev-env submodule commit (`80743df`) uses Neovim's native `vim.pack`,
which requires **Neovim 0.12+**. Its lockfile is `nvim-pack-lock.json`; the fork's
README recommends tracking that file even though upstream ignores it. Inspect
plugins with `:lua vim.pack.update(nil, { offline = true })`; request updates with
`:lua vim.pack.update()` and follow the review buffer (`:write` applies updates,
`:quit` cancels). Mason remains available for language tools. Older commits using
lazy.nvim keep their normal `:Lazy` commands and `lazy-lock.json` instead.

An explicit `-u` or `--clean` bypasses `VIMINIT`. A custom `NVIM_APPNAME` loads its
own configuration without Neon. If `~/.config/nvim` points to a different
configuration, the wrapper loads that configuration and skips Neon too.
A graphical editor launched outside the Neon shell does not inherit the shell's
environment and therefore loads ordinary Kickstart. `neon editor` explicitly
launches with the overlay when you want it from another shell.

Because Vim also reads `VIMINIT`, the exported expression checks which editor is
running. Plain Vim loads its conventional Unix vimrc locations, then `EXINIT` or
the usual fallback, through `vim-fallback.vim`; it never executes the Neon Lua.
An existing user-provided `VIMINIT` is never replaced by the shell integration.

## Controls

With your fork's Space leader:

| Shortcut | Command | Action |
| --- | --- | --- |
| Space a | `:NeonDeck` | Search, tests, focus, HUD and configuration actions |
| Space rt | `:NeonTest` | Choose a test command for the project |
| Space rr | `:NeonTestLast` | Repeat the last command |
| Space ro | `:NeonTestOutput` | Show captured output; q closes it |
| Space rs | `:NeonTestStop` | Signal the running test process to stop |
| Space uz | `:NeonFocus` | Hide visual clutter, then restore it |
| Space uh | `:NeonHud` | Switch between Neon and Kickstart statuslines |
| — | `:NeonHealth` | Show overlay health and shortcut collisions |

Existing mappings and their prefixes win. A conflicting Neon shortcut is skipped;
the corresponding command remains available. Later-loaded plugins may assign
their own mappings too. Your Kickstart search, navigation and completion controls
remain in place.

The cyan/magenta HUD displays mode, file, Git branch (from existing Gitsigns),
diagnostics and the test result. The work profile uses green accents. It performs
no shell calls, network requests or periodic polling. `:NeonHud` restores the
statusline captured from Kickstart. Focus mode restores the original window's
numbers/winbar and the previous diagnostic text and statusline visibility.

## Explicit tests

Presets support Go, Python/pytest, JavaScript package tests, and project-local
PHPUnit/Lando. The nearest manifest or Git boundary determines the project root.
Tests run asynchronously with argument lists, never with shell-string evaluation.
Modified buffers in the selected project must be saved first. Output is capped
at 6,000 lines and 16,000 characters per line; basic file:line errors are added to
a new quickfix list. Run a command in your terminal when you need complete output.
Stop signals the launched process, not an entire descendant process tree.

No tests run automatically on startup or file saves. Boot.dev website tests are
not visible to the local shell/editor. The overlay does not award XP for test
output or add keyboard sounds inside Neovim; shell sounds remain a shell feature.

## Personal overrides

Create `~/.config/neon/local.lua` (outside both repositories):

```lua
return {
  hud = false,     -- Keep Kickstart's statusline initially; :NeonHud still works.
  keymaps = true,  -- false keeps commands but adds no Neon shortcuts.
}
```

To change plugins, language servers, formatting or your base theme, edit the
Kickstart submodule and commit/push to your fork first. Then commit the updated
submodule pointer in dev-env. Changes to `neon/nvim/` belong only to dev-env.
On a new machine clone dev-env with `--recurse-submodules`, install the required
tools and run the Neon installer. Kickstart retains its normal plugin bootstrap;
this overlay has no separate plugin set and no `:NeonInstall` command.

The overlay's own APIs work with Neovim 0.11+, but **your current Kickstart fork
requires 0.12+** for `vim.pack`. Use the parent repository's dependency guidance.

## Validation

`tests/verify.py --nvim /path/to/nvim` runs the overlay in isolated temporary XDG
directories, with a minimal stand-in for the submodule. It checks real startup
precedence, preserved paths, conflicting keymaps, HUD/focus restoration, explicit
test execution, custom-app isolation, clean-mode bypass and Vim fallback logic.
It does not download or change your actual Kickstart plugins. The fixture checks
the overlay on Neovim 0.11.5 and 0.12.5; it does not install or run the current
fork's entire plugin set.
