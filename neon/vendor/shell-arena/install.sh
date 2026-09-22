#!/usr/bin/env bash
# Installs only this add-on; no sudo, downloads or shell replacement.
set -euo pipefail
if (( EUID == 0 )); then
    printf 'Run this as your normal WSL user, not root/sudo.\n' >&2
    exit 1
fi
command -v python3 >/dev/null || { printf 'Install Arch python first.\n' >&2; exit 1; }
arena_src=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
arena_dest="$HOME/.local/share/shell-arena"
arena_stamp=$(date +%Y%m%d-%H%M%S-%N)
if [[ $arena_src == "$arena_dest" ]]; then
    printf 'Run install.sh from the extracted download, not the installed copy.\n' >&2
    exit 1
fi
for arena_file in arena.bash arena_audio.py arena_state.py README.md windows-terminal-scheme.json; do
    [[ -f "$arena_src/$arena_file" ]] || { printf 'Incomplete download: %s\n' "$arena_file" >&2; exit 1; }
done
if [[ -e $arena_dest || -L $arena_dest ]]; then
    mv -- "$arena_dest" "$arena_dest.backup-$arena_stamp"
    printf 'Previous add-on saved at %s\n' "$arena_dest.backup-$arena_stamp"
fi
install -d -m 700 "$arena_dest"
install -m 600 "$arena_src/arena.bash" "$arena_src/README.md" "$arena_src/windows-terminal-scheme.json" "$arena_dest/"
install -m 700 "$arena_src/arena_audio.py" "$arena_src/arena_state.py" "$arena_dest/"
python3 "$arena_dest/arena_audio.py" generate "$arena_dest/sounds"
arena_rc="$HOME/.bashrc"
if [[ -e $arena_rc || -L $arena_rc ]]; then
    cp -p -- "$arena_rc" "$arena_rc.arena-backup-$arena_stamp"
    printf 'Shell configuration backed up to %s\n' "$arena_rc.arena-backup-$arena_stamp"
fi
arena_source='[[ -r "$HOME/.local/share/shell-arena/arena.bash" ]] && source "$HOME/.local/share/shell-arena/arena.bash" # shell-arena'
if ! grep -Fqx -- "$arena_source" "$arena_rc" 2>/dev/null; then
    printf '\n%s\n' "$arena_source" >> "$arena_rc"
fi
printf '\nNeon Link v2 installed. Open a fresh Bash terminal, then run:\n  arena vibe cyber\n  arena soundtest\n  arena help\n\nExisting XP, mute and enabled preferences are preserved.\nAtuin must be loaded earlier in .bashrc. Neovim and Starship config are untouched.\n'
if ! command -v paplay >/dev/null; then
    printf '\nAudio client missing: sudo pacman -Syu --needed libpulse\n'
fi
