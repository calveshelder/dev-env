# Terminal controls and project workspaces

The same controls work in Linux, WSL and macOS. The terminal emulator draws the
window; tmux keeps your project sessions alive; your shell runs commands; Neovim
edits code. You can use the shell and Neovim without tmux, too.

## Your everyday loop

Press **Ctrl-f at the zsh or Bash prompt** to pick a project. Or run:

```bash
tmux-sessionizer
tmux-sessionizer "$HOME/code/challenges/pokedexcli"
```

A new project opens an **edit** window and a **run** window in that directory.
If Neovim is installed, the edit window opens `nvim .`; otherwise it remains a
shell. The next visit reuses the existing session and leaves its windows alone.
Switching projects never closes your other sessions or detaches other clients.

Session names contain the directory name and a short hash of its canonical path.
Two projects called `api` in different folders get different sessions; a symlink
to the same project reuses its session. Moving a project creates a different
session, while the old session remains available through `tmux list-sessions`.

### Where the picker looks

Edit `~/.config/neon/projects` with one
absolute parent directory per line:

```text
~/code
~/personal
~/SpiderOnline/Projects
~/Projects
~/src
```

Those are also the defaults when the file is absent. Blank lines and lines
starting with `#` are ignored. `~` expands to your home directory; `$VARIABLE`,
backticks, and shell expressions are literal, never executed. Relative roots
and missing directories are skipped. Roots are local machine preferences.

Discovery checks immediate child folders and one further level through grouping
folders such as `code/challenges`. It stops descending when a folder has a common
project marker such as `.git`, `go.mod`, `composer.json` or `package.json`. Hidden
folders and dependency/build folders are skipped. Duplicates are removed.
An explicitly supplied directory works even if it is outside the configured roots.

```bash
tmux-sessionizer --list  # Inspect discovery without opening a session
```

The picker needs `fzf`; direct paths do not. Escape cancels without changing tmux.
Names containing spaces, quotes and shell punctuation are supported. Control
characters in paths are rejected. Legacy project `.tmux-sessionizer` files are
not sourced: opening a project should not silently execute its hydration script.

## tmux controls

**Prefix** means press **Ctrl-a**, release it, then press the next key.

| Keys | Action |
| --- | --- |
| Prefix, `1` / `2` | Select edit / run on a fresh project |
| Prefix, `f` | Open project picker |
| Prefix, `h j k l` | Focus panes left/down/up/right |
| Prefix, `H J K L` | Resize the pane |
| Prefix, `\|` | Split side by side in the current directory |
| Prefix, `-` | Split top and bottom in the current directory |
| Prefix, `c` | New shell window in the current directory |
| Prefix, `z` | Zoom pane / restore layout |
| Prefix, `D` | Open this project's `TODO.md` in a new Neovim window |
| Prefix, `[` | Enter scrollback/copy mode |
| In copy mode: `v`, move, `y` | Select and copy to the OS clipboard |
| In copy mode: `Escape` | Cancel |
| Prefix, `r` | Reload the installed shared tmux configuration |
| Prefix, `d` | Detach while keeping the session alive |
| Prefix, `s` | Choose an existing session |
| Prefix, Ctrl-a | Send a literal Ctrl-a to the application |

Mouse selection and resizing are enabled; keyboard navigation remains unchanged.
The bottom status line shows the session, windows, foreground application, clock,
and **COMMAND**/**ZOOM** indicators. It uses tmux's own format variables; it does
not launch a command on every refresh. This setup requires tmux 3.2 or newer.

## Clipboard

`neon-copy` receives text on standard input and selects an available endpoint:

| Environment | Endpoint |
| --- | --- |
| WSL with Windows interoperability | `clip.exe` |
| macOS | `pbcopy` |
| Wayland with a display session | `wl-copy` |
| X11 with a display session | `xclip -selection clipboard` |

There is no automatic OSC52 fallback. Missing clipboard support produces a clear
error rather than terminal escape sequences. In a plain SSH session, use tmux's
internal paste buffer with Prefix, `]`, or arrange an explicit clipboard endpoint.

Try `printf 'Neon clipboard check\n' | neon-copy` and paste into another app.
If it fails, check that your session has the expected display/interop and the
matching tool. On Wayland the package is usually named `wl-clipboard`; on X11 it
is `xclip`. Clipboard data is sent only to the selected OS clipboard endpoint.

## Windows Terminal

Open Windows Terminal **Settings → Open JSON file**. Back up the file first.
Add the object in `neon/config/windows-terminal/Shell-Arena.json` to your existing
`"schemes"` array, or replace the existing scheme with the same name. Do not
replace the whole Windows Terminal settings file or duplicate the scheme name.

In **your existing Arch/WSL profile** under `profiles.list`, add:

```json
"colorScheme": "Shell Arena",
"cursorShape": "filledBox",
"opacity": 100
```

Keep its `guid`, `name`, `source`, command line, and other settings. These are
object properties, so include commas between them and surrounding properties.
Keep your installed font, especially a Nerd Font if you already rely on its
icons. A comfortable starting size is 12. No font is silently installed or
assumed to exist, and the Windows profile ID is not hardcoded in this repository.

The scheme sets terminal ANSI colours. Neovim's truecolour theme is configured
separately, with a matching palette. Shell Arena's sounds and HUD also remain
their own component; see the main README for its controls.

## Ghostty

`neon/config/ghostty/config` supplies the same cyan/yellow/pink palette with modest
padding and a steady block cursor. It uses the installed default font. It adds
no shaders, global shortcuts, automatic window launches, or background animation.
Ghostty is the Linux/macOS option; Windows Terminal hosts your WSL environment.

## Troubleshooting and customisation

- **Ctrl-f does nothing:** use the command directly, verify the shared shell setup
  is loaded, and check `command -v tmux-sessionizer`. In Neovim, Ctrl-f retains
  its editor meaning; use the tmux prefix then `f` to switch projects there.
- **Existing tmux server cannot find commands:** ensure `~/.local/bin` is in its
  environment. Start a fresh shell before starting tmux. Do not kill a server
  containing work just to refresh it; `tmux set-environment -g PATH "$PATH"`
  refreshes its PATH for new windows.
- **The picker misses a directory:** inspect `tmux-sessionizer --list`, add its
  parent directory to `neon/projects`, or pass the project path directly.
- **Colours look reduced:** `echo "$TERM"` inside tmux should normally report
  `tmux-256color`. The terminal emulator and tmux must both support truecolour.
- **Reload cannot find the configuration:** Prefix, `r` resolves through the
  installer's `~/.config/neon/root` link. Check that the repository has not been
  moved or install it again from its new location. The installer targets
  conventional `~/.config` paths; custom `XDG_CONFIG_HOME` layouts need a manual
  adaptation and are not automatically managed.
- **Want to change mappings or colours everywhere?** Edit the shared config files
  in this repository, commit, pull on the other machine, and reload. Keep each
  machine's project roots in its local `neon/projects` file.

## Checking future changes

From the repository root:

```bash
python3 -m unittest discover -s neon/tests -p test_terminal.py
NEON_TEST_TMUX="$(command -v tmux)" python3 -m unittest discover -s neon/tests -p test_terminal.py
```

The second command additionally parses the actual configuration and creates two
temporary project sessions in a separate tmux server with its own socket. It
does not attach to or stop your normal server. Eighteen portable checks passed
during package preparation. The real tmux check is provided, but this build
environment blocked Unix sockets before a server could start; run it on your
machine for that final integration check. Windows/macOS clipboard behavior and
Ghostty appearance still need a check on the corresponding machine.
