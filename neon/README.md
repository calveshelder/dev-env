# Neon + your Kickstart fork

One dev-env checkout supplies your zsh or Bash, project workspaces, shell atmosphere
and editor add-ons. Your existing Kickstart fork supplies the editor itself.
The same tracked files are reusable on macOS, Arch Linux and Arch in WSL.

## Start here

From the **dev-env repository root**, follow [README-NEON.md](../README-NEON.md).
Preview installation before applying. Installing creates symlinks in your home
and backs up replaced files; it never commits, pushes or updates a submodule.
The ZIP's separate `apply-to-repo.py` only copies additive source files into
your checkout. These are two different operations.

## What is where

Paths below are relative to the dev-env root.

| Path | Purpose | Which repository owns it? |
| --- | --- | --- |
| `.config/nvim/` | Kickstart init, plugin specs and editor customization | Kickstart fork; parent records a commit pointer |
| `.gitmodules` | Existing Kickstart submodule URL and path | dev-env; unchanged |
| `neon-install.py` | Entry point for preview, apply and restore | dev-env |
| `neon/install.py` | Portable home installer and backup transactions | dev-env |
| `neon/shell/` | Native zsh/Bash environment, history, search, aliases and startup ordering | dev-env |
| `neon/nvim/` | Startup hook plus command deck, test controls and focus/HUD additions | dev-env |
| `neon/bin/`, `neon/lib/` | `neon`, project picker and clipboard helper | dev-env |
| `neon/config/` | Starship, tmux, new-install Atuin and optional terminal appearance | dev-env |
| `neon/vendor/shell-arena/` | HUD, command-submit audio, quests and generated sound packs | dev-env |
| `neon/examples/` | Examples for private per-machine settings | dev-env |
| `neon/docs/`, `neon/tests/` | Reference material and repeatable checks | dev-env |
| `env/`, `runs/`, `.config/i3/`, old terminal configs | Previous setup and platform-specific scripts | dev-env; retained unchanged |

Your installed `~/.config/nvim` points directly to the submodule. Kickstart's
runtime directory, plugin lockfile and plugin setup therefore remain its own.
Your current revision uses native `vim.pack` and `nvim-pack-lock.json`; it needs
Neovim 0.12+. Neon does not add a second plugin manager. An older checkout using
lazy.nvim keeps its own setup too; the integration never migrates plugin managers.

## Controls to learn first

| Where | Control | Action |
| --- | --- | --- |
| Shell | `Ctrl-f` | Pick a project and enter its tmux workspace |
| Shell | `Ctrl-r` | Search Atuin history if installed |
| Shell | `neon` | Open the shell command deck |
| Shell | `neon editor` | Launch Kickstart with the Neon overlay explicitly |
| Shell | `neon test` | Choose a project test command |
| Shell | `neon scratch` | Capture a note in a private local file |
| Shell | `arena` | See HUD, sound and quest controls |
| Neovim | `Space a` / `:NeonDeck` | Discover editor actions |
| Neovim | `Space rt` / `rr` / `ro` / `rs` | Choose test / repeat / output / stop |
| Neovim | `Space uz` | Toggle the focus view |
| tmux | `Ctrl-a`, then `f` | Change project |
| tmux | `Ctrl-a`, then `h/j/k/l` | Move between panes |
| tmux | `Ctrl-a`, then `r` | Reload the tmux configuration |

Editor mappings are only added when their keys are available. Existing Kickstart
bindings win; use named commands when a key is already taken. See
[NEOVIM.md](docs/NEOVIM.md) for the overlay controls and options.

## Atmosphere and learning

Arena reacts automatically to commands submitted in interactive zsh or Bash. OPS counts
operations; XP and quests follow Arena's explicit rules. Sound is not attached
to every individual keystroke or every Neovim Enter press. The integration cannot
see tests running on Boot.dev's website. Run local checks through the editor or
shell test controls, and use your existing quests for deliberate learning wins.

The personal profile retains your saved Arena preferences. Work starts with
quiet visuals and muted sounds. Both use the same source; settings, XP, notes
and histories remain local. Start `arena soundtest` at low volume.

Zsh plays its submit cue when a command starts; blank Enter presses and
continuation lines stay silent. Existing ZLE/Atuin Enter widgets are retained.

The prompt avoids scanning every untracked file, NVM loads only when called,
and the overlay adds no plugin downloads or background network checks.
Kickstart still performs whatever plugin/tool setup your fork normally performs.
These are implementation choices, not a measured performance guarantee.

## Your private settings

| File under your home | Use |
| --- | --- |
| `~/.config/neon/local.bash` | Machine-only PATH entries, aliases and feature switches |
| `~/.config/neon/local.zsh` | The equivalent native zsh overrides |
| `~/.config/neon/local.lua` | Overlay options; see NEOVIM.md and the example |
| `~/.config/neon/projects` | Project search roots, one path per line |
| `~/.config/neon/machine.json` | Installer-selected personal/work profile |
| `~/.local/state/neon/notes/inbox.md` | Private scratch notes |
| `~/.local/state/neon/backups/` | Recoverable installation backups |

Examples are tracked; live private settings stay outside the repository. Existing
Atuin configuration is preserved. The integration never configures cloud history
sync, Git identity, credentials or project secrets.

## Shell and package portability

The editor, prompt, tmux, project picker and configuration layout are shared.
Startup files and command hooks have native adapters for **zsh and Bash**;
other shells can use `neon editor`, `neon projects` and the CLI, but do not gain
the automatic shell HUD. This does not claim universal fish/PowerShell support.

Your existing Homebrew installations are reused. The installer performs no
package operations, manual binary downloads or login-shell changes. `neon deps`
prints suggestions; on macOS it reads installed formulae and PATH first to omit
tools you already have. `neon deps --all` shows the full set for a fresh machine.

## Guides

- [Installation and rollback](docs/INSTALLER.md)
- [Neovim overlay and Kickstart ownership](docs/NEOVIM.md)
- [tmux, projects, clipboard and terminal colors](docs/TERMINAL.md)
- [Mac, Arch/WSL and other Linux setup](docs/PLATFORMS.md)
- [Commit, push and set up your next machine](docs/SYNC.md)
- [What changed and what was retained](docs/CHANGES.md)
- [Validation and device checks](docs/VALIDATION.md)
- [Source attribution](docs/THIRD_PARTY.md)

Run `neon docs` to open this guide, or `neon docs sync` for the Git workflow.
