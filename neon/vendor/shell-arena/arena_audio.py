#!/usr/bin/env python3
"""Original, quiet shell cues and a bounded local PulseAudio event player.

The daemon receives only fixed event names; it never receives command text.
It uses one paplay process at most, not a Windows process for every keypress.
"""

from __future__ import annotations

import argparse
import array
import math
import os
from pathlib import Path
import random
import select
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import wave


RATE = 24_000
DURATIONS = {"launch": 0.055, "ok": 0.10, "error": 0.15, "level": 0.36, "quest": 0.28}
PRIORITY = {"launch": 1, "ok": 2, "error": 3, "quest": 4, "level": 5}
DURATIONS.update(launch2=0.055, ok2=0.10, boot=0.24, recover=0.20, complete=0.24)
PRIORITY.update(launch2=1, ok2=2, boot=3, recover=3, complete=3)
PROFILES = ("classic", "cyber", "ghost")
MAX_PEAK = 0.12
QUEUE_TTL = 0.25


def _tone(t: float, start: float, duration: float, first: float, last: float, gain: float) -> float:
    local = t - start
    if local < 0 or local >= duration:
        return 0.0
    phase = 2 * math.pi * (first * local + (last - first) * local * local / (2 * duration))
    envelope = min(1.0, local / 0.002) * (1.0 - local / duration) ** 2
    return gain * envelope * (math.sin(phase) + 0.13 * math.sin(2 * phase))


def cue_samples(event: str, profile: str = "classic") -> array.array:
    """Mono signed 16-bit PCM: short mechanical chirps, not third-party samples."""
    duration = DURATIONS[event]
    rng = random.Random(event)
    samples = array.array("h")
    for frame in range(round(duration * RATE)):
        t = frame / RATE
        value = 0.0
        if event in ("launch", "launch2"):
            value = _tone(t, 0, 0.05, 1500, 680, 0.072)
            value += rng.uniform(-1, 1) * 0.020 * math.exp(-t * 850) * min(1, t / 0.001)
        elif event in ("ok", "ok2"):
            value = _tone(t, 0, 0.058, 760, 1100, 0.065)
            value += _tone(t, 0.035, 0.063, 1320, 1500, 0.065)
        elif event == "error":
            value = _tone(t, 0, 0.085, 380, 285, 0.060)
            value += _tone(t, 0.065, 0.080, 270, 215, 0.050)
        elif event == "quest":
            for start, pitch in ((0, 620), (0.070, 830), (0.14, 1245)):
                value += _tone(t, start, 0.13, pitch, pitch * 1.02, 0.062)
        elif event == "level":
            for start, pitch in ((0, 660), (0.065, 880), (0.13, 1100), (0.195, 1320)):
                value += _tone(t, start, 0.16, pitch, pitch * 1.015, 0.062)
        elif event == "boot":
            for start, pitch in ((0, 240), (0.05, 480), (0.11, 960)):
                value += _tone(t, start, 0.12, pitch, pitch * 1.3, 0.055)
        elif event == "recover":
            value = _tone(t, 0, 0.11, 260, 620, 0.055)
            value += _tone(t, 0.08, 0.11, 1040, 1320, 0.060)
        elif event == "complete":
            for start, pitch in ((0, 520), (0.05, 780), (0.10, 1040)):
                value += _tone(t, start, 0.13, pitch, pitch, 0.060)
        if profile == "cyber":
            # A restrained low transient and short metallic data chirps.
            if event in ("launch", "launch2"):
                pitch = 1760 if event == "launch" else 1480
                value = _tone(t, 0, 0.048, 190, 90, 0.040)
                value += _tone(t, 0, 0.025, pitch, pitch * 0.65, 0.052)
                value += _tone(t, 0.016, 0.026, pitch * 1.5, pitch, 0.028)
            elif event in ("ok", "ok2"):
                pitch = 980 if event == "ok" else 1100
                value = _tone(t, 0, 0.045, pitch, pitch, 0.065)
                value += _tone(t, 0.027, 0.065, pitch * 1.6, pitch * 1.62, 0.060)
            else:
                value += _tone(t, 0, min(duration, 0.09), 160, 90, 0.020)
        elif profile == "ghost":
            # Softer, lower-register counterpart; no noise transient.
            pitch = {"launch": 600, "launch2": 560, "ok": 880, "ok2": 820,
                     "error": 280, "boot": 440, "recover": 660, "complete": 740,
                     "quest": 880, "level": 1040}[event]
            value = _tone(t, 0, duration * 0.95, pitch, pitch * 1.05, 0.038)
        value = max(-MAX_PEAK, min(MAX_PEAK, value))
        samples.append(round(value * 32767))
    return samples


