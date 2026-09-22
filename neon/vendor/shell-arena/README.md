# Shell Arena v2 — Neon Link

A small Bash add-on for Helder's Arch/WSL + Atuin + Starship + Neovim setup.
Original retro-game-inspired sound cues, a compact neon HUD, and learning quests.
No GunZ assets are included. This is a motivation experiment, not an ADHD treatment
or a claim that sounds or XP improve retention for everyone.

## What's new: automatic atmosphere

Use the shell normally. No `arena` prefix is needed for any of these effects:

- **Cyber (default):** cyan/yellow HUD, pink milestone highlights, two alternating
  metallic submit clicks and two success chirps. Original synthesized audio only.
- **Ghost:** green-on-black-style HUD and gentler lower-register sine cues.
- **Classic:** the original one-line HUD and original five core sound designs.
- **Boot:** a short link-up cue when an enabled, unmuted Cyber/Ghost shell starts.
- **ACK:** a successful command's duration at the next prompt.
- **RECOVERED:** a success immediately after a nonzero exit (other than Ctrl-C),
  with a rising cue. This does not prove you fixed the same command or bug.
- **JOB DONE:** a success after at least ten seconds, with a distinct completion
  cue. Recovery and quest cues take priority if several conditions apply.
- **OPS:** a per-shell operation count and a diamond indicator that changes on
  command completion. Cosmetic activity only, not XP, a speed target or mastery.

Cyber/Ghost use two compact lines when there is room, otherwise a single line.
They show your current directory's final name or active quest. Directory names
are displayed, not stored. Full-width Unicode text can occupy extra terminal
cells; shorten a goal if your terminal wraps it unexpectedly.

```bash
arena vibe cyber
arena vibe ghost
arena vibe classic
arena volume 60
```

Vibe and volume are saved. Volume is 0–100% of the already capped source level;
Windows/output-device volume still matters. Start low. `arena mute`, `arena hud off`
and `arena off` still work. There are no random jackpots, background animations,
screen shake, flashing, idle penalties or global keyboard monitoring.

Website-only Boot.dev tests remain invisible to this shell add-on. The manual
learning quests below are unchanged and optional. This version does not infer
test commands, automatically award learning XP, or assess your understanding.

### Upgrade from v1

Download the updated ZIP and extract it into a new directory. Run its `install.sh`
as your normal user, just as for the original installation. The old installed
code and `.bashrc` are backed up; XP and existing mute/HUD/enabled preferences are
retained. Cyber is the first-upgrade default. Open a **new Bash terminal**; do not
try to hot-reload an old session. Complete any active v1 quest before closing it.
The installer does not change Windows Terminal settings automatically.

## Install

Run inside Arch as your normal user. Complete your earlier Bash/Atuin setup first.

```bash
sudo pacman -Syu --needed libpulse python unzip
```

Extract `shell-arena.zip`, then from the extracted folder:

```bash
bash shell-arena/install.sh
```

Open a **new Bash terminal**, preserving the old one in case you want to compare.
Then start with low Windows volume:

```bash
arena soundtest
arena help
```

The installer backs up `.bashrc` and any previous add-on installation, adds one
source line at the end of `.bashrc`, and installs into
`~/.local/share/shell-arena`. It never modifies Neovim, Starship, Atuin, Readline
bindings, shell traps or Windows settings. Shell Arena uses Atuin's existing
`preexec_functions` and `precmd_functions` hook arrays. Atuin's current Bash
integration supplies bash-preexec; do not install a second copy on top of it.

## What it feels like

- Submit a nonempty shell command: a short launch tick.
- Command returns zero: a brighter completion cue.
- Command returns nonzero: a soft lower cue and `RETRY (code)`, not a punishment.
  Nonzero does not always indicate an error; `grep` with no match is one example.
- Ctrl-C: `CANCELLED`, no retry sound.
- Quest completion: +100 XP, small ascending fanfare.
- Every 300 XP: a level-up cue.
- HUD: level, next-level XP meter, command status/duration and quest stage.

This is **command-submit feedback, not a keyboard-wide sound driver**. Blank
Enter, individual keystrokes and Enter inside Neovim do not trigger the shell
hooks. A compound command line counts as one submission. Fast submissions can
coalesce/drop sound cues deliberately to avoid delayed sound queues. Audio is
best-effort; startup/WSLg latency may be perceptible on some systems.

The HUD redraws only at prompts; it does not animate or flash while you are
editing. It adds one or two lines to shell scrollback. `arena hud off` hides it.
Short terminal widths truncate the HUD. `NO_COLOR` disables its ANSI colouring.

## Learning quests

Use one small question per quest. The 0/3 -> 1/3 -> 2/3 -> 3/3 indicator is your
learning combo. There is no speed bonus and no lost XP when tests fail or when
you return after a break. Completed quests award XP; raw command volume does not.

```bash
arena quest "Understand Go error propagation"
arena focus 20
```

1. Before running the code, predict the result out loud or in your notes.

```bash
arena predict
```

2. Edit/test as usual in Neovim. Run your test through `arena check`:

```bash
arena check go test ./...
# or: arena check bootdev run
# or: arena check python -m pytest
# or: arena check uv run pytest
```

The check executes exactly the command and arguments you provide, without
`eval`, and preserves its exit status. It is not a sandbox: only run commands
you would normally trust. A successful exit marks the check, not mastery.
Use an actual test or meaningful exercise, not `true` to farm points.
Shell syntax such as pipelines is intentionally not re-parsed: run complex
checks through a script you wrote, for example `arena check bash ./check.sh`.

3. Hide your answer and explain *why* it worked. Then mark recall:

```bash
arena recall
arena finish
```

