# Installing, merging and restoring

The installer uses Python 3.10 or newer and the standard library. Run it as your
normal account inside Linux, WSL or macOS. It does not install packages, contact
the network, change your login shell, or modify Windows Terminal settings.

Keep your dev-env checkout in a permanent location such as `~/code/dev-env`. Installed
links point into the checkout; deleting or moving it will break those links.
Do not place the checkout inside a destination it will manage, such as
`~/.config/nvim`.

Run these commands from the dev-env repository root. The drop-in adds `neon/`
and `neon-install.py`; it leaves your existing `.gitmodules`, `.config/nvim`
submodule, `env/`, `runs/`, and legacy installation scripts alone. Use
`neon-install.py` for this setup. Running the older `./dev-env` or `./run`
afterward can replace the installed configuration again.

## Initialize your existing editor

Your fork of Kickstart remains the editor's configuration repository. Before
installing the default components, initialize it from the dev-env root:

```bash
git submodule update --init --recursive
```

The installer checks that `.gitmodules` declares `.config/nvim` and that
`.config/nvim/init.lua` exists. It never fetches the submodule, checks out a
branch, changes its commit, or edits its files. Your existing SSH URL is
preserved, so a new computer needs GitHub SSH access or a local HTTPS URL
override as described in the setup guide. To start without the editor, use
`--components shell,tmux,starship,arena` on both plan and apply.

`~/.config/nvim` points to that submodule, preserving Kickstart's runtime paths
and lockfile location. Neon loads its additions through the wrapper at
`neon/nvim/init.lua`, using the shell's `VIMINIT` integration and explicit Neon
editor launches. An existing `VIMINIT` is preserved. Direct Neovim launches from
other shells or GUI applications need the documented wrapper launch to receive
the additions; `nvim --clean` and explicit `-u` startup choices bypass them.

## Choose the shell migration

On your current Mac, select **zsh** and preview **merge mode** to retain your
existing Homebrew setup and other startup additions:

```bash
python3 neon-install.py plan --profile personal --shell zsh --shell-mode merge
```

The preview writes nothing. It lists each path that would be created or
replaced. Inspect the repository configuration and the source blocks in
`neon/install.py` before applying:

```bash
python3 neon-install.py apply --profile personal --shell zsh --shell-mode merge
```

Use `--profile work` on your work computer. Your current terminal keeps its old
shell state until you open a new terminal.

`--shell auto` is the default: it selects zsh when `$SHELL` names zsh,
otherwise Bash. Use `--shell bash` on a Bash-based Arch/WSL setup, or
`--shell both` if you actively use both shells. This selection controls which
startup files are managed; it does not change your login shell. The installer
does not run Homebrew, reinstall packages, or alter installed package versions.

**zsh** manages only `.zshrc`. Your `.zprofile`, `.zshenv`, and `.zlogin` stay
untouched, including a Homebrew `shellenv` entry you already use. If `ZDOTDIR`
is set to an absolute directory inside your home, its `.zshrc` is used instead.
Relative or outside-home `ZDOTDIR` values are refused before any change; use a
home-local directory or omit the shell component and integrate the source
block into your existing shell manager. Symlinked destination directories are
refused as described below.

**Bash** manages `.bashrc` and `.bash_profile`; `.profile` stays untouched.

**Clean mode** is optional: pass `--shell-mode clean` to replace the selected
startup files with short source blocks, backing up their complete originals.
This removes previous eager startup loaders and duplicate prompt initialization.
For Bash, `.profile` is not automatically sourced by the clean startup files.
Review old exports and aliases in the backup, then copy the ones you still
need into `~/.config/neon/local.zsh` for zsh or `~/.config/neon/local.bash` for
Bash. These local files are never managed or overwritten.

**Merge mode** is the default when `--shell-mode` is omitted. It preserves the
existing startup text and adds one marked Neon block. Only recognisable,
standalone source commands for the previous `~/.config/dev-shell/init.bash`
and `~/.local/share/shell-arena/arena.bash` are commented out. It recognises
ordinary `source`/`.` commands, optionally guarded with `[ -f ... ]` or
`[[ -r ... ]]` (either `-f` or `-r`), using quoted `$HOME`, `${HOME}`, tilde,
or the selected home's absolute path. Compound commands and unknown shell
code are retained. Existing eager loaders may still cost startup time in this
mode; it cannot guarantee elimination of duplicate tools in arbitrary files.

For startup files that are already symlinks, the installer backs up the link
itself and creates a regular startup file at its home destination. Merge mode
copies the readable source text into that file; clean mode writes only the
minimal loader. The symlink's source is never edited. Restore reinstates the
original symlink. A broken startup symlink requires clean mode or repair first.
Other dotfiles managers may recreate their links when rerun; choose which
manager owns shell startup, or omit the shell component.

## Install only selected parts

```bash
python3 neon-install.py plan --profile personal --components nvim
python3 neon-install.py apply --profile personal --components nvim
```