def generate(directory: Path, profile: str = "classic") -> None:
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    for event in DURATIONS:
        samples = cue_samples(event, profile)
        if sys.byteorder != "little":
            samples.byteswap()
        fd, temp_name = tempfile.mkstemp(prefix=f".{event}-", suffix=".wav", dir=directory)
        try:
            with os.fdopen(fd, "wb") as output:
                with wave.open(output, "wb") as sound:
                    sound.setnchannels(1)
                    sound.setsampwidth(2)
                    sound.setframerate(RATE)
                    sound.writeframes(samples.tobytes())
            os.replace(temp_name, directory / f"{event}.wav")
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
    if profile == "classic":
        for extra in ("cyber", "ghost"):
            generate(directory / extra, extra)


def audio_backend() -> tuple[str | None, dict[str, str]]:
    env = os.environ.copy()
    if sys.platform == 'darwin':
        return shutil.which('afplay'), env
    if not env.get("PULSE_SERVER") and Path("/mnt/wslg/PulseServer").exists():
        env["PULSE_SERVER"] = "unix:/mnt/wslg/PulseServer"
    return shutil.which("paplay"), env


def player_command(backend: str, sound: Path, volume: int) -> list[str]:
    if Path(backend).name == 'afplay':
        return [backend, '-v', str(volume / 100), str(sound)]
    return [backend, f'--volume={round(65536 * volume / 100)}', str(sound)]


