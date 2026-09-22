# Validation of the drop-in integration

The current uploaded parent files were compared byte for byte with the
`develop` checkout at `632b0ddb8766daac4856bf895e4a4f7e4fff62eb`; they match.
Its Neovim gitlink records `80743df53d8f7058fc5b60e41f1081d11df9c880`.
The ZIP adds parent-owned files and does not package either Git database.

## Checks executed

- The complete payload was applied to an actual checkout matching the upload,
  committed with explicit paths while unrelated staged work remained untouched,
  and cloned again. HTTPS submodule initialization recovered the exact recorded
  editor commit; both zsh and Bash installation previews passed in the fresh clone.
- A temporary home passed zsh merge, apply, idempotence and restore while
  preserving its existing `.zshrc` text, `.zprofile`, and absent Bash entrypoints.
- 86 repository Python tests passed; one optional real tmux test was skipped.
  This includes 36 home-installer tests, 10 native zsh startup tests, 7 native
  zsh Arena tests, shell/CLI tests, and terminal-helper tests.
- 37 existing Shell Arena state/audio tests passed.
- 14 additive drop-in copier tests passed: read-only preview, conflict refusal,
  unchanged Git index/submodule/dirty files, safe paths, idempotence and rollback.
- 9 real Neovim startup/overlay tests passed on both 0.11.5 and 0.12.5, using
  a minimal stand-in for Kickstart. They exercise VIMINIT, explicit launch,
  custom-app isolation, original runtime paths, unchanged init/lock files,
  shortcut collisions, HUD/focus restoration and test process/output behavior.
- Native zsh 5.9 tests preserve exit status, pipeline status, existing hooks,
  Enter widgets and already-loaded integrations. Audio tests use a fake player
  to verify FIFO delivery; physical sound is not asserted.
- The missing-tools Homebrew suggestion is tested against an installed package
  inventory, ensuring Neovim/tmux/Python already present are not suggested again.

## Remaining device checks

A fresh run of the actual current Kickstart fork on official Neovim 0.12.5
downloaded ten plugins without a reported startup error, but reached the
150-second test limit before all downloads completed. Full current-fork plugin
startup is therefore **not** claimed as verified. Your fork is left intact;
its plugin bootstrap, native builds, LSP installations and parser updates remain
its own behavior. Its current version requires 0.12 even though the independent
overlay fixtures also pass on 0.11.

Actual macOS/WSLg audio, terminal colors, clipboard round trips and live tmux
sessions require checking on your device. This managed runtime previously
rejected tmux's Unix socket, so its optional real-server test remains skipped.
The plain-Vim fallback was exercised through Neovim's Vimscript interpreter;
an actual Vim executable was not available for that check.

Package installation is never performed by the drop-in helper or home installer.
The Homebrew helper reads local inventory and prints suggestions; the user
chooses whether to run a package-manager command.

## Repeat checks

From dev-env:

```sh
python3 -m unittest discover -s neon/tests -p 'test_*.py' -v
python3 neon/nvim/tests/verify.py --nvim "$(command -v nvim)" -v
```

From `neon/vendor/shell-arena`:

```sh
python3 -m unittest -v tests_audio tests_arena
```

From the extracted drop-in ZIP:

```sh
python3 -m unittest discover -s checks -p 'test_*.py' -v
```

Use temporary explicit homes for installer experiments. The included tests do
not replace the process HOME or install into your account. For the actual device
check, retain an old terminal while opening a new zsh terminal, then try
`neon doctor`, `arena soundtest`, Ctrl-f into a project, clipboard copy/paste,
and `neon editor` followed by `:NeonHealth` and `:NeonDeck`.
