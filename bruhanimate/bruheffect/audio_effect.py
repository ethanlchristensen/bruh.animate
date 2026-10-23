"""
Copyright 2023 Ethan Christensen

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import math
import random
import sys
import threading
from collections import deque
from contextlib import ExitStack
from importlib import import_module
from importlib.util import find_spec

import numpy as np
from bruhcolor import bruhcolored as bc

from ..bruhutil.bruhffer import Buffer
from .base_effect import BaseEffect
from .settings import AudioSettings

_SAMPLE_RATE = 44100
_CHUNK = 1024
_RAIN_CHARS = "01アウイエオカキクケコサシスセソタチツテト"
_FW_CHARS = "*+.·o°"
_N_STARS = 150
_N_BALLS = 12
_TRAIL_LEN = 7
_GRADIENT_CHARS = " .:-=+*#%@"

# Modes that manage their own buffer state — skip the per-frame clear
_STATEFUL_MODES = {"spectrum", "rain", "waveform"}


def _make_bolt(width: int, height: int) -> list[tuple[int, int]]:
    """Generate a branching lightning bolt path from a random top position downward."""
    path: list[tuple[int, int]] = []
    bx = random.randint(width // 6, 5 * width // 6)
    for y in range(height):
        bx = max(0, min(width - 1, bx + random.randint(-2, 2)))
        path.append((bx, y))
        if random.random() < 0.12:
            brx, bry = bx, y
            direction = random.choice([-1, 1])
            for _ in range(random.randint(3, 10)):
                brx = max(0, min(width - 1, brx + direction + random.randint(-1, 1)))
                bry += 1
                if bry >= height:
                    break
                path.append((brx, bry))
    return path


# Optional dependency detection
_sd = None
_pa_mod = None
_HAS_SD = find_spec("sounddevice") is not None
_HAS_PAW = sys.platform == "win32" and find_spec("pyaudiowpatch") is not None


def _find_monitor_device():
    """Return a sounddevice input device index for a PulseAudio/PipeWire monitor, or None."""
    if not _HAS_SD:
        return None
    for i, dev in enumerate(_sd.query_devices()):
        name = dev.get("name", "").lower()
        if "monitor" in name and dev.get("max_input_channels", 0) > 0:
            return i
    return None


class AudioEffect(BaseEffect):
    """
    Visualizes system audio output as terminal animations.

    Modes:

    - ``"bars"``     — vertical EQ bars
    - ``"mirror"``   — EQ bars mirrored from the vertical center outward
    - ``"waveform"`` — oscilloscope: filled columns from center to sample amplitude
    - ``"spectrum"`` — scrolling spectrogram; frequency on Y, time on X
    - ``"radial"``   — circular pulse from center; each ring driven by a frequency band
    - ``"rain"``     — audio-driven falling character rain; frequency energy sets density
    - ``"tunnel"``       — rectangular frames that zoom toward the viewer; speed tracks energy
    - ``"ripple"``       — beat-triggered elliptical rings that expand from center
    - ``"vortex"``       — rotating Archimedean spiral arms; rotation speed tracks energy
    - ``"wave"``         — multi-frequency sine interference; each band drives its own wave
    - ``"starfield"``    — perspective star-zoom; stars accelerate with audio energy
    - ``"fireworks"``    — particle bursts that explode and fall under gravity
    - ``"interference"`` — two-source wave interference pattern; geometry shifts with audio
    - ``"bounce"``       — balls with glowing trails that speed up with their frequency band
    - ``"lightning"``    — branching electric bolts that strike on energy spikes
    - ``"aurora"``       — flowing curtains of color that undulate with frequency bands
    - ``"orbit"``        — sparse particles scattered at orbital radii; fills the screen with scattered dots
    - ``"scope"``        — raw audio oscilloscope; shows the actual waveform sample-by-sample
    - ``"grid"``         — screen-filling frequency grid; each cell glows with its band's energy
    - ``"helix"``        — scrolling double helix with rungs; pitch and rung density track audio
    - ``"lissajous"``    — Lissajous figure whose frequency ratios are driven by bass and treble bands
    - ``"sunburst"``     — rotating radial spokes from center; each spoke's length driven by its band
    - ``"mandala"``      — 8-fold symmetric petal patterns that bloom and rotate with audio
    - ``"comet"``        — comets streak from screen edges with fading trails; speed tracks energy
    - ``"weave"``        — interlaced horizontal and vertical sine waves that cross each other

    **Windows** requires ``PyAudioWPatch`` for WASAPI loopback::

        pip install bruhanimate[audio]

    **Linux** requires ``sounddevice`` and a PulseAudio/PipeWire monitor source::

        pip install bruhanimate[audio]
    """

    def __init__(self, buffer: Buffer, background: str, settings: AudioSettings = None):
        """
        Initialize the audio effect.

        Args:
            buffer (Buffer): Effect buffer to push updates to.
            background (str): Character or string to use for the background.
            settings (AudioSettings, optional): Configuration for the audio effect.
        """
        super().__init__(buffer, background)
        s = settings or AudioSettings()

        self.mode = s.mode
        self.bar_char = s.bar_char
        self.smoothing = s.smoothing
        self.color = s.color
        self.sensitivity = s.sensitivity
        self.compact = s.compact

        self._height = buffer.height()
        self._width = buffer.width()
        self._num_bars = s.num_bars if s.num_bars > 0 else max(1, self._width // 2)

        self._bars = np.zeros(self._num_bars)
        self._wave_history = np.zeros(self._width)
        self._lock = threading.Lock()
        self._running = False
        self._stop_event = threading.Event()
        self._thread = None
        self._audio_chunk = np.zeros(_CHUNK, dtype=np.float32)
        self._error: str = None

        # tunnel state
        self._tunnel_rings: list[dict] = []
        self._tunnel_frame: int = 0

        # ripple state
        self._ripples: list[dict] = []
        self._beat_cooldown: int = 0

        # vortex state
        self._vortex_angle: float = 0.0

        # wave state
        self._sine_phases: np.ndarray = np.zeros(8)

        # starfield state — columns: norm-x, norm-y, z-depth
        rng = np.random.default_rng()
        self._stars: np.ndarray = np.column_stack(
            [
                rng.uniform(-1.0, 1.0, _N_STARS),
                rng.uniform(-1.0, 1.0, _N_STARS),
                rng.uniform(0.05, 1.0, _N_STARS),
            ]
        )

        # fireworks state
        self._fw_particles: list[dict] = []
        self._fw_cooldown: int = 0

        # interference state
        self._intf_phase: float = 0.0
        # precompute pixel grids (recomputed lazily if screen size changes)
        self._intf_X: np.ndarray | None = None
        self._intf_Y: np.ndarray | None = None

        # lightning state
        self._lightning_bolts: list[tuple[list, int]] = []  # (path, frames_remaining)
        self._lightning_cooldown: int = 0

        # aurora state
        self._aurora_phase: float = 0.0

        # orbit state — one angle per orbit ring (dynamic up to 128)
        self._orbit_angles: np.ndarray = np.zeros(128)
        self._orbit_mags: np.ndarray = np.zeros(128)

        # helix state
        self._helix_phase: float = 0.0

        # lissajous state
        self._liss_t: float = 0.0

        # sunburst state
        self._sunburst_angle: float = 0.0

        # mandala state
        self._mandala_angle: float = 0.0

        # comet state
        self._comets: list[dict] = []
        self._comet_cooldown: int = 0

        # weave state
        self._weave_phase: float = 0.0

        # bounce state
        self._balls: list[dict] = [
            {
                "x": random.uniform(0, self._width),
                "y": random.uniform(0, self._height),
                "vx": random.choice([-1, 1]) * random.uniform(0.4, 1.2),
                "vy": random.choice([-1, 1]) * random.uniform(0.25, 0.7),
                "band": i,
                "trail": deque(maxlen=_TRAIL_LEN),
            }
            for i in range(_N_BALLS)
        ]

    def start(self):
        """Start capture explicitly; constructing/configuring an effect is inert."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._error = None
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        try:
            self._thread.start()
        except BaseException:
            self._running = False
            self._stop_event.set()
            self._thread = None
            raise
        super().start()

    # ------------------------------------------------------------------
    # Runtime setters
    # ------------------------------------------------------------------

    def set_mode(self, mode: str):
        """Switch visualization mode. Clears the buffer when leaving a stateful mode."""
        if self.mode in _STATEFUL_MODES and mode not in _STATEFUL_MODES:
            self.buffer.clear_buffer(val=self.background)
        self.mode = mode

    def set_sensitivity(self, sensitivity: float):
        """Adjust the amplitude sensitivity multiplier."""
        self.sensitivity = sensitivity

    def set_smoothing(self, smoothing: float):
        """Set temporal smoothing (0 = none, close to 1 = very smooth)."""
        self.smoothing = smoothing

    def set_color(self, color: bool):
        """Enable or disable colorized output."""
        self.color = color

    def set_bar_char(self, bar_char: str):
        """Set the character used to draw bars and fills."""
        self.bar_char = bar_char

    def set_compact(self, compact: bool):
        """Remove the gap column between bars when True."""
        self.compact = compact

    # ------------------------------------------------------------------
    # Audio capture
    # ------------------------------------------------------------------

    def _capture_loop(self):
        if sys.platform == "win32":
            self._capture_windows()
        else:
            self._capture_linux()

    def _capture_windows(self):
        global _pa_mod
        if not _HAS_PAW:
            self._error = (
                "PyAudioWPatch not installed. Run: pip install bruhanimate[audio]"
            )
            return
        try:
            if _pa_mod is None:
                _pa_mod = import_module("pyaudiowpatch")
            with ExitStack() as cleanup:
                self._capture_windows_stream(cleanup)
        except Exception as exc:
            self._error = f"Audio error: {exc}"

    def _capture_windows_stream(self, cleanup):
        pa = _pa_mod.PyAudio()
        cleanup.callback(pa.terminate)
        wasapi = pa.get_host_api_info_by_type(_pa_mod.paWASAPI)
        speakers = pa.get_device_info_by_index(wasapi["defaultOutputDevice"])

        # Loopback device names are "<name> [Loopback]" — use substring match.
        loopback = None
        if hasattr(pa, "get_loopback_device_info_generator"):
            for dev in pa.get_loopback_device_info_generator():
                if speakers["name"] in dev["name"]:
                    loopback = dev
                    break

        if loopback is None:
            for i in range(pa.get_device_count()):
                dev = pa.get_device_info_by_index(i)
                if (
                    dev.get("isLoopbackDevice", False)
                    and speakers["name"] in dev["name"]
                ):
                    loopback = dev
                    break

        if loopback is None:
            self._error = "No WASAPI loopback device found. Is PyAudioWPatch installed?"
            return

        channels = max(1, loopback.get("maxInputChannels", 2))
        rate = int(loopback.get("defaultSampleRate", _SAMPLE_RATE))

        def _cb(in_data, frame_count, time_info, status):
            audio = np.frombuffer(in_data, dtype=np.float32)
            if channels > 1:
                audio = audio[::channels]
            chunk = np.zeros(_CHUNK, dtype=np.float32)
            n = min(len(audio), _CHUNK)
            chunk[:n] = audio[:n]
            with self._lock:
                self._audio_chunk = chunk
            return (None, _pa_mod.paContinue)

        stream = pa.open(
            format=_pa_mod.paFloat32,
            channels=channels,
            rate=rate,
            input=True,
            frames_per_buffer=_CHUNK,
            input_device_index=loopback["index"],
            stream_callback=_cb,
        )
        cleanup.callback(stream.close)
        cleanup.callback(stream.stop_stream)
        stream.start_stream()
        while self._running:
            self._stop_event.wait(0.05)

    def _capture_linux(self):
        global _sd
        if not _HAS_SD:
            self._error = (
                "sounddevice not installed. Run: pip install bruhanimate[audio]"
            )
            return

        def _cb(indata, frames, time, status):
            audio = indata[:, 0].copy()
            chunk = np.zeros(_CHUNK, dtype=np.float32)
            n = min(len(audio), _CHUNK)
            chunk[:n] = audio[:n]
            with self._lock:
                self._audio_chunk = chunk

        try:
            if _sd is None:
                _sd = import_module("sounddevice")
            device = _find_monitor_device()
            kwargs = {"device": device} if device is not None else {}
            stream = _sd.InputStream(
                samplerate=_SAMPLE_RATE,
                channels=1,
                callback=_cb,
                blocksize=_CHUNK,
                **kwargs,
            )
            with ExitStack() as cleanup:
                cleanup.callback(stream.close)
                cleanup.callback(stream.stop)
                stream.start()
                while self._running:
                    self._stop_event.wait(0.05)
        except Exception as exc:
            self._error = f"Audio error: {exc}"

    # ------------------------------------------------------------------
    # DSP helpers
    # ------------------------------------------------------------------

    def _fft_bars(self, audio: np.ndarray) -> np.ndarray:
        """Return smoothed, normalised EQ bar heights (0–1)."""
        window = np.hanning(len(audio))
        fft = np.abs(np.fft.rfft(audio * window))
        freqs = np.linspace(0, _SAMPLE_RATE / 2, len(fft))
        edges = np.logspace(np.log10(20), np.log10(20000), self._num_bars + 1)

        raw = np.zeros(self._num_bars)
        for i in range(self._num_bars):
            lo = np.searchsorted(freqs, edges[i])
            hi = max(np.searchsorted(freqs, edges[i + 1]), lo + 1)
            raw[i] = np.mean(fft[lo:hi])

        peak = raw.max() + 1e-8
        raw = np.clip(raw / peak * self.sensitivity, 0.0, 1.0)
        self._bars = self._bars * self.smoothing + raw * (1.0 - self.smoothing)
        return self._bars

    @staticmethod
    def _height_color(ratio: float) -> int:
        """Green → yellow → red based on magnitude (0–1)."""
        if ratio < 0.5:
            return 22 + int(ratio * 2 * 24)  # dark green → bright green
        elif ratio < 0.8:
            return 226  # yellow
        else:
            return 196  # red

    @staticmethod
    def _heat_color(ratio: float) -> int:
        """Blue → cyan → green → yellow → red heat palette (0–1)."""
        if ratio < 0.25:
            return 17 + int(ratio * 4 * 18)  # dark blue → blue
        elif ratio < 0.5:
            return 51 + int((ratio - 0.25) * 4 * 12)  # cyan → green
        elif ratio < 0.75:
            return 82 + int((ratio - 0.5) * 4 * 12)  # green → yellow
        else:
            return 220 + int((ratio - 0.75) * 4 * 3)  # yellow → red

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """Advance one simulation tick; dt is measured in seconds."""
        # Stateful modes scroll their own buffer; everything else gets cleared.
        if self.mode not in _STATEFUL_MODES:
            self.buffer.clear_buffer(val=self.background)

        with self._lock:
            audio = self._audio_chunk.copy()

        if self._error:
            msg = self._error[: self._width]
            y = self._height // 2
            x = max(0, (self._width - len(msg)) // 2)
            self.buffer.put_at(x, y, msg)
            return

        if self.mode == "mirror":
            self._render_mirror(audio)
        elif self.mode == "waveform":
            self._render_waveform(audio)
        elif self.mode == "spectrum":
            self._render_spectrum(audio)
        elif self.mode == "radial":
            self._render_radial(audio)
        elif self.mode == "rain":
            self._render_rain(audio)
        elif self.mode == "tunnel":
            self._render_tunnel(audio)
        elif self.mode == "ripple":
            self._render_ripple(audio)
        elif self.mode == "vortex":
            self._render_vortex(audio)
        elif self.mode == "wave":
            self._render_wave(audio)
        elif self.mode == "starfield":
            self._render_starfield(audio)
        elif self.mode == "fireworks":
            self._render_fireworks(audio)
        elif self.mode == "interference":
            self._render_interference(audio)
        elif self.mode == "bounce":
            self._render_bounce(audio)
        elif self.mode == "lightning":
            self._render_lightning(audio)
        elif self.mode == "aurora":
            self._render_aurora(audio)
        elif self.mode == "orbit":
            self._render_orbit(audio)
        elif self.mode == "orbit_gradient":
            self._render_orbit_gradient(audio)
        elif self.mode == "scope":
            self._render_scope(audio)
        elif self.mode == "grid":
            self._render_grid(audio)
        elif self.mode == "helix":
            self._render_helix(audio)
        elif self.mode == "lissajous":
            self._render_lissajous(audio)
        elif self.mode == "sunburst":
            self._render_sunburst(audio)
        elif self.mode == "mandala":
            self._render_mandala(audio)
        elif self.mode == "comet":
            self._render_comet(audio)
        elif self.mode == "weave":
            self._render_weave(audio)
        else:
            self._render_bars(audio)

    def _render_bars(self, audio: np.ndarray):
        bars = self._fft_bars(audio)
        bar_w = max(1, self._width // self._num_bars)
        gap = 0 if self.compact else 1

        for i, mag in enumerate(bars):
            bar_h = int(mag * self._height)
            x0 = i * bar_w
            color = self._height_color(mag) if self.color else None
            ch = bc(self.bar_char, color=color) if color is not None else self.bar_char

            for col in range(x0, min(x0 + bar_w - gap, self._width)):
                for pix in range(bar_h):
                    self.buffer.put_char(col, self._height - 1 - pix, ch)

    def _render_mirror(self, audio: np.ndarray):
        bars = self._fft_bars(audio)
        bar_w = max(1, self._width // self._num_bars)
        mid = self._height // 2
        gap = 0 if self.compact else 1

        for i, mag in enumerate(bars):
            bar_h = int(mag * mid)
            x0 = i * bar_w
            color = self._height_color(mag) if self.color else None
            ch = bc(self.bar_char, color=color) if color is not None else self.bar_char

            for col in range(x0, min(x0 + bar_w - gap, self._width)):
                for pix in range(bar_h):
                    row_up = mid - 1 - pix
                    row_dn = mid + pix
                    if 0 <= row_up < self._height:
                        self.buffer.put_char(col, row_up, ch)
                    if 0 <= row_dn < self._height:
                        self.buffer.put_char(col, row_dn, ch)

    def _render_waveform(self, audio: np.ndarray):
        """Scrolling RMS amplitude envelope: each column = one frame, scrolls left over time."""
        rms = float(np.sqrt(np.mean(audio**2)))
        amp = min(rms * self.sensitivity * 8, 1.0)

        self._wave_history = np.roll(self._wave_history, -1)
        self._wave_history[-1] = amp

        mid = self._height // 2
        bg = self.background
        for x, val in enumerate(self._wave_history):
            peak = int(val * mid)
            color = self._height_color(val) if self.color else None
            ch = bc(self.bar_char, color=color) if color is not None else self.bar_char
            for row in range(self._height):
                offset = abs(row - mid)
                self.buffer.put_char(x, row, ch if offset <= peak else bg)

    def _render_spectrum(self, audio: np.ndarray):
        """Scrolling spectrogram: frequency on Y axis, time scrolls left."""
        bars = self._fft_bars(audio)
        bg = self.background

        # Shift every row 1 column left
        for row in self.buffer.buffer:
            row.pop(0)
            row.append(bg)

        # Draw the current FFT snapshot on the rightmost column
        x = self._width - 1
        n = len(bars)
        for i, mag in enumerate(bars):
            # Low frequencies at bottom, high at top
            y = self._height - 1 - int(i * self._height / n)
            y = max(0, min(self._height - 1, y))
            if mag > 0.02:
                color = self._heat_color(mag) if self.color else None
                ch = (
                    bc(self.bar_char, color=color)
                    if color is not None
                    else self.bar_char
                )
                self.buffer.put_char(x, y, ch)

    def _render_radial(self, audio: np.ndarray):
        """Circular pulse: each ring's radius is driven by its frequency band's energy."""
        bars = self._fft_bars(audio)
        cx = self._width // 2
        cy = self._height // 2
        # Terminal chars are ~2x taller than wide, compensate so the shape looks circular
        max_r = max(1, min(cx, cy * 2))
        n = len(bars)

        for row in range(self._height):
            for col in range(self._width):
                dx = col - cx
                dy = (row - cy) * 2  # aspect ratio compensation
                r = (dx * dx + dy * dy) ** 0.5
                r_norm = min(r / max_r, 1.0)
                band = int(r_norm * (n - 1))
                mag = bars[band]
                if mag > r_norm:
                    # Color by distance from center (inner = brighter)
                    color = self._height_color(1.0 - r_norm) if self.color else None
                    ch = (
                        bc(self.bar_char, color=color)
                        if color is not None
                        else self.bar_char
                    )
                    self.buffer.put_char(col, row, ch)

    def _render_rain(self, audio: np.ndarray):
        """Audio-driven rain with occasional lightning strikes."""
        bars = self._fft_bars(audio)
        cols_per_bar = max(1, self._width // len(bars))
        bg = self.background

        # Scroll buffer down by 1 row
        self.buffer.buffer.insert(0, [bg] * self._width)
        self.buffer.buffer.pop()

        # Spawn new drops at the top row based on frequency energy
        top = self.buffer.buffer[0]
        for i, mag in enumerate(bars):
            x0 = i * cols_per_bar
            x1 = min(x0 + cols_per_bar, self._width)
            for col in range(x0, x1):
                if random.random() < mag:
                    color = self._height_color(mag) if self.color else None
                    char = random.choice(_RAIN_CHARS)
                    top[col] = bc(char, color=color) if color is not None else char

        # Lightning overlay — less frequent than standalone lightning mode
        energy = float(np.mean(bars))
        if self._lightning_cooldown > 0:
            self._lightning_cooldown -= 1
        if self._lightning_cooldown == 0 and energy > 0.15:
            self._lightning_bolts.append(
                (_make_bolt(self._width, self._height), random.randint(2, 4))
            )
            self._lightning_cooldown = max(20, int(70 - energy * 45))

        alive = []
        for path, frames in self._lightning_bolts:
            if frames <= 0:
                continue
            alive.append((path, frames - 1))
            color = (226 if frames > 2 else 229) if self.color else None
            ch = bc("|", color=color) if color is not None else "|"
            for bx, by in path:
                if 0 <= bx < self._width and 0 <= by < self._height:
                    self.buffer.buffer[by][bx] = ch
        self._lightning_bolts = alive

    def _render_tunnel(self, audio: np.ndarray):
        """Rectangular frames that spawn at the edges and zoom inward, driven by energy."""
        bars = self._fft_bars(audio)
        energy = float(np.mean(bars))
        cx, cy = self._width // 2, self._height // 2

        spawn_every = max(1, int(7 - energy * 6))
        if self._tunnel_frame % spawn_every == 0:
            self._tunnel_rings.append({"depth": 1.0, "bars": bars.copy()})
        self._tunnel_frame += 1

        speed = 0.04 + energy * 0.09
        alive = []
        for ring in self._tunnel_rings:
            ring["depth"] -= speed
            if ring["depth"] <= 0.0:
                continue
            alive.append(ring)

            # depth=1 → far (tiny), depth→0 → near (full screen)
            scale = 1.0 - ring["depth"]
            rx = max(1, int(scale * cx))
            ry = max(1, int(scale * cy))

            # Color transitions from cool (far) to hot (near)
            color = self._heat_color(scale) if self.color else None
            ch = bc(self.bar_char, color=color) if color is not None else self.bar_char

            top, bot = cy - ry, cy + ry
            left, right = cx - rx, cx + rx

            for x in range(max(0, left), min(self._width, right + 1)):
                if 0 <= top < self._height:
                    self.buffer.put_char(x, top, ch)
                if 0 <= bot < self._height:
                    self.buffer.put_char(x, bot, ch)
            for y in range(max(0, top + 1), min(self._height, bot)):
                if 0 <= left < self._width:
                    self.buffer.put_char(left, y, ch)
                if 0 <= right < self._width:
                    self.buffer.put_char(right, y, ch)

        self._tunnel_rings = alive[-24:]

    def _render_ripple(self, audio: np.ndarray):
        """Elliptical rings that expand from the center; spawn rate scales with energy."""
        bars = self._fft_bars(audio)
        energy = float(np.mean(bars))

        # Spawn a new ripple when the cooldown expires and there's any signal.
        # Cooldown shrinks as energy rises so loud audio produces dense rings.
        if self._beat_cooldown > 0:
            self._beat_cooldown -= 1

        if self._beat_cooldown == 0 and energy > 0.02:
            dominant = int(np.argmax(bars))
            self._ripples.append(
                {
                    "r": 0.0,
                    "speed": 0.8 + energy * 2.5,
                    "color_ratio": dominant / max(1, len(bars) - 1),
                }
            )
            self._beat_cooldown = max(2, int(14 - energy * 12))

        cx, cy = self._width // 2, self._height // 2
        max_r = math.hypot(cx, cy)

        alive = []
        for ripple in self._ripples:
            ripple["r"] += ripple["speed"]
            if ripple["r"] > max_r * 1.4:
                continue
            alive.append(ripple)

            r = ripple["r"]
            color = self._heat_color(ripple["color_ratio"]) if self.color else None
            ch = bc(self.bar_char, color=color) if color is not None else self.bar_char

            n_steps = max(8, int(r * math.pi))
            thetas = np.linspace(0, 2 * math.pi, n_steps, endpoint=False)
            xs = (cx + r * np.cos(thetas)).astype(int)
            ys = (cy + r * np.sin(thetas) * 0.5).astype(int)
            mask = (xs >= 0) & (xs < self._width) & (ys >= 0) & (ys < self._height)
            for x, y in zip(xs[mask], ys[mask]):
                self.buffer.put_char(int(x), int(y), ch)

        self._ripples = alive

    def _render_vortex(self, audio: np.ndarray):
        """Three Archimedean spiral arms that rotate; speed and fill track audio energy."""
        bars = self._fft_bars(audio)
        energy = float(np.mean(bars))
        cx, cy = self._width // 2, self._height // 2
        max_r = min(cx, cy * 2)

        self._vortex_angle += 0.04 + energy * 0.28

        n_arms = 3
        t = np.linspace(0, 1, 350)
        r = t * max_r
        band_idx = (t * (len(bars) - 1)).astype(int)
        mags = bars[band_idx]

        for arm in range(n_arms):
            arm_offset = 2 * math.pi * arm / n_arms
            theta = self._vortex_angle + arm_offset + t * 3.5 * math.pi

            xs = (cx + r * np.cos(theta)).astype(int)
            ys = (cy + r * np.sin(theta) * 0.5).astype(int)

            # Only draw points where the frequency band has enough energy
            visible = (
                (xs >= 0)
                & (xs < self._width)
                & (ys >= 0)
                & (ys < self._height)
                & (mags > t * 0.35)
            )
            for i in np.where(visible)[0]:
                mag = float(mags[i])
                color = self._height_color(mag) if self.color else None
                ch = (
                    bc(self.bar_char, color=color)
                    if color is not None
                    else self.bar_char
                )
                self.buffer.put_char(int(xs[i]), int(ys[i]), ch)

    def _render_wave(self, audio: np.ndarray):
        """Multiple sine waves, each driven by its own frequency band, overlaid."""
        bars = self._fft_bars(audio)
        n_waves = min(8, len(bars))
        mid = self._height // 2

        # Advance each wave's phase; higher bands scroll faster
        for i in range(n_waves):
            band_idx = int(i * (len(bars) - 1) / max(1, n_waves - 1))
            self._sine_phases[i] += 0.06 + i * 0.018 + bars[band_idx] * 0.22

        for i in range(n_waves):
            band_idx = int(i * (len(bars) - 1) / max(1, n_waves - 1))
            mag = bars[band_idx]
            amp = mag * mid * 0.85
            freq = (i + 1) / 4.0
            # Color progresses through the heat palette across bands
            color = self._heat_color(i / max(1, n_waves - 1)) if self.color else None
            ch = bc(self.bar_char, color=color) if color is not None else self.bar_char

            prev_y = None
            for x in range(self._width):
                y = int(mid + amp * math.sin(freq * x * 0.13 + self._sine_phases[i]))
                y = max(0, min(self._height - 1, y))
                self.buffer.put_char(x, y, ch)

                # Fill vertically between consecutive points so the wave is solid
                if prev_y is not None and abs(y - prev_y) > 1:
                    for py in range(min(y, prev_y) + 1, max(y, prev_y)):
                        self.buffer.put_char(x, py, ch)
                prev_y = y

    def _render_starfield(self, audio: np.ndarray):
        """Stars zoom toward the viewer; speed proportional to audio energy."""
        bars = self._fft_bars(audio)
        energy = float(np.mean(bars))
        cx, cy = self._width // 2, self._height // 2

        speed = 0.012 + energy * 0.055
        self._stars[:, 2] -= speed

        # Reset stars that have passed the camera
        reset = self._stars[:, 2] <= 0.0
        if reset.any():
            n = int(reset.sum())
            rng = np.random.default_rng()
            self._stars[reset, 0] = rng.uniform(-1.0, 1.0, n)
            self._stars[reset, 1] = rng.uniform(-1.0, 1.0, n)
            self._stars[reset, 2] = 1.0

        # Perspective project and draw
        z = self._stars[:, 2]
        sx = (cx + self._stars[:, 0] / z * cx * 0.95).astype(int)
        sy = (cy + self._stars[:, 1] / z * cy * 0.95).astype(int)
        brightness = np.clip(1.0 - z, 0.0, 1.0)

        visible = (sx >= 0) & (sx < self._width) & (sy >= 0) & (sy < self._height)
        for i in np.where(visible)[0]:
            b = float(brightness[i])
            color = self._height_color(b) if self.color else None
            ch = bc(self.bar_char, color=color) if color is not None else self.bar_char
            self.buffer.put_char(int(sx[i]), int(sy[i]), ch)

    def _render_fireworks(self, audio: np.ndarray):
        """Particle bursts that explode outward and fall under gravity."""
        bars = self._fft_bars(audio)
        energy = float(np.mean(bars))

        if self._fw_cooldown > 0:
            self._fw_cooldown -= 1

        if self._fw_cooldown == 0 and energy > 0.05:
            bx = random.randint(self._width // 5, 4 * self._width // 5)
            by = random.randint(self._height // 5, 3 * self._height // 5)
            n = int(18 + energy * 35)
            dominant = int(np.argmax(bars))
            color_ratio = dominant / max(1, len(bars) - 1)
            for _ in range(n):
                angle = random.uniform(0, 2 * math.pi)
                spd = random.uniform(0.4, 1.8 + energy * 2.0)
                self._fw_particles.append(
                    {
                        "x": float(bx),
                        "y": float(by),
                        "vx": math.cos(angle) * spd,
                        "vy": math.sin(angle) * spd * 0.45,
                        "life": 1.0,
                        "decay": random.uniform(0.04, 0.12),
                        "color_ratio": color_ratio,
                        "ch": random.choice(_FW_CHARS),
                    }
                )
            self._fw_cooldown = max(3, int(18 - energy * 14))

        gravity = 0.06
        alive = []
        for p in self._fw_particles:
            p["vy"] += gravity
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["life"] -= p["decay"]
            if p["life"] <= 0.05:
                continue
            x, y = int(p["x"]), int(p["y"])
            if not (0 <= x < self._width and 0 <= y < self._height):
                alive.append(p)  # keep off-screen particles (they may come back)
                continue
            alive.append(p)
            # Fade color as particle ages
            cr = p["color_ratio"] * p["life"]
            color = self._heat_color(cr) if self.color else None
            ch = bc(p["ch"], color=color) if color is not None else p["ch"]
            self.buffer.put_char(x, y, ch)

        self._fw_particles = alive[:300]  # hard cap

    def _render_interference(self, audio: np.ndarray):
        """Two-source wave interference; source positions and wave freq shift with audio."""
        bars = self._fft_bars(audio)
        energy = float(np.mean(bars))

        self._intf_phase += 0.04 + energy * 0.12

        # Lazily build the pixel coordinate grids
        if self._intf_X is None or self._intf_X.shape != (self._height, self._width):
            cols = np.arange(self._width)
            rows = np.arange(self._height)
            self._intf_X, self._intf_Y = np.meshgrid(cols, rows)

        cx, cy = self._width // 2, self._height // 2

        # Source positions oscillate gently around symmetric points
        ox = int(cx * 0.35 + cx * 0.1 * math.sin(self._intf_phase * 0.17))
        oy = int(cy * 0.2 * math.cos(self._intf_phase * 0.11))
        s1x, s1y = cx - ox, cy + oy
        s2x, s2y = cx + ox, cy - oy

        # Aspect-ratio-corrected distances (chars ~2× taller than wide)
        Yc = self._intf_Y * 2
        d1 = np.sqrt((self._intf_X - s1x) ** 2 + (Yc - s1y * 2) ** 2)
        d2 = np.sqrt((self._intf_X - s2x) ** 2 + (Yc - s2y * 2) ** 2)

        # Bass band drives frequency, treble drives secondary source freq
        freq1 = 0.28 + float(bars[0]) * 0.35
        freq2 = 0.28 + float(bars[-1]) * 0.35
        combined = (
            np.sin(d1 * freq1 - self._intf_phase)
            + np.sin(d2 * freq2 - self._intf_phase)
        ) / 2.0

        threshold = 0.45
        lit_y, lit_x = np.where(combined > threshold)
        mags = (combined[lit_y, lit_x] - threshold) / (1.0 - threshold)

        for idx in range(len(lit_y)):
            mag = float(mags[idx])
            color = self._heat_color(mag) if self.color else None
            ch = bc(self.bar_char, color=color) if color is not None else self.bar_char
            self.buffer.put_char(int(lit_x[idx]), int(lit_y[idx]), ch)

    def _render_bounce(self, audio: np.ndarray):
        """Balls with glowing trails bounce around; each tracks its own frequency band."""
        bars = self._fft_bars(audio)

        for ball in self._balls:
            band_idx = int(ball["band"] * (len(bars) - 1) / max(1, _N_BALLS - 1))
            mag = bars[band_idx]

            speed = 0.4 + mag * 3.5
            ball["x"] += ball["vx"] * speed
            ball["y"] += ball["vy"] * speed * 0.5

            if ball["x"] < 0:
                ball["x"] = 0.0
                ball["vx"] = abs(ball["vx"])
            elif ball["x"] >= self._width:
                ball["x"] = float(self._width - 1)
                ball["vx"] = -abs(ball["vx"])

            if ball["y"] < 0:
                ball["y"] = 0.0
                ball["vy"] = abs(ball["vy"])
            elif ball["y"] >= self._height:
                ball["y"] = float(self._height - 1)
                ball["vy"] = -abs(ball["vy"])

            ball["trail"].append((ball["x"], ball["y"], mag))

            # Draw trail from oldest (dim) to newest (bright)
            trail = list(ball["trail"])
            for j, (tx, ty, tmag) in enumerate(trail):
                fade = (j + 1) / len(trail)  # 0=oldest, 1=newest
                color = self._heat_color(fade * tmag) if self.color else None
                ch = (
                    bc(self.bar_char, color=color)
                    if color is not None
                    else self.bar_char
                )
                self.buffer.put_char(int(tx), int(ty), ch)

    def _render_lightning(self, audio: np.ndarray):
        """Branching electric bolts strike downward on energy spikes."""
        bars = self._fft_bars(audio)
        energy = float(np.mean(bars))

        if self._lightning_cooldown > 0:
            self._lightning_cooldown -= 1

        if self._lightning_cooldown == 0 and energy > 0.08:
            self._lightning_bolts.append(
                (_make_bolt(self._width, self._height), random.randint(2, 5))
            )
            self._lightning_cooldown = max(4, int(28 - energy * 22))

        alive = []
        for path, frames in self._lightning_bolts:
            if frames <= 0:
                continue
            alive.append((path, frames - 1))
            # Brighter on first frame, dimmer as it fades
            color = (226 if frames > 3 else 229) if self.color else None
            ch = bc("|", color=color) if color is not None else "|"
            for bx, by in path:
                self.buffer.put_char(bx, by, ch)

        self._lightning_bolts = alive

    def _render_aurora(self, audio: np.ndarray):
        """Flowing vertical curtains of color; each band drives its own curtain's height."""
        bars = self._fft_bars(audio)
        energy = float(np.mean(bars))

        self._aurora_phase += 0.018 + energy * 0.04

        n_curtains = min(6, len(bars))

        for col in range(self._width):
            col_norm = col / max(1, self._width - 1)

            for i in range(n_curtains):
                band_idx = int(i * (len(bars) - 1) / max(1, n_curtains - 1))
                mag = bars[band_idx]
                if mag < 0.04:
                    continue

                # Wave: two overlapping sines give the rippling curtain edge
                wave = (
                    math.sin(col_norm * 5.0 + self._aurora_phase + i * 0.8) * 0.35
                    + math.sin(col_norm * 11.0 - self._aurora_phase * 1.4 + i * 1.5)
                    * 0.15
                    + 0.5
                )
                top_y = int(self._height * (0.05 + i * 0.10))
                curtain_h = int(mag * wave * self._height * 0.45)

                for dy in range(curtain_h):
                    y = top_y + dy
                    if not (0 <= y < self._height):
                        continue
                    # Fade from hot (top) to cool (bottom of curtain)
                    fade = 1.0 - dy / max(1, curtain_h)
                    color_r = i / max(1, n_curtains - 1) * 0.6 + fade * 0.4
                    color = self._heat_color(color_r) if self.color else None
                    ch = (
                        bc(self.bar_char, color=color)
                        if color is not None
                        else self.bar_char
                    )
                    self.buffer.put_char(col, y, ch)

    def _render_orbit(self, audio: np.ndarray):
        """Orbiting particles with audio-reactive branching spikes; scales with screen dimensions."""
        bars = self._fft_bars(audio)
        cx, cy = self._width // 2, self._height // 2
        max_r = min(cx * 0.92, cy * 1.85)

        # Cap orbits to a much more readable number, maxing out at 32
        n_orbits = min(len(bars), max(12, min(32, int(self._height * 0.4))))

        # Significantly lower density factor so individual characters are distinguishable
        density_factor = max(0.5, (self._width + self._height * 2) / 160.0)

        for i in range(n_orbits):
            band_idx = int(i * (len(bars) - 1) / max(1, n_orbits - 1))
            raw_mag = bars[band_idx]

            # Decay logic: fast attack, slow decay
            old_mag = self._orbit_mags[i]
            if raw_mag > old_mag:
                mag = raw_mag * 0.8 + old_mag * 0.2  # Fast attack
            else:
                mag = old_mag * 0.88  # Slow decay
            self._orbit_mags[i] = mag

            if mag < 0.01:
                continue

            # Smoother rotation: reduced base speed and mag influence
            omega = 0.01 + (i / n_orbits) * 0.02 + mag * 0.03
            self._orbit_angles[i] += omega

            # Smoother radius: less extreme expansion/contraction
            base_r = (i + 1) / n_orbits * max_r
            r = base_r * (0.85 + mag * 0.15)

            color = self._heat_color(mag) if self.color else None
            ch = bc(self.bar_char, color=color) if color is not None else self.bar_char

            # Drastically fewer particles for cleaner readability
            n_particles = max(4, int(r * density_factor * (0.4 + mag * 0.4)))
            base_thetas = self._orbit_angles[i] + np.linspace(
                0, 2 * math.pi, n_particles, endpoint=False
            )

            # Low jitter: tight orbits for a cleaner look
            jitter_theta = np.random.uniform(-0.06, 0.06, n_particles)
            jitter_r = np.random.uniform(-base_r * 0.025, base_r * 0.025, n_particles)
            thetas = base_thetas + jitter_theta
            rs = r + jitter_r

            # Branching effect: extrude lines outward based on audio magnitude
            # Shorter spikes, fewer steps to prevent a solid wall of characters
            spike_amp = mag * max_r * 0.25
            steps = min(8, max(1, int(spike_amp * 0.4)))

            if steps > 1:
                rs_ext = rs[:, None] + np.linspace(0, spike_amp, steps)
                curve_dirs = np.random.uniform(-0.15, 0.15, (n_particles, 1))
                thetas_ext = thetas[:, None] + (
                    curve_dirs * np.linspace(0, 1.0, steps) * mag
                )
                rs = rs_ext.flatten()
                thetas = thetas_ext.flatten()

            xs = (cx + rs * np.cos(thetas)).astype(int)
            ys = (cy + rs * np.sin(thetas) * 0.5).astype(int)
            mask = (xs >= 0) & (xs < self._width) & (ys >= 0) & (ys < self._height)
            for x, y in zip(xs[mask], ys[mask]):
                self.buffer.put_char(int(x), int(y), ch)

    def _render_orbit_gradient(self, audio: np.ndarray):
        """Orbiting particles using a character density gradient with branching spikes for different bands."""
        bars = self._fft_bars(audio)
        cx, cy = self._width // 2, self._height // 2
        max_r = min(cx * 0.92, cy * 1.85)

        # Cap orbits to a much more readable number, maxing out at 32
        n_orbits = min(len(bars), max(12, min(32, int(self._height * 0.4))))

        # Significantly lower density factor so individual characters are distinguishable
        density_factor = max(0.5, (self._width + self._height * 2) / 160.0)

        for i in range(n_orbits):
            band_idx = int(i * (len(bars) - 1) / max(1, n_orbits - 1))
            raw_mag = bars[band_idx]

            # Decay logic: fast attack, slow decay
            old_mag = self._orbit_mags[i]
            if raw_mag > old_mag:
                mag = raw_mag * 0.8 + old_mag * 0.2  # Fast attack
            else:
                mag = old_mag * 0.88  # Slow decay
            self._orbit_mags[i] = mag

            if mag < 0.01:
                continue

            omega = 0.01 + (i / n_orbits) * 0.02 + mag * 0.03
            self._orbit_angles[i] += omega

            base_r = (i + 1) / n_orbits * max_r
            r = base_r * (0.85 + mag * 0.15)

            color = self._heat_color(mag) if self.color else None

            # Select character based on radius/band (inner = light, outer = heavy)
            char_idx = int((i / max(1, n_orbits - 1)) * (len(_GRADIENT_CHARS) - 1))
            base_char = _GRADIENT_CHARS[char_idx]

            ch = bc(base_char, color=color) if color is not None else base_char

            # Drastically fewer particles for cleaner readability
            n_particles = max(4, int(r * density_factor * (0.4 + mag * 0.4)))
            base_thetas = self._orbit_angles[i] + np.linspace(
                0, 2 * math.pi, n_particles, endpoint=False
            )

            jitter_theta = np.random.uniform(-0.06, 0.06, n_particles)
            jitter_r = np.random.uniform(-base_r * 0.025, base_r * 0.025, n_particles)
            thetas = base_thetas + jitter_theta
            rs = r + jitter_r

            # Branching effect: extrude lines outward based on audio magnitude
            # Shorter spikes, fewer steps to prevent a solid wall of characters
            spike_amp = mag * max_r * 0.25
            steps = min(8, max(1, int(spike_amp * 0.4)))

            if steps > 1:
                rs_ext = rs[:, None] + np.linspace(0, spike_amp, steps)
                curve_dirs = np.random.uniform(-0.15, 0.15, (n_particles, 1))
                thetas_ext = thetas[:, None] + (
                    curve_dirs * np.linspace(0, 1.0, steps) * mag
                )
                rs = rs_ext.flatten()
                thetas = thetas_ext.flatten()

            xs = (cx + rs * np.cos(thetas)).astype(int)
            ys = (cy + rs * np.sin(thetas) * 0.5).astype(int)
            mask = (xs >= 0) & (xs < self._width) & (ys >= 0) & (ys < self._height)
            for x, y in zip(xs[mask], ys[mask]):
                self.buffer.put_char(int(x), int(y), ch)

    def _render_scope(self, audio: np.ndarray):
        """Raw oscilloscope: draws the actual audio samples across the screen width."""
        # No FFT — use the raw waveform directly
        n = len(audio)
        mid = self._height // 2
        prev_y: int | None = None

        for x in range(self._width):
            idx = int(x * n / self._width)
            sample = float(audio[idx]) * self.sensitivity
            y = int(mid - sample * mid * 0.92)
            y = max(0, min(self._height - 1, y))

            mag = min(abs(sample), 1.0)
            color = self._height_color(mag) if self.color else None
            ch = bc(self.bar_char, color=color) if color is not None else self.bar_char
            self.buffer.put_char(x, y, ch)

            # Draw a vertical line between this and the previous sample so fast
            # transitions don't leave gaps
            if prev_y is not None and abs(y - prev_y) > 1:
                for py in range(min(y, prev_y) + 1, max(y, prev_y)):
                    self.buffer.put_char(x, py, ch)
            prev_y = y

    def _render_grid(self, audio: np.ndarray):
        """Screen-filling frequency grid; each cell glows proportionally to its band's energy."""
        bars = self._fft_bars(audio)
        n_cols = max(1, min(16, self._width // 4))
        n_rows = max(1, min(8, self._height // 3))
        cell_w = max(1, self._width // n_cols)
        cell_h = max(1, self._height // n_rows)
        n_cells = n_cols * n_rows

        for row in range(n_rows):
            for col in range(n_cols):
                cell_idx = row * n_cols + col
                band_idx = min(int(cell_idx * len(bars) / n_cells), len(bars) - 1)
                mag = bars[band_idx]
                if mag < 0.04:
                    continue

                x0 = col * cell_w
                y0 = row * cell_h
                fill_w = max(1, int(mag * (cell_w - 1)))
                fill_h = max(1, int(mag * (cell_h - 1)))
                x_off = (cell_w - fill_w) // 2
                y_off = (cell_h - fill_h) // 2

                color = self._heat_color(mag) if self.color else None
                ch = (
                    bc(self.bar_char, color=color)
                    if color is not None
                    else self.bar_char
                )

                for dy in range(fill_h):
                    for dx in range(fill_w):
                        x = x0 + x_off + dx
                        y = y0 + y_off + dy
                        if 0 <= x < self._width and 0 <= y < self._height:
                            self.buffer.put_char(x, y, ch)

    def _render_helix(self, audio: np.ndarray):
        """Scrolling double helix with rungs; pitch and rung spacing react to audio energy."""
        bars = self._fft_bars(audio)
        energy = float(np.mean(bars))

        self._helix_phase += 0.06 + energy * 0.18

        mid = self._height // 2
        amp = mid * 0.8
        # Bass drives how many full cycles span the screen
        freq = 2.0 + float(bars[0]) * 2.5

        for x in range(self._width):
            t = (x / self._width) * 2 * math.pi * freq + self._helix_phase

            y1 = max(0, min(self._height - 1, int(mid + amp * math.sin(t) * 0.5)))
            y2 = max(
                0, min(self._height - 1, int(mid + amp * math.sin(t + math.pi) * 0.5))
            )

            # Strand 1 — cool end of palette
            color1 = (
                self._heat_color(0.15 + float(bars[0]) * 0.3) if self.color else None
            )
            ch1 = (
                bc(self.bar_char, color=color1) if color1 is not None else self.bar_char
            )
            self.buffer.put_char(x, y1, ch1)

            # Strand 2 — warm end of palette
            color2 = (
                self._heat_color(0.65 + float(bars[-1]) * 0.3) if self.color else None
            )
            ch2 = (
                bc(self.bar_char, color=color2) if color2 is not None else self.bar_char
            )
            self.buffer.put_char(x, y2, ch2)

            # Connecting rungs — spacing shrinks with energy
            rung_interval = max(2, int(8 - energy * 5))
            if x % rung_interval == 0:
                color_r = self._heat_color(energy) if self.color else None
                rung_ch = bc("-", color=color_r) if color_r is not None else "-"
                lo, hi = min(y1, y2), max(y1, y2)
                for y in range(lo + 1, hi):
                    if 0 <= y < self._height:
                        self.buffer.put_char(x, y, rung_ch)

    def _render_lissajous(self, audio: np.ndarray):
        """Lissajous figure; bass drives the horizontal frequency ratio, treble drives vertical."""
        bars = self._fft_bars(audio)
        cx, cy = self._width // 2, self._height // 2
        rx = cx * 0.9
        ry = cy * 0.85

        a = 1.0 + float(bars[0]) * 3.0  # 1–4 driven by bass
        b = 2.0 + float(bars[-1]) * 2.0  # 2–4 driven by treble

        energy = float(np.mean(bars))
        self._liss_t += 0.025 + energy * 0.07

        n_steps = max(200, self._width * 2)
        ts = np.linspace(0, 2 * math.pi, n_steps)
        xs = (cx + rx * np.sin(a * ts + self._liss_t)).astype(int)
        ys = (cy + ry * np.sin(b * ts) * 0.5).astype(int)

        mask = (xs >= 0) & (xs < self._width) & (ys >= 0) & (ys < self._height)
        idxs = np.where(mask)[0]

        for idx in idxs:
            ratio = float(idx) / max(1, n_steps - 1)
            color = self._heat_color(ratio) if self.color else None
            ch = bc(self.bar_char, color=color) if color is not None else self.bar_char
            self.buffer.put_char(int(xs[idx]), int(ys[idx]), ch)

    def _render_sunburst(self, audio: np.ndarray):
        """Radial spokes from center; each spoke's length is driven by its frequency band."""
        bars = self._fft_bars(audio)
        cx, cy = self._width // 2, self._height // 2
        max_r = min(cx * 0.95, cy * 1.9)
        energy = float(np.mean(bars))

        self._sunburst_angle += 0.008 + energy * 0.025

        n_spokes = min(32, len(bars))

        for i in range(n_spokes):
            band_idx = int(i * (len(bars) - 1) / max(1, n_spokes - 1))
            mag = bars[band_idx]
            if mag < 0.02:
                continue

            theta = self._sunburst_angle + (i / n_spokes) * 2 * math.pi
            r = mag * max_r

            color = self._heat_color(mag) if self.color else None
            ch = bc(self.bar_char, color=color) if color is not None else self.bar_char

            steps = max(2, int(r * 1.2))
            ts = np.linspace(0.0, 1.0, steps)
            xs = (cx + r * ts * math.cos(theta)).astype(int)
            ys = (cy + r * ts * math.sin(theta) * 0.5).astype(int)
            mask = (xs >= 0) & (xs < self._width) & (ys >= 0) & (ys < self._height)
            for x, y in zip(xs[mask], ys[mask]):
                self.buffer.put_char(int(x), int(y), ch)

    def _render_mandala(self, audio: np.ndarray):
        """N-fold symmetric petal pattern; each layer's bloom size driven by a frequency band."""
        bars = self._fft_bars(audio)
        cx, cy = self._width // 2, self._height // 2
        max_r = min(cx * 0.9, cy * 1.8)
        energy = float(np.mean(bars))

        self._mandala_angle += 0.004 + energy * 0.012

        n_fold = 8
        n_layers = min(6, len(bars))

        for layer in range(n_layers):
            band_idx = int(layer * (len(bars) - 1) / max(1, n_layers - 1))
            mag = bars[band_idx]
            if mag < 0.03:
                continue

            layer_r = (layer + 1) / n_layers * max_r
            color = (
                self._heat_color(layer / max(1, n_layers - 1)) if self.color else None
            )
            ch = bc(self.bar_char, color=color) if color is not None else self.bar_char

            arc_steps = max(8, int(layer_r * 0.9))
            ts = np.linspace(0.0, 1.0, arc_steps)
            petal_scale = np.sin(ts * math.pi) * mag

            for fold in range(n_fold):
                base_theta = fold * (2 * math.pi / n_fold) + self._mandala_angle
                thetas = base_theta + ts * (math.pi / n_fold)
                rs = layer_r * petal_scale
                xs = (cx + rs * np.cos(thetas)).astype(int)
                ys = (cy + rs * np.sin(thetas) * 0.5).astype(int)
                mask = (xs >= 0) & (xs < self._width) & (ys >= 0) & (ys < self._height)
                for x, y in zip(xs[mask], ys[mask]):
                    self.buffer.put_char(int(x), int(y), ch)

    def _render_comet(self, audio: np.ndarray):
        """Comets streak across the screen from random edges; speed and spawn rate track energy."""
        bars = self._fft_bars(audio)
        energy = float(np.mean(bars))

        if self._comet_cooldown > 0:
            self._comet_cooldown -= 1

        if self._comet_cooldown == 0 and energy > 0.03:
            edge = random.randint(0, 3)
            speed_mult = 1.0 + energy * 2.5
            if edge == 0:
                x, y = 0.0, float(random.randint(0, self._height - 1))
                vx = random.uniform(1.5, 3.5) * speed_mult
                vy = random.uniform(-0.6, 0.6)
            elif edge == 1:
                x, y = (
                    float(self._width - 1),
                    float(random.randint(0, self._height - 1)),
                )
                vx = random.uniform(-3.5, -1.5) * speed_mult
                vy = random.uniform(-0.6, 0.6)
            elif edge == 2:
                x, y = float(random.randint(0, self._width - 1)), 0.0
                vx = random.uniform(-0.6, 0.6)
                vy = random.uniform(0.5, 1.8) * speed_mult
            else:
                x, y = (
                    float(random.randint(0, self._width - 1)),
                    float(self._height - 1),
                )
                vx = random.uniform(-0.6, 0.6)
                vy = random.uniform(-1.8, -0.5) * speed_mult

            dominant = int(np.argmax(bars))
            self._comets.append(
                {
                    "x": x,
                    "y": y,
                    "vx": vx,
                    "vy": vy,
                    "trail": deque(maxlen=14),
                    "color_ratio": dominant / max(1, len(bars) - 1),
                }
            )
            self._comet_cooldown = max(2, int(10 - energy * 8))

        alive = []
        for comet in self._comets:
            comet["x"] += comet["vx"]
            comet["y"] += comet["vy"]
            comet["trail"].append((comet["x"], comet["y"]))

            margin = 16
            if not (
                -margin <= comet["x"] < self._width + margin
                and -margin <= comet["y"] < self._height + margin
            ):
                continue
            alive.append(comet)

            trail = list(comet["trail"])
            for j, (tx, ty) in enumerate(trail):
                fade = (j + 1) / len(trail)
                color = (
                    self._heat_color(comet["color_ratio"] * fade)
                    if self.color
                    else None
                )
                ch = (
                    bc(self.bar_char, color=color)
                    if color is not None
                    else self.bar_char
                )
                ix, iy = int(tx), int(ty)
                if 0 <= ix < self._width and 0 <= iy < self._height:
                    self.buffer.put_char(ix, iy, ch)

        self._comets = alive[:40]

    def _render_weave(self, audio: np.ndarray):
        """Interlaced horizontal and vertical sine waves; crossings glow based on energy."""
        bars = self._fft_bars(audio)
        energy = float(np.mean(bars))

        self._weave_phase += 0.04 + energy * 0.12

        n_h = max(1, min(6, len(bars) // 2))
        n_v = max(1, min(6, len(bars) // 2))

        # Horizontal wave lines
        for i in range(n_h):
            band_idx = int(i * (len(bars) - 1) / max(1, n_h - 1))
            mag = bars[band_idx]
            if mag < 0.02:
                continue
            amp = mag * self._height * 0.12
            y_base = int((i + 0.5) / n_h * self._height)
            color = self._heat_color(i / max(1, n_h - 1) * 0.5) if self.color else None
            ch = bc(self.bar_char, color=color) if color is not None else self.bar_char

            xs = np.arange(self._width)
            ys = np.clip(
                (y_base + amp * np.sin(xs * 0.15 + self._weave_phase + i * 1.1)).astype(
                    int
                ),
                0,
                self._height - 1,
            )
            for x, y in zip(xs, ys):
                self.buffer.put_char(int(x), int(y), ch)

        # Vertical wave lines
        for i in range(n_v):
            band_idx = min(
                int((i + n_h) * (len(bars) - 1) / max(1, n_h + n_v - 1)), len(bars) - 1
            )
            mag = bars[band_idx]
            if mag < 0.02:
                continue
            amp = mag * self._width * 0.06
            x_base = int((i + 0.5) / n_v * self._width)
            color = (
                self._heat_color(0.5 + i / max(1, n_v - 1) * 0.5)
                if self.color
                else None
            )
            ch = bc(self.bar_char, color=color) if color is not None else self.bar_char

            ys = np.arange(self._height)
            xs = np.clip(
                (x_base + amp * np.sin(ys * 0.25 - self._weave_phase + i * 0.9)).astype(
                    int
                ),
                0,
                self._width - 1,
            )
            for x, y in zip(xs, ys):
                self.buffer.put_char(int(x), int(y), ch)

    def stop(self, timeout: float = 2.0):
        """Stop capture and wait at most timeout seconds for resource cleanup.

        A backend stuck during device initialization is reported, rather than
        silently leaving a live worker behind. A later close can retry joining.
        """
        self._running = False
        self._stop_event.set()
        if self._thread is not None:
            if self._thread is threading.current_thread():
                return
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                raise RuntimeError(
                    "Audio capture worker did not stop before the timeout"
                )
            self._thread = None
        super().stop()
