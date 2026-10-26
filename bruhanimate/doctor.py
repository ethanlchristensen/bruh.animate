"""Read-only setup diagnostics; never opens a Screen, device or subprocess."""

import importlib.util
import os
import platform
import sys
from importlib.metadata import PackageNotFoundError, version


def diagnose() -> dict[str, object]:
    """Report environment hints, not proof of terminal or hardware support."""
    packages: dict[str, str | None] = {}
    for name in (
        "bruhanimate",
        "bruhcolor",
        "Pillow",
        "imageio-ffmpeg",
        "PyAudioWPatch" if sys.platform == "win32" else "sounddevice",
    ):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    modules = {
        "raster_export": "PIL",
        "video_export": "imageio_ffmpeg",
        "audio": "pyaudiowpatch" if sys.platform == "win32" else "sounddevice",
    }
    available = {
        name: importlib.util.find_spec(module) is not None
        for name, module in modules.items()
    }
    tty = bool(sys.stdout.isatty())
    color_disabled = "ANSI_COLORS_DISABLED" in os.environ or bool(os.getenv("NO_COLOR"))
    term, colorterm = os.getenv("TERM", ""), os.getenv("COLORTERM", "")
    color_hint = (
        "disabled"
        if color_disabled
        else "truecolor hint"
        if colorterm.lower() in ("truecolor", "24bit")
        else "256-color hint"
        if "256color" in term
        else "unknown"
    )
    advice = []
    if not tty:
        advice.append(
            "stdout is redirected; run play/browse in an interactive terminal."
        )
    if not available["raster_export"] or not available["video_export"]:
        advice.append(
            'Install export tools: python -m pip install "bruhanimate[export]"'
        )
    if not available["audio"]:
        advice.append('Install audio tools: python -m pip install "bruhanimate[audio]"')
    if term == "dumb":
        advice.append("TERM=dumb: use an ANSI-capable terminal for animation.")
    return {
        "python": platform.python_version(),
        "platform": sys.platform,
        "stdout_is_terminal": tty,
        "encoding": getattr(sys.stdout, "encoding", None),
        "term": term,
        "colorterm": colorterm,
        "color": color_hint,
        "packages": packages,
        "available": available,
        "advice": advice,
        "limits": "Environment hints only; no terminal rendering, audio device or encoder was exercised.",
    }