Prediction and recall are self-reported. The program cannot assess whether you
understood the material. Use external tests and your explanation as the real
feedback. Re-running `arena finish` cannot award the same quest twice. A failed
check clears the check/recall stages but keeps your prediction stage and all
earned XP. You can revise your prediction before retrying.

Quests and focus rounds belong to the current terminal session and are not
resumed after closing it. The focus timer is prompt-based: the break notice
appears at the first shell prompt after the countdown, not while inside Neovim
or a long-running command. It is not a scheduled background reminder.

Suggested first quests:

- Predict which error a Go function returns, then test it.
- Write a test that reproduces a bug, fix the bug, and explain the cause.
- Rebuild a short Boot.dev function without viewing your previous solution.
- Reproduce a Neovim text transformation using motions and inspect the diff.

## Controls

| Command | Effect |
| --- | --- |
| `arena status` | Refresh totals, including quests finished in another terminal |
| `arena mute` / `arena unmute` | Save sound preference |
| `arena hud off` / `arena hud on` | Save HUD preference |
| `arena vibe cyber` / `ghost` / `classic` | Save HUD and sound-pack selection |
| `arena volume 60` | Save volume, 0–100% of capped source |
| `arena off` / `arena on` | Save disabled/enabled preference |
| `arena abandon` | Clear unfinished quest, without losing earned XP |
| `arena focus 20` | Set a 20-minute, prompt-based focus round |
| `arena soundtest` | Play all ten cues in the selected pack and report audio problems |

Preferences are loaded when a new shell starts; an already-open second terminal
may retain its old settings until `arena status` or a fresh shell. Totals use
SQLite transactions, so concurrent quest awards do not lose updates.

## Make Windows Terminal match

Open Windows Terminal Settings -> Open JSON file. Add the **object** from
`windows-terminal-scheme.json` to your existing `schemes` array. Do not replace
the whole settings file. If you already have a scheme named `Shell Arena`, update
that one rather than adding a duplicate. The installed copy is at
`~/.local/share/shell-arena/windows-terminal-scheme.json`.
In your Arch profile, add or merge:

```json
"colorScheme": "Shell Arena",
"cursorShape": "filledBox",
"opacity": 100,
"font": {
  "face": "Cascadia Mono",
  "size": 12
}
```

Keep your existing Nerd Font if you already have one. Fonts must be installed
in Windows to affect Windows Terminal. The Arena HUD itself needs no Nerd Font.
Opaque background, crisp text and one consistent colour palette are the default;
no CRT blur, screen shake or flashing is enabled. The shell colour scheme may
not recolour Neovim when your own Neovim theme uses truecolour.

## Sound troubleshooting

WSLg provides the audio server; Arch's `libpulse` supplies `paplay`, the client.
Do not start another PulseAudio server just for this add-on.

```bash
command -v paplay
printf 'Pulse server: %s\n' "${PULSE_SERVER:-auto-detect}"
test -S /mnt/wslg/PulseServer && printf 'WSLg audio socket present\n'
arena soundtest
```

If WSLg is absent, the HUD/quests still work, but sound needs a functioning
PulseAudio-compatible server. In PowerShell, `wsl --update` updates WSL; a
restart may be necessary. Save your work before restarting any distro. Check
Windows' volume mixer and output device. Do not increase volume suddenly to
compensate for a failed test.

If you see `load Atuin before arena.bash`, ensure the prior dev-shell config is
sourced before the new Arena source line. In a fresh interactive Bash terminal:

```bash
declare -p preexec_functions precmd_functions
printf 'Bash: %s\n' "$BASH_VERSION"
```

`arena soundtest` is explicit and plays even when ordinary feedback is muted,
but still respects the saved volume (so volume 0 is silent).
The daemon has one playback process maximum, a short bounded queue, a timeout
for hung playback, and exits when its owning shell exits. No Windows process
is launched for every command.

## Privacy and undo

Arena does not send data over the network. It stores only numeric XP, quest
counts and preferences in `${XDG_STATE_HOME:-~/.local/state}/shell-arena/stats.sqlite3`.
It never stores command text, answers, paths, goal titles or recordings. Your
existing Bash/Atuin history behaviour is unchanged by Arena, and can still save
what you type. Do not type secrets into commands or quest names.

Disable with `arena off`. To detach entirely, remove only the line ending
`# shell-arena` from `.bashrc` and open a new terminal. The installed code,
backups and earned XP remain recoverable. No global uninstaller or destructive
cleanup command is needed.

## Verification and sources

Run the bundled offline checks from the extracted directory:

```bash
cd shell-arena
python3 -m unittest -v tests_audio tests_arena
```

Tests cover synthesized audio bounds, queue limits, state persistence/concurrent
awards, hook registration, mission rules, v1 migration, palettes, volume, passive
feedback and bounded HUD rendering. All 37 checks passed during v2 packaging.
A separate real interactive Bash session with bash-preexec also passed checks
for exit codes, the last argument, pipefail, quests and disabling the add-on.
Real WSLg audibility, your installed Atuin/Starship versions and your custom
Neovim setup still need the on-device check.

- [Atuin Bash integration](https://docs.atuin.sh/main/reference/init/)
- [bash-preexec hook API](https://github.com/rcaloras/bash-preexec)
- [Starship's Bash integration](https://github.com/starship/starship/blob/main/src/init/starship.bash)
- [WSLg audio architecture](https://github.com/microsoft/wslg)
- [Arch libpulse files](https://archlinux.org/packages/extra/x86_64/libpulse/files/)
- [Windows Terminal appearance](https://learn.microsoft.com/en-us/windows/terminal/customize-settings/profile-appearance)
