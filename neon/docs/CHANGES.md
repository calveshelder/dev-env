# Changes for the drop-in edition

The September 20 `dev-env-develop.zip` is the source of truth for the parent
repository layout. Its `.config/nvim/` directory is empty because the ZIP does
not contain the separate submodule's checkout. The new package integrates with
the initialized fork in your real clone, instead of replacing it.

| Area | Integration behavior |
| --- | --- |
| Existing tracked files | Retained byte for byte; only new paths are added |
| `.gitmodules` and Kickstart pointer | Retained; no fork commit needed for Neon |
| Shell setup | Native zsh and Bash adapters with shared tools; existing startup can be merged |
| Neovim | Existing Kickstart startup, then parent-managed controls and HUD |
| LSP, completion, formatting, plugins | Remain the responsibility of your Kickstart fork |
| tmux | New installed config retains Ctrl-a/hjkl and adds safe project switching |
| Ghostty and i3 | Source configurations remain; Ghostty replacement is opt-in, i3 is never installed by Neon |
| Shell Arena | Existing HUD, sounds and progress logic reused; work starts quiet |
| New computer | Normal Git clone, submodule initialization, platform dependencies, installer |

The earlier standalone Neon edition reorganized the editor into a separate
modular setup. **This edition uses your actual Kickstart fork.** Its LSP and
formatting behavior are not rewritten, and its plugin versions are not replaced
by the standalone edition's lockfile. The overlay supplies the new controls.

Use `neon-install.py` going forward. The original `dev-env` installer copies
and removes whole target configuration directories; running it after Neon
would interfere with the new symlinks. It is preserved unchanged for reference.
The original `run` and `runs/` tools are also preserved but never auto-executed.

The private home configuration can contain changes not present in this ZIP.
The home installer backs up replaced files; review that backup and copy any
desired machine settings into `~/.config/neon/local.zsh` or `local.bash`. Merge shell mode
preserves startup text but may retain duplicate pre-existing prompt/hooks;
clean mode gives the predictable initialization order documented here.

The drop-in helper refuses conflicting new paths rather than overwriting them,
so a checkout with other work is not silently flattened. Existing files and
the Git index are not modified by the helper.

No packages are installed by either helper. On macOS `neon deps` offers
Homebrew commands only for tools not already installed or available on PATH.
Your existing Neovim, tmux and Homebrew configuration are reused.
