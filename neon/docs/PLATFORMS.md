# Platform setup

Use Python 3.10+, zsh 5.8+ or Bash 4.4+, Neovim 0.12+, tmux 3.2+ and Git. The latest recorded
Kickstart submodule uses native `vim.pack`, which needs Neovim 0.12. The overlay
alone can also run on 0.11; that does not make the current fork compatible with it.
See VALIDATION.md for what was executed. Most optional tools degrade by
being absent; `neon doctor` reports what is missing. The managed installer uses
the conventional `~/.config` and `~/.local` paths, not custom XDG config/data roots.
Native Windows PowerShell/cmd installation is outside this package; use WSL.

## Arch inside WSL

Run in Arch, as your normal user:

```bash
sudo pacman -Syu --needed zsh neovim tmux git python fzf ripgrep fd starship atuin zoxide eza bat jq unzip libpulse wl-clipboard gcc make tree-sitter-cli
sudo pacman -S --needed go uv
```

The first command performs an ordinary full Arch upgrade before adding missing
packages. Substitute `bash` for `zsh` if that is the shell you choose on Arch,
and select it with the installer's `--shell` option.
The second is optional for Go/Python learning. Keep your existing Node manager;
this configuration lazily loads NVM when present. It does not install another
Node manager or replace your Lando/Docker setup.

Keep Linux projects on the distro filesystem, for example `~/code`, and use
Windows Terminal to host it. Start with the existing font. Apply the colour
scheme using [TERMINAL.md](TERMINAL.md); do not overwrite Windows Terminal's whole
settings file or copy another machine's profile GUID.

`paplay` uses the existing WSLg audio server when available. The add-on does not
start another PulseAudio server. `neon-copy` selects Windows `clip.exe` when WSL
interoperability is available. Test clipboard and `arena soundtest` on the device.
Neovim retains your Kickstart clipboard settings and Neovim provider detection.
Check `:checkhealth vim.provider` if system yanks fail; `wl-clipboard` supplies
WSLg's `wl-copy`/`wl-paste`, and `win32yank.exe` is another common WSL provider.

## macOS

Keep your current zsh and Homebrew installations. First inspect what's missing
from the dev-env repository root:

```bash
python3 neon/bin/neon deps --platform macos
python3 neon/bin/neon doctor
```

The first command reads `brew list --formula` and command availability, then
prints a Homebrew command containing only missing suggestions. It does not run
that command or reinstall/upgrade anything. Already available Neovim and tmux
are omitted. `doctor` checks versions and reports issues; it also installs
nothing. Use `neon deps --all --platform macos` only to see a full package list.

Install configuration with `--shell zsh --shell-mode merge` to retain your
existing `.zshrc` and append the shared loader. `.zprofile`, `.zshenv`, your
Homebrew startup and login-shell choice remain in place. Optional tools simply
remain inactive if missing. Local zsh settings go in `~/.config/neon/local.zsh`.

If you later choose Bash, use a Homebrew Bash 4.4+ (`brew install bash` only if
needed), and its `bin/bash` executable from `brew --prefix bash`. The package
does not change `/etc/shells` or invoke `chsh`. Bash is not required for the
zsh integration's automatic hooks.

Kickstart builds native plugins and parsers. If Apple Command Line Tools are
missing, run `xcode-select --install`. On both platforms check `nvim --version`
before first launch. The official Homebrew and Arch package pages report 0.12.5
at the time of this review; your local packages may need upgrading.

Ghostty is optional and has a matching configuration. To install its config,
include `ghostty` in your component list, for example:

```bash
python3 neon-install.py plan --profile work --shell zsh --shell-mode merge --components shell,nvim,tmux,starship,arena,ghostty
python3 neon-install.py apply --profile work --shell zsh --shell-mode merge --components shell,nvim,tmux,starship,arena,ghostty
```

The sound helper selects macOS `afplay`; clipboard uses `pbcopy`. Their command
construction is tested, but actual macOS audio, fonts and clipboard need a check
on your Mac. Source files and sound samples contain no Windows-only path.

## Debian/Ubuntu Linux

```bash
sudo apt update
sudo apt install zsh git python3 tmux fzf ripgrep fd-find bat jq unzip pulseaudio-utils build-essential
```

Check `nvim --version`. Install Neovim 0.12 or newer from the
[official releases](https://github.com/neovim/neovim/releases) if the distribution
package is older. Install the tree-sitter CLI required by the current Kickstart
parser setup. Follow the official installation instructions for
[Starship](https://starship.rs/guide/), [Atuin](https://docs.atuin.sh/latest/guide/installation/)
and [zoxide](https://github.com/ajeetdsouza/zoxide) when desired.
The shell knows the Debian `fdfind` executable name. Old fzf releases use the
packaged Bash keybinding file when `fzf --bash` is unavailable.

For desktop clipboard integration install `wl-clipboard` on Wayland, or `xclip`
on X11. A display server and an available endpoint are needed; a remote SSH
session does not magically gain access to the local machine's clipboard.

## Work-specific tools

Existing Lando, Composer, Rust/Cargo, Go, NVM and AWS EB CLI paths are added only
when their conventional directories exist. Sonar Scanner's conventional `/opt`
path is similarly optional. Extra paths go into local.zsh or local.bash. No project is
created automatically and no Drupal installation is run by this bootstrap.

PHP formatting and language servers remain controlled by your Kickstart fork.
This overlay does not rewrite those settings or install a global Composer
formatter. Keep each project's `composer.lock`, PHPCS rules and Lando
configuration with that project, and configure its formatter in Kickstart.

## Primary references

- [Homebrew Bash formula](https://formulae.brew.sh/formula/bash)
- [Homebrew Neovim formula](https://formulae.brew.sh/formula/neovim)
- [Arch Neovim package](https://archlinux.org/packages/extra/x86_64/neovim/)
- [Arch Atuin package](https://archlinux.org/packages/extra/x86_64/atuin/)
- [Starship configuration and timeouts](https://starship.rs/config/)
- [Atuin configuration](https://docs.atuin.sh/latest/configuration/config/)
- [fzf shell integration](https://github.com/junegunn/fzf#setting-up-shell-integration)
- [WSLg audio architecture](https://github.com/microsoft/wslg)
- [Windows Terminal profile appearance](https://learn.microsoft.com/en-us/windows/terminal/customize-settings/profile-appearance)
