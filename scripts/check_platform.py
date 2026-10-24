"""Opt-in native Screen/resize and audio-capture checks with machine-readable results.

No device is opened without --terminal, --pty, or --audio. Reports never contain
audio samples. Use --pty on Linux/macOS CI; use --terminal in a real local console.
"""

import argparse
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def terminal_check(*, resize_pty: bool = False) -> dict:
    from bruhanimate import Buffer, FramePresenter, Screen

    screen = Screen.open()
    original = (screen.width, screen.height)
    try:
        presenter = FramePresenter(screen)
        frame = Buffer(screen.height, screen.width)
        frame.put_at(0, 0, "Screen ")
        frame.put_char(7, 0, "\x1b[38;5;117mX\x1b[0m")
        presenter.present(frame)
        if resize_pty:
            import fcntl
            import signal
            import struct
            import termios

            expected = (original[0] + 3, original[1] + 2)
            fcntl.ioctl(
                sys.stdout.fileno(),
                termios.TIOCSWINSZ,
                struct.pack("HHHH", expected[1], expected[0], 0, 0),
            )
            os.kill(os.getpid(), signal.SIGWINCH)
            if not screen.has_resized():
                raise RuntimeError("SIGWINCH did not mark a pending resize")
        else:
            expected = original
        if not screen.refresh_size():
            raise RuntimeError("Screen could not refresh its dimensions")
        refreshed = (screen.width, screen.height)
        if resize_pty and refreshed != expected:
            raise RuntimeError(f"Resize mismatch: expected {expected}, got {refreshed}")
        presenter.resize()
        frame = Buffer(screen.height, screen.width)
        frame.put_at(0, 0, "Refreshed")
        presenter.present(frame)
        return {
            "status": "passed",
            "backend": "Windows console"
            if sys.platform == "win32"
            else "Unix curses/PTY",
            "original_size": original,
            "refreshed_size": refreshed,
            "resize": "SIGWINCH and dimension change"
            if resize_pty
            else "refresh only; manual drag not tested",
            "limits": "Writes/flushes and cleanup only; no visual fidelity or keyboard claim",
        }
    finally:
        screen.close()


def pty_check() -> dict:
    if sys.platform == "win32":
        raise ValueError(
            "--pty is for Linux/macOS; use --terminal in a Windows console"
        )
    import fcntl
    import pty
    import struct
    import termios

    with TemporaryDirectory(prefix="bruhanimate-platform-") as directory:
        result = Path(directory) / "result.json"
        master, slave = pty.openpty()
        process = None
        try:
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 8, 24, 0, 0))
            environment = dict(os.environ, TERM="xterm-256color")
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--terminal",
                    "--resize-pty",
                    "--output",
                    str(result),
                ],
                stdin=slave,
                stdout=slave,
                stderr=slave,
                env=environment,
            )
            os.close(slave)
            slave = -1
            # Drain the PTY while the child runs; a full terminal pipe must not
            # turn a slow machine into a false timeout or deadlock.
            import select

            deadline = time.monotonic() + 20
            output = bytearray()
            while process.poll() is None:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Native PTY check exceeded 20 seconds")
                readable, _, _ = select.select([master], [], [], 0.1)
                if readable:
                    try:
                        chunk = os.read(master, 4096)
                    except OSError:
                        break
                    output.extend(chunk)
                    del output[:-8192]
            code = process.wait(timeout=2)
            if code or not result.exists():
                raise RuntimeError(
                    f"Native PTY check failed ({code}): {output.decode(errors='replace')}"
                )
            return json.loads(result.read_text(encoding="utf-8"))["terminal"]
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)
            if slave >= 0:
                os.close(slave)


def audio_check(seconds: float) -> dict:
    from bruhanimate import AudioEffect, Buffer

    effect = AudioEffect(Buffer(4, 12), " ")
    peak = 0.0
    try:
        effect.start()
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if effect._error:
                raise RuntimeError(effect._error)
            with effect._lock:
                peak = max(peak, float(abs(effect._audio_chunk).max()))
            time.sleep(0.05)
        if effect._thread is None or not effect._thread.is_alive():
            raise RuntimeError("Capture worker stopped before the check finished")
        return {
            "status": "passed" if peak > 0 else "inconclusive",
            "nonzero_signal": peak > 0,
            "limits": "Nonzero samples and clean shutdown only; silence cannot establish device support",
        }
    finally:
        effect.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--terminal", action="store_true")
    mode.add_argument("--pty", action="store_true")
    parser.add_argument(
        "--audio",
        action="store_true",
        help="Explicitly capture system audio briefly; no samples are saved",
    )
    parser.add_argument("--seconds", type=float, default=3)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--resize-pty", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not 0 < args.seconds <= 30:
        parser.error("seconds must be finite and in (0, 30]")
    if args.resize_pty and (not args.terminal or sys.platform == "win32"):
        parser.error("--resize-pty requires a Unix --terminal child")
    if args.terminal and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        parser.error(
            "--terminal requires interactive stdin/stdout; Unix automation can use --pty"
        )
    report = {
        "platform": platform.platform(),
        "python": sys.version,
        "terminal": {"status": "not_run"},
        "audio": {"status": "not_run"},
        "audio_dependency": bool(
            importlib.util.find_spec(
                "pyaudiowpatch" if sys.platform == "win32" else "sounddevice"
            )
        ),
    }
    for name, enabled, check in (
        (
            "terminal",
            args.terminal or args.pty,
            lambda: pty_check()
            if args.pty
            else terminal_check(resize_pty=args.resize_pty),
        ),
        ("audio", args.audio, lambda: audio_check(args.seconds)),
    ):
        if enabled:
            try:
                report[name] = check()
            except Exception as exc:
                report[name] = {"status": "failed", "error": str(exc)}
    payload = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return int(
        any(
            report[name]["status"] in ("failed", "inconclusive")
            for name in ("terminal", "audio")
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
