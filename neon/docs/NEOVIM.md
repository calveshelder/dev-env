# Neovim: your Kickstart fork plus Neon

The full editor reference is [neon/nvim/README.md](../nvim/README.md).

Your `.config/nvim` remains the Git submodule for your Kickstart fork. The
installer points `~/.config/nvim` there. Neon loads that original configuration
first, then adds the command deck, test runner, optional HUD and focus mode from
the parent repository's `neon/nvim/`. The overlay writes nothing into the
submodule and does not install a second plugin manager or plugin set.

After installation, start a fresh Neon Bash/Zsh shell and run `nvim`, or run
`neon editor` explicitly from another shell. Existing `VIMINIT` settings win over
automatic shell integration. `nvim --clean` and an explicit `nvim -u ...` bypass
automatic integration. A custom `NVIM_APPNAME` uses its own configuration without
Neon. GUI editors launched outside the shell normally use plain Kickstart.

`$MYVIMRC` points to Kickstart's actual `init.lua`. The plugin manager's default
lockfile remains in the submodule, and Kickstart owns its theme, language servers, formatting and
plugin updates. The overlay does not enable Neovim's `exrc` option; normal
`VIMINIT` startup keeps the existing setting. The explicit `-u` launch used by
`neon editor` follows Neovim's normal explicit-config startup rules.

Press **Space a** for the command deck. **Space rt/rr/ro/rs** chooses, repeats,
shows and stops tests; **Space uz** toggles focus; **Space uh** toggles the HUD.
Existing bindings and prefixes win, with conflicts reported by `:NeonHealth`.
The corresponding `:Neon...` commands remain available if a shortcut is occupied.

Your current pinned fork (`80743df`) uses native `vim.pack`, requiring **Neovim
0.12+**. Inspect plugin state with `:lua vim.pack.update(nil, { offline = true })`
and request updates with `:lua vim.pack.update()`. Its review buffer uses `:write`
to apply updates and `:quit` to cancel. Language tools remain under `:Mason`.
Older lazy.nvim-based fork commits retain their normal `:Lazy` workflow.

This additive edition has no `:NeonInstall` or `:NeonTools` commands. Keep plugin,
formatter and LSP edits in the fork; commit/push those there before committing a
new submodule pointer in dev-env. Overlay edits are ordinary files committed
directly to dev-env. For reproducible plugin versions, track the current fork's
`nvim-pack-lock.json` as its README recommends (upstream ignores it).

For machine-only preferences, copy [examples/local.lua](../examples/local.lua) to
`~/.config/neon/local.lua`; supported options are `hud` and `keymaps`.

The [full reference](../nvim/README.md) documents test safeguards, output limits,
all commands, startup behavior and the included Neovim integration tests.
