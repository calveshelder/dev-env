#!/usr/bin/env python3
"""Offline tests. These do not produce audible output or require PulseAudio."""

import array
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import wave

import arena_audio


class AudioTests(unittest.TestCase):
    def test_original_cues_are_short_quiet_and_deterministic(self):
        for event, duration in arena_audio.DURATIONS.items():
            with self.subTest(event=event):
                samples = arena_audio.cue_samples(event)
                self.assertEqual(samples, arena_audio.cue_samples(event))
                self.assertEqual(len(samples), round(duration * arena_audio.RATE))
                self.assertGreater(max(abs(value) for value in samples), 200)
                self.assertLessEqual(max(abs(value) for value in samples), round(0.12 * 32767))
                self.assertEqual(samples[0], 0)
                self.assertEqual(samples[-1], 0)
                self.assertLessEqual(duration, 0.5 if event == "level" else 0.4)

    def test_generate_wav_files(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "sounds"
            arena_audio.generate(target)
            self.assertEqual(len(list(target.rglob('*.wav'))), len(arena_audio.DURATIONS) * 3)
            for event in arena_audio.DURATIONS:
                with wave.open(str(target / f"{event}.wav"), "rb") as sound:
                    self.assertEqual(sound.getnchannels(), 1)
                    self.assertEqual(sound.getsampwidth(), 2)
                    self.assertEqual(sound.getframerate(), arena_audio.RATE)
                    samples = array.array("h", sound.readframes(sound.getnframes()))
                    self.assertTrue(samples)
                self.assertEqual((target / f"{event}.wav").stat().st_mode & 0o077, 0)

    def test_reject_regular_file_and_public_fifo(self):
        with tempfile.TemporaryDirectory() as temp:
            regular = Path(temp) / "regular"
            regular.touch(mode=0o600)
            with self.assertRaises(ValueError):
                arena_audio.open_private_fifo(regular)
            fifo = Path(temp) / "fifo"
            os.mkfifo(fifo, 0o600)
            os.chmod(fifo, 0o622)
            with self.assertRaises(ValueError):
                arena_audio.open_private_fifo(fifo)

    def test_accept_private_fifo_reject_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            fifo = Path(temp) / "fifo"
            os.mkfifo(fifo, 0o600)
            fd = arena_audio.open_private_fifo(fifo)
            os.close(fd)
            link = Path(temp) / "link"
            link.symlink_to(fifo)
            if hasattr(os, "O_NOFOLLOW"):
                with self.assertRaises(OSError):
                    arena_audio.open_private_fifo(link)

    def test_preserve_configured_audio_environment(self):
        with mock.patch.dict(os.environ, {"PULSE_SERVER": "unix:/custom/audio"}, clear=True):
            with mock.patch("arena_audio.shutil.which", return_value="/usr/bin/paplay"):
                backend, env = arena_audio.audio_backend()
            self.assertEqual(backend, "/usr/bin/paplay")
            self.assertEqual(env["PULSE_SERVER"], "unix:/custom/audio")

    def test_wslg_fallback_does_not_mutate_environment(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("arena_audio.Path.exists", return_value=True):
                with mock.patch("arena_audio.shutil.which", return_value=None):
                    backend, env = arena_audio.audio_backend()
            self.assertIsNone(backend)
            self.assertEqual(env["PULSE_SERVER"], "unix:/mnt/wslg/PulseServer")
            self.assertNotIn("PULSE_SERVER", os.environ)

    def test_daemon_drains_events_without_audio_and_quits(self):
        with tempfile.TemporaryDirectory() as temp:
            fifo = Path(temp) / "events"
            os.mkfifo(fifo, 0o600)
            fd = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
            process = subprocess.Popen(
                [sys.executable, str(Path(arena_audio.__file__).resolve()), "daemon",
                 "--fifo", str(fifo), "--sounds", temp, "--parent", str(os.getpid())],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env={**os.environ, "PATH": ""},
            )
            try:
                os.write(fd, b"launch\nok\nunknown\n$(touch dangerous)\n" + b"x" * 100 + b"\nquit\n")
                stdout, stderr = process.communicate(timeout=3)
                self.assertEqual(process.returncode, 0, stderr.decode())
                self.assertEqual(stdout, b"")
                self.assertEqual(stderr, b"")
            finally:
                os.close(fd)
                if process.poll() is None:
                    process.kill()
                    process.wait()

    def test_parent_identity_checks(self):
        state = arena_audio._parent_state(os.getpid())
        self.assertTrue(arena_audio.parent_alive(os.getpid(), state[1] if state else None))
        if state:
            self.assertFalse(arena_audio.parent_alive(os.getpid(), "impossible-start-time"))
        self.assertFalse(arena_audio.parent_alive(2_147_483_647, None))

    def test_cleanup_removes_only_matching_fifo_and_empty_private_run_dir(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / f"shell-arena.{os.getuid()}.test1234"
            directory.mkdir(mode=0o700)
            fifo = directory / "events"
            os.mkfifo(fifo, 0o600)
            fd = arena_audio.open_private_fifo(fifo)
            try:
                arena_audio.cleanup_private_fifo(fifo, os.fstat(fd))
                self.assertFalse(fifo.exists())
                self.assertFalse(directory.exists())
            finally:
                os.close(fd)

    def test_cleanup_preserves_replacement_fifo(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / f"shell-arena.{os.getuid()}.test1234"
            directory.mkdir(mode=0o700)
            fifo = directory / "events"
            os.mkfifo(fifo, 0o600)
            fd = arena_audio.open_private_fifo(fifo)
            try:
                fifo.unlink()
                os.mkfifo(fifo, 0o600)
                arena_audio.cleanup_private_fifo(fifo, os.fstat(fd))
                self.assertTrue(fifo.exists())
                self.assertTrue(directory.exists())
            finally:
                os.close(fd)

    def test_cleanup_keeps_unrelated_file_in_run_dir(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / f"shell-arena.{os.getuid()}.test1234"
            directory.mkdir(mode=0o700)
            fifo = directory / "events"
            os.mkfifo(fifo, 0o600)
            other = directory / "keep-me"
            other.touch()
            fd = arena_audio.open_private_fifo(fifo)
            try:
                arena_audio.cleanup_private_fifo(fifo, os.fstat(fd))
                self.assertFalse(fifo.exists())
                self.assertTrue(other.exists())
                self.assertTrue(directory.exists())
            finally:
                os.close(fd)

    def test_cleanup_ignores_non_arena_or_public_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            for name, mode in (("other-private-dir", 0o700),
                               (f"shell-arena.{os.getuid()}.test1234", 0o755)):
                with self.subTest(directory=name):
                    directory = Path(temp) / name
                    directory.mkdir(mode=mode)
                    os.chmod(directory, mode)
                    fifo = directory / "events"
                    os.mkfifo(fifo, 0o600)
                    fd = arena_audio.open_private_fifo(fifo)
                    try:
                        arena_audio.cleanup_private_fifo(fifo, os.fstat(fd))
                        self.assertTrue(fifo.exists())
                        self.assertTrue(directory.exists())
                    finally:
                        os.close(fd)

    def test_daemon_removes_private_run_dir_when_parent_is_gone(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / f"shell-arena.{os.getuid()}.test1234"
            directory.mkdir(mode=0o700)
            fifo = directory / "events"
            os.mkfifo(fifo, 0o600)
            result = subprocess.run(
                [sys.executable, str(Path(arena_audio.__file__).resolve()), "daemon",
                 "--fifo", str(fifo), "--sounds", temp, "--parent", "2147483647"],
                stdin=subprocess.DEVNULL, capture_output=True, timeout=3,
                env={**os.environ, "PATH": ""},
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertFalse(directory.exists())

    def test_daemon_stops_when_fifo_is_unlinked_or_replaced(self):
        for replace in (False, True):
            with self.subTest(replace=replace), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp) / f"shell-arena.{os.getuid()}.test1234"
                directory.mkdir(mode=0o700)
                fifo = directory / "events"
                os.mkfifo(fifo, 0o600)

                def unlink_during_poll(*_args):
                    fifo.unlink()
                    if replace:
                        os.mkfifo(fifo, 0o600)
                    return [], [], []

                with mock.patch("arena_audio.signal.signal"), \
                     mock.patch("arena_audio.audio_backend", return_value=(None, {})), \
                     mock.patch("arena_audio.select.select", side_effect=unlink_during_poll) as select_call:
                    result = arena_audio.daemon(fifo, Path(temp), os.getpid())
                self.assertEqual(result, 0)
                self.assertEqual(select_call.call_count, 1)
                self.assertEqual(fifo.exists(), replace)

    def test_player_is_bounded_and_stale_events_are_dropped(self):
        clock = [100.0]
        reads = [b"launch\n", b"level\n", b"\n", b"\n", b"\n", b"level\nlaunch\nok\n"]
        players = []
        loops = [0]

        class FakePlayer:
            def __init__(inner, command, **_kwargs):
                self.assertFalse(any(player.poll() is None for player in players))
                self.assertIn('--volume=39322', command)
                inner.event = Path(command[-1]).stem
                inner.started = clock[0]
                inner.stopped = False
                players.append(inner)

            def poll(inner):
                if inner.stopped or clock[0] - inner.started >= arena_audio.DURATIONS[inner.event]:
                    return 0
                return None

            def terminate(inner):
                inner.stopped = True

            kill = terminate

            def wait(inner, timeout):
                return 0

        def alive(*_args):
            loops[0] += 1
            return loops[0] < 35

        def ready(fds, _write, _except, timeout):
            clock[0] += 0.025
            return (fds if reads else []), [], []

        with tempfile.TemporaryDirectory() as temp:
            fifo = Path(temp) / "events"
            os.mkfifo(fifo, 0o600)
            with mock.patch("arena_audio.audio_backend", return_value=("/fake/paplay", {})), \
                 mock.patch("arena_audio.signal.signal"), \
                 mock.patch("arena_audio.parent_alive", side_effect=alive), \
                 mock.patch("arena_audio.time.monotonic", side_effect=lambda: clock[0]), \
                 mock.patch("arena_audio.select.select", side_effect=ready), \
                 mock.patch("arena_audio.os.read", side_effect=lambda *_args: reads.pop(0)), \
                 mock.patch("arena_audio.Path.is_file", return_value=True), \
                 mock.patch("arena_audio.subprocess.Popen", side_effect=FakePlayer):
                result = arena_audio.daemon(fifo, Path(temp), os.getpid())
            self.assertEqual(result, 0)
            self.assertEqual([player.event for player in players], ["launch", "level"])

    def test_all_profiles_are_bounded_and_distinct(self):
        for event, duration in arena_audio.DURATIONS.items():
            variants = []
            for profile in arena_audio.PROFILES:
                samples = arena_audio.cue_samples(event, profile)
                self.assertEqual(len(samples), round(duration * arena_audio.RATE))
                self.assertEqual(samples[0], 0)
                self.assertEqual(samples[-1], 0)
                self.assertLessEqual(max(map(abs, samples)), round(arena_audio.MAX_PEAK * 32767))
                variants.append(samples.tobytes())
            self.assertEqual(len(set(variants)), 3, event)
        self.assertNotEqual(arena_audio.cue_samples('launch', 'cyber'), arena_audio.cue_samples('launch2', 'cyber'))
        self.assertNotEqual(arena_audio.cue_samples('ok', 'cyber'), arena_audio.cue_samples('ok2', 'cyber'))

    def test_soundtest_uses_selected_pack_and_volume(self):
        result = subprocess.CompletedProcess([], 0, '', '')
        with mock.patch('arena_audio.audio_backend', return_value=('/fake/paplay', {})), \
             mock.patch('arena_audio.Path.is_file', return_value=True), \
             mock.patch('arena_audio.time.sleep'), \
             mock.patch('arena_audio.subprocess.run', return_value=result) as run:
            self.assertEqual(arena_audio.test_audio(Path('/sounds'), 'ghost', 25), 0)
        self.assertEqual(run.call_count, 10)
        for call in run.call_args_list:
            self.assertEqual(call.args[0][1], '--volume=16384')
            self.assertEqual(Path(call.args[0][-1]).parent, Path('/sounds/ghost'))

    def test_cli_rejects_unsafe_profile_and_volume(self):
        for args in (['--profile', '../other'], ['--volume', '101'], ['--volume', '-1']):
            result = subprocess.run([sys.executable, str(Path(arena_audio.__file__)),
                                     'test', '--sounds', '/unused', *args], capture_output=True)
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
