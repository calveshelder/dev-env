# Neon integration for your dev-env repository

This is an additive integration. Your existing `dev-env`, `run`, `runs/`,
`env/`, `.config/`, `.local/`, `.gitignore` and `.gitmodules` remain yours.
The new configuration lives under `neon/`; its installer is `neon-install.py`.

**Your `.config/nvim` remains a Git submodule of your Kickstart fork.**
No Kickstart source, plugin manager or submodule commit is replaced by this
integration. Neon loads your existing init first and adds discoverable editor
actions afterward. The zsh or Bash shell exports the startup hook; `neon editor` also
works when you launch from another shell.

Read [the complete guide](neon/README.md) for the component map, setup, shortcuts
and customization. [Sync and commit instructions](neon/docs/SYNC.md) explain both
repositories and how to prepare your next computer.

## Install from this repository

Use a real Git clone with its submodule initialized, Python 3.10+, zsh 5.8+
or Bash 4.4+, Neovim 0.12+ and tmux 3.2+. Your existing macOS zsh and Homebrew
tools are reused. Neither the drop-in helper nor the installer installs packages.

```bash
git submodule update --init --recursive
python3 neon/bin/neon deps
```

On macOS the helper suggests only missing tools, omitting existing formulae and
commands on PATH. Run a suggested Homebrew command only if you want those extras.
Then preview and merge into your existing zsh setup:

```bash
python3 neon-install.py plan --profile personal --shell zsh --shell-mode merge
python3 neon-install.py apply --profile personal --shell zsh --shell-mode merge
```

Use `--profile work` on your work computer. Merge mode keeps `.zshrc` contents
and appends a managed loader; `.zprofile` and your login shell stay unchanged.
Use `--shell bash` on a Bash machine, or `--shell both` to configure both.
Optional clean mode replaces the selected shell's startup entrypoints with
backups. Machine-only settings belong in `~/.config/neon/local.zsh` or
`local.bash`. Keep the checkout in place because installation uses symlinks.

Open a new terminal, keeping the old one open, and try:

```bash
neon doctor
arena soundtest
neon editor
```

Use `:NeonDeck` or **Space a** in Neovim. Your current Kickstart revision uses
Neovim's native `vim.pack`: `:lua vim.pack.update(nil, { offline = true })`
inspects plugin state. Use your fork's tool-installation workflow. There is no
`:NeonInstall` command in this submodule-preserving edition.

For rollback run `python3 neon-install.py list-backups`, then
`python3 neon-install.py restore BACKUP_ID` using the printed backup ID.

**Use `neon-install.py` for this setup going forward.** The old `./dev-env`
script is preserved for history, but running it again would copy the old
configuration over installed paths. See [changes](neon/docs/CHANGES.md).