def open_private_fifo(path: Path) -> int:
    fd = os.open(path, os.O_RDWR | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
    info = os.fstat(fd)
    if not stat.S_ISFIFO(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        os.close(fd)
        raise ValueError("Audio event path must be a FIFO owned by you with mode 600 or stricter.")
    return fd


def cleanup_private_fifo(path: Path, opened_info: os.stat_result) -> None:
    """Remove only this opened FIFO and its empty, private Shell Arena run dir."""
    directory = path.parent
    if path.name != "events" or not directory.name.startswith(f"shell-arena.{os.getuid()}."):
        return
    directory_fd = None
    ancestor_fd = None
    try:
        directory_fd = os.open(
            directory, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
        )
        directory_info = os.fstat(directory_fd)
        if directory_info.st_uid != os.getuid() or directory_info.st_mode & 0o077:
            return
        current = os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            not stat.S_ISFIFO(current.st_mode)
            or current.st_uid != os.getuid()
            or current.st_mode & 0o077
            or (current.st_dev, current.st_ino) != (opened_info.st_dev, opened_info.st_ino)
        ):
            return
        os.unlink(path.name, dir_fd=directory_fd)
        # Match the directory again before removing it. rmdir cannot remove content.
        ancestor_fd = os.open(directory.parent, os.O_RDONLY | os.O_DIRECTORY)
        current_directory = os.stat(directory.name, dir_fd=ancestor_fd, follow_symlinks=False)
        if (current_directory.st_dev, current_directory.st_ino) == (
            directory_info.st_dev, directory_info.st_ino,
        ):
            os.rmdir(directory.name, dir_fd=ancestor_fd)
    except OSError:
        # Explicit shell cleanup may already have run; unexpected files are retained.
        pass
    finally:
        if ancestor_fd is not None:
            os.close(ancestor_fd)
        if directory_fd is not None:
            os.close(directory_fd)


def fifo_still_current(path: Path, opened_info: os.stat_result) -> bool:
    """A removed/replaced FIFO is also a stop signal, even if its queue was full."""
    try:
        current = path.lstat()
    except OSError:
        return False
    return stat.S_ISFIFO(current.st_mode) and (
        current.st_dev, current.st_ino,
    ) == (opened_info.st_dev, opened_info.st_ino)


def _parent_state(pid: int) -> tuple[str, str] | None:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return fields[0], fields[19]
    except (OSError, IndexError):
        return None


def parent_alive(pid: int, start_time: str | None) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    current = _parent_state(pid)
    if current is not None:
        if current[0] == "Z" or (start_time is not None and current[1] != start_time):
            return False
    return True


def _stop_player(player: subprocess.Popen | None) -> None:
    if player is None or player.poll() is not None:
        return
    player.terminate()
    try:
        player.wait(timeout=0.2)
    except subprocess.TimeoutExpired:
        player.kill()
        player.wait(timeout=0.2)


def daemon(fifo: Path, sounds: Path, parent: int, profile: str = "classic", volume: int = 60) -> int:
    if profile not in PROFILES or not 0 <= volume <= 100:
        raise ValueError("Invalid sound profile or volume")
    if profile != "classic":
        sounds = sounds / profile
    fd = open_private_fifo(fifo)
    opened_info = os.fstat(fd)
    backend, env = audio_backend()
    parent_state = _parent_state(parent)
    parent_start = parent_state[1] if parent_state else None
    stopping = False
    player: subprocess.Popen | None = None
    playing_event = ""
    playing_since = 0.0
    pending: tuple[str, float] | None = None
    retry_after = 0.0
    last_launch = 0.0
    carry = b""
    discarding_line = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        while not stopping and parent_alive(parent, parent_start) and fifo_still_current(fifo, opened_info):
            now = time.monotonic()
            if player is not None:
                result = player.poll()
                if result is not None:
                    if result not in (0, -signal.SIGTERM):
                        retry_after = now + 10
                    player = None
                    playing_event = ""
                elif now - playing_since > 2:
                    _stop_player(player)
                    player = None
                    playing_event = ""
                    retry_after = now + 10

            ready, _, _ = select.select([fd], [], [], 0.025 if player or pending else 0.20)
            if ready:
                # Bounded reads prevent event floods from starving shutdown and cleanup.
                chunk = os.read(fd, 4096)
                if discarding_line:
                    _, separator, chunk = chunk.partition(b"\n")
                    if not separator:
                        chunk = b""
                    else:
                        discarding_line = False
                data = carry + chunk
                lines = data.split(b"\n")
                carry = lines.pop()
                if len(carry) > 32:
                    carry = b""
                    discarding_line = True
                for line in lines:
                    if line == b"quit":
                        stopping = True
                        break
                    if len(line) > 16:
                        continue
                    event = line.decode("ascii", errors="replace")
                    if event not in PRIORITY:
                        continue
                    now = time.monotonic()
                    if pending is not None and now - pending[1] > QUEUE_TTL:
                        pending = None
                    if playing_event and PRIORITY[event] < PRIORITY[playing_event]:
                        continue
                    if pending is None or PRIORITY[event] >= PRIORITY[pending[0]]:
                        pending = (event, now)

            if stopping:
                break
            now = time.monotonic()
            if pending is not None and now - pending[1] > QUEUE_TTL:
                pending = None
            if player is None and pending is not None:
                event, _ = pending
                pending = None
                if backend is None or now < retry_after or volume == 0:
                    continue
                if event in ("launch", "launch2") and now - last_launch < 0.045:
                    continue
                sound = sounds / f"{event}.wav"
                if not sound.is_file():
                    continue
                try:
                    player = subprocess.Popen(
                        player_command(backend, sound, volume), env=env, stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
                    )
                except OSError:
                    retry_after = now + 10
                    continue
                playing_event = event
                playing_since = now
                if event in ("launch", "launch2"):
                    last_launch = now
    finally:
        try:
            _stop_player(player)
        finally:
            cleanup_private_fifo(fifo, opened_info)
            os.close(fd)
    return 0


def test_audio(sounds: Path, profile: str = "classic", volume: int = 60) -> int:
    if profile != "classic":
        sounds = sounds / profile
    backend, env = audio_backend()
    if backend is None:
        print("Audio player missing: macOS uses afplay; Linux/WSL uses paplay (Arch package libpulse).", file=sys.stderr)
        return 1
    for event in ("boot", "launch", "launch2", "ok", "ok2", "error", "recover", "complete", "quest", "level"):
        sound = sounds / f"{event}.wav"
        if not sound.is_file():
            print(f"Missing {sound}. Run: arena_audio.py generate SOUNDS_DIRECTORY", file=sys.stderr)
            return 1
        try:
            result = subprocess.run(
                player_command(backend, sound, volume), env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=4,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            print(f"Could not play the {event} cue: {error}", file=sys.stderr)
            return 1
        if result.returncode:
            detail = result.stderr.strip()[:500]
            print(f"Audio unavailable: {detail or 'paplay failed'}", file=sys.stderr)
            print(
                "On WSL, check WSLg audio and Windows volume; update WSL from PowerShell "
                "with 'wsl --update' if needed. Shell Arena stays usable without sound.",
                file=sys.stderr,
            )
            return 1
        time.sleep(0.08)
    print(f"Played {profile} cues at {volume}% of the capped source volume.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("generate", help="generate three original sound packs")
    make.add_argument("outdir", type=Path)
    play = commands.add_parser("daemon", help="read private FIFO events; quiet if audio is unavailable")
    play.add_argument("--fifo", required=True, type=Path)
    play.add_argument("--sounds", required=True, type=Path)
    play.add_argument("--parent", type=int, default=os.getppid())
    check = commands.add_parser("test", help="play every cue and report audio failures")
    check.add_argument("--sounds", required=True, type=Path)
    for audio_parser in (play, check):
        audio_parser.add_argument("--profile", choices=PROFILES, default="classic")
        audio_parser.add_argument("--volume", type=int, choices=range(101), default=60, metavar="0-100")
    args = parser.parse_args()
    try:
        if args.command == "generate":
            generate(args.outdir)
            print(f"Generated {len(DURATIONS)} cues in each of three sound packs in {args.outdir}")
            return 0
        if args.command == "test":
            return test_audio(args.sounds, args.profile, args.volume)
        if args.parent <= 0:
            parser.error("--parent must be a positive process ID")
        return daemon(args.fifo, args.sounds, args.parent, args.profile, args.volume)
    except (OSError, ValueError) as error:
        print(f"Shell Arena audio: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