The default components are `shell,nvim,tmux,starship,arena`. Optional components
are `ghostty` and `atuin`. Shell setup already includes an absent-only Atuin
configuration. A component list selects this installation's changes; it does
not uninstall components installed earlier.

| Component | Managed destination | Repository source |
| --- | --- | --- |
| Always | `~/.config/neon/root` | `neon/` |
| Always | `~/.config/neon/machine.json` | Generated profile; extra existing keys retained |
| Always | `~/.config/neon/machine.bash` | Generated shell profile, avoiding Python on startup |
| Always | `~/.local/bin/neon` | `neon/bin/neon` |
| shell, zsh selected | `~/.zshrc` (or home-local `$ZDOTDIR/.zshrc`) | Managed source block for `neon/shell/init.zsh` |
| shell, Bash selected | `~/.bashrc`, `~/.bash_profile` | Managed source blocks for `neon/shell/init.bash` and `profile.bash` |
| shell or tmux | `~/.local/bin/neon-copy` | `neon/bin/neon-copy` |
| nvim | `~/.config/nvim` | `.config/nvim` (existing Kickstart submodule) |
| tmux | `~/.config/tmux/tmux.conf`, `~/.tmux.conf` | `neon/config/tmux/tmux.conf` |
| tmux | `~/.local/bin/tmux-sessionizer` | `neon/bin/tmux-sessionizer` |
| starship | `~/.config/starship.toml` | `neon/config/starship.toml` |
| arena | `~/.local/share/shell-arena` | `neon/vendor/shell-arena` |
| ghostty | `~/.config/ghostty/config` | `neon/config/ghostty/config` |
| shell or atuin | `~/.config/atuin/config.toml` | `neon/config/atuin/config.toml`, only if destination is absent |

Existing Atuin configuration and history remain in place. Shell Arena's
database lives outside its installed code directory, so replacing the Arena
code does not replace XP. Shared symlinked configuration is edited directly in
the checkout, where Git can show and sync the changes. Changes under `neon/`
belong to dev-env. Edits through `~/.config/nvim` belong to the Kickstart
submodule: commit and push those in the fork, then commit its updated pointer
in dev-env. The integration itself requires no submodule file changes.

The installer deliberately targets `HOME/.config` and `HOME/.local`; it does
not relocate configuration according to `XDG_CONFIG_HOME` or `XDG_DATA_HOME`.
If you use custom XDG paths, reconcile them before installation. `--home PATH`
selects a different existing destination home for previews, staging and tests;
it never changes the `HOME` environment variable. Run the installed setup as
the user who owns that destination. `--home` is not a sandbox or a change to
the current shell's home.

## Backups and rollback

Each nonempty apply creates a private backup directory under
`~/.local/state/neon/backups/TIMESTAMP-ID`. Existing managed files, directories
and symlinks are moved there intact; directories are not recursively deleted.
A JSON manifest records the original type, target paths, installed file hashes
and modes, symlink targets, and transaction progress. Reapplying the same
configuration makes no changes and creates no extra backup.

```bash
python3 neon-install.py list-backups
python3 neon-install.py restore 20260920T120000Z-0123abcd
```

Use an actual ID printed by `list-backups`. Restore checks every installed path
before changing any of them. If you modified a managed generated file, changed
its permissions, removed an installed link, or replaced a link with another
target, restore refuses and names the conflicting paths. Save those edits
elsewhere and return the path to the installed state before trying again.
There is deliberately no destructive `--force` option.

Edits inside a symlinked repository directory remain in the checkout after
restore. Restoring the old `~/.config/nvim` replaces the installed link with the
original directory; it does not undo your Git changes. Unmanaged files added
alongside installed files are retained. Restored installed files are retained
inside the backup's `restored-installation` directory for inspection.

Caught installation failures trigger rollback; a failed restore attempts to
reinstate the installation. Only empty newly created parent directories are
removed. A per-home advisory lock prevents simultaneous installer mutations.
The installer also refuses paths beneath symlinked destination directories,
so it cannot silently write through `~/.config` to an unexpected location.

Backups need to be on the same filesystem as replaced targets for atomic
renames. A mount point inside the home can therefore cause an apply to fail
and roll back. Sudden power loss, `SIGKILL`, manual backup edits, or external
concurrent file changes can leave a transaction requiring inspection. In that
case inspect the status, paths and errors in `manifest.json`; originals remain
in its `files` directory unless already restored. Do not delete a backup until
you have checked its contents. Backups may contain your previous private
configuration and should not be committed to the shared repository.

## Verification

```bash
python3 -m unittest discover -s neon/tests -p test_installer.py -v
```

The tests use temporary explicit home paths. They verify read-only previews,
component selection, symlink and intact directory restoration, clean and merge
migration, preserved Atuin/local settings, idempotence, conflicting edits,
failure rollback, failed-restore recovery, locking, and generated Bash syntax.
They also verify initialized submodule detection, unchanged `.gitmodules` and
Kickstart files, symlinked startup migration, source checkout protection,
automatic and explicit shell selection, preserved zsh login files, home-local
ZDOTDIR routing, and restoration of both shells.
They do not install into the account running the tests.
