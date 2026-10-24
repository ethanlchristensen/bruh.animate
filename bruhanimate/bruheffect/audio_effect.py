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
import sys
import threading
from contextlib import ExitStack
from importlib import import_module
from importlib.util import find_spec

import numpy as np
from bruhcolor import bruhcolored as bc

from ..bruhutil.bruhffer import Buffer
from ._resize import raster
from .base_effect import BaseEffect
from .settings import AudioMode, AudioSettings, validated_settings

_SAMPLE_RATE = 44100
_CHUNK = 1024

# Modes that manage their own buffer state — skip the per-frame clear
_STATEFUL_MODES = {"spectrum", "waveform"}


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

    Seven modes: objects (a screen-wide field of reactive shapes), tiles (frequency
    blocks), glow (moving light pools), bars, mirror, waveform (volume history),
    and spectrum (frequency history). Summed band energy includes diffuse mids
    and treble, with a fixed noise floor instead of normalizing each chunk to its
    peak. These are artistic displays, not calibrated audio meters.

    **Windows** requires ``PyAudioWPatch`` for WASAPI loopback::

        pip install bruhanimate[audio]

    **Linux** requires ``sounddevice`` and a PulseAudio/PipeWire monitor source::

        pip install bruhanimate[audio]
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: AudioSettings | None = None
    ):
        """
        Initialize the audio effect.

        Args:
            buffer (Buffer): Effect buffer to push updates to.
            background (str): Character or string to use for the background.
            settings (AudioSettings, optional): Configuration for the audio effect.
        """
        s = validated_settings(settings, AudioSettings)
        super().__init__(buffer, background, seed=s.seed)

        self.mode = s.mode
        self.bar_char = s.bar_char
        self.smoothing = s.smoothing
        self.color = s.color
        self.sensitivity = s.sensitivity
        self.compact = s.compact
        self.bar_gain = s.bar_gain

        self._height = buffer.height()
        self._width = buffer.width()
        self._auto_bars = s.num_bars == 0
        self._num_bars = s.num_bars if s.num_bars > 0 else max(1, self._width // 2)

        self._bars = np.zeros(self._num_bars)
        self._wave_history = np.zeros(self._width)
        self._lock = threading.Lock()
        self._running = False
        self._stop_event = threading.Event()
        self._thread = None
        self._audio_chunk = np.zeros(_CHUNK, dtype=np.float32)
        self._error: str | None = None

        self.noise_floor = s.noise_floor
        self._sample_rate = _SAMPLE_RATE
        self._analysis_cache = None
        self._level = self._bass = self._mid = self._treble = 0.0
        self._object_phase = self.rng.uniform(0, 2 * math.pi)
        self._peaks = np.zeros(self._num_bars)

        self._tiles_phase = 0.0
        self._glow_phase = 0.0
        self._glow_grid = None

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

    def set_mode(self, mode: AudioMode) -> None:
        """Select a supported mode without restarting capture; clear stale pixels."""
        AudioSettings(mode=mode)
        if mode != self.mode:
            self.buffer.clear_buffer(val=self.background)
        self.mode = mode

    def set_sensitivity(self, sensitivity: float) -> None:
        """Adjust the amplitude sensitivity multiplier."""
        self.sensitivity = AudioSettings(sensitivity=sensitivity).sensitivity

    def set_smoothing(self, smoothing: float) -> None:
        """Set release retention (0..1); attack retention is capped at 0.25."""
        self.smoothing = AudioSettings(smoothing=smoothing).smoothing

    def set_color(self, color: bool) -> None:
        """Enable or disable colorized output."""
        self.color = AudioSettings(color=color).color

    def set_bar_char(self, bar_char: str) -> None:
        """Set the character used to draw bars and fills."""
        self.bar_char = AudioSettings(bar_char=bar_char).bar_char

    def set_compact(self, compact: bool) -> None:
        """Remove the gap column between bars when True."""
        self.compact = AudioSettings(compact=compact).compact

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
        with self._lock:
            self._sample_rate = rate

        def _cb(in_data, frame_count, time_info, status):
            audio = np.frombuffer(in_data, dtype=np.float32)
            if channels > 1:
                # Preserve energy from either speaker, including opposite-phase
                # stereo, instead of silently ignoring every channel but left.
                channels_audio = audio.reshape(-1, channels)
                loudest = np.argmax(np.mean(channels_audio**2, axis=0))
                audio = channels_audio[:, loudest]
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

    def _analyze(self, audio: np.ndarray, rate: int) -> None:
        """Analyze once per tick with cached windows/bins and absolute levels."""
        audio = np.clip(
            np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0), -1, 1
        ).astype(float)
        audio -= audio.mean()  # DC offsets should not masquerade as bass.
        key = (len(audio), rate, self._num_bars)
        if self._analysis_cache is None or self._analysis_cache[0] != key:
            window = np.hanning(len(audio))
            frequencies = np.fft.rfftfreq(len(audio), 1 / rate)
            # Ease into logarithmic spacing: pure log spacing repeats the same
            # few FFT bins across much of the bass end of a typical viewport.
            edges = (
                np.geomspace(20 + 250, min(20000, rate / 2) + 250, self._num_bars + 1)
                - 250
            )
            spans = []
            for low, high in zip(edges[:-1], edges[1:]):
                lo = min(
                    len(frequencies) - 1, max(1, int(np.searchsorted(frequencies, low)))
                )
                hi = min(
                    len(frequencies),
                    max(lo + 1, int(np.searchsorted(frequencies, high))),
                )
                spans.append((lo, hi))
            self._analysis_cache = (key, window, frequencies, spans)
        _, window, frequencies, spans = self._analysis_cache
        # Sum power, not peak bins: cymbals and other broadband sounds spread
        # their energy over many individually quiet bins. Window-energy scaling
        # keeps a sine's total band amplitude close to its input peak amplitude.
        power = np.abs(np.fft.rfft(audio * window)) ** 2
        power *= 4 / max(1, len(audio) * np.sum(window**2))
        if len(audio) % 2 == 0:
            power[-1] *= 0.5  # Nyquist has no negative-frequency counterpart.

        def level(amplitude):
            db = 20 * np.log10(
                np.maximum(np.asarray(amplitude) * self.sensitivity, 1e-12)
            )
            return np.clip((db - self.noise_floor) / -self.noise_floor, 0, 1)

        def smooth(old, new):
            retention = np.where(new > old, min(self.smoothing, 0.25), self.smoothing)
            return old * retention + new * (1 - retention)

        raw = level([np.sqrt(power[lo:hi].sum()) for lo, hi in spans])
        self._bars = smooth(self._bars, raw)
        self._peaks = np.maximum(self._bars, self._peaks - 0.025)
        raw_level = float(level(np.sqrt(np.mean(audio**2))))
        bands = []
        for low, high in ((20, 250), (250, 4000), (4000, rate / 2 + 1)):
            bins = power[(frequencies >= low) & (frequencies < high)]
            bands.append(float(level(np.sqrt(bins.sum()))))
        self._level = float(smooth(self._level, raw_level))
        self._bass, self._mid, self._treble = map(
            float,
            smooth(np.array([self._bass, self._mid, self._treble]), np.array(bands)),
        )

    @staticmethod
    def _height_color(ratio: float) -> int:
        """Green → yellow → red based on magnitude (0–1)."""
        palette = (22, 28, 34, 40, 46, 118, 190, 226, 214, 196)
        return palette[min(9, max(0, int(ratio * 9)))]

    @staticmethod
    def _heat_color(ratio: float) -> int:
        """Blue → cyan → green → yellow → red heat palette (0–1)."""
        palette = (17, 18, 25, 32, 39, 45, 51, 86, 154, 226, 214, 196)
        return palette[min(11, max(0, int(ratio * 11)))]

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """Advance one simulation tick; draw only copies the persistent raster."""
        if self.mode not in _STATEFUL_MODES:
            self.buffer.clear_buffer(val=self.background)
        with self._lock:
            audio, rate = self._audio_chunk.copy(), self._sample_rate
        if self._error:
            self.buffer.clear_buffer(val=self.background)
            msg = self._error[: self._width]
            self.buffer.put_at(
                max(0, (self._width - len(msg)) // 2), self._height // 2, msg
            )
            return
        self._analyze(audio, rate)
        renderers = {
            "objects": self._render_objects,
            "tiles": self._render_tiles,
            "glow": self._render_glow,
            "bars": self._render_bars,
            "mirror": self._render_mirror,
            "waveform": self._render_waveform,
            "spectrum": self._render_spectrum,
        }
        renderers[self.mode](audio)

    def _render_objects(self, audio: np.ndarray) -> None:
        """Blocks grow from 3x3 cells to adjoining, fully filled tile regions.

        Bass controls both dimensions; mids move blocks within their remaining
        space and treble highlights their faces. Tiny viewports clip the minimum
        size. Integer tile boundaries cover odd dimensions without seams. Resize
        retains phase and needs no random draws or resources.
        """
        self._object_phase = (self._object_phase + 0.015 + self._mid * 0.12) % (
            2 * math.pi
        )
        columns, rows = max(1, self._width // 10), max(1, self._height // 5)
        palette = (238, 24, 31, 38, 45, 81, 123, 159, 195)
        color = palette[min(len(palette) - 1, int(self._level * (len(palette) - 1)))]
        body = bc("o", color=color) if self.color else "o"
        fill = bc(":", color=color) if self.color else ":"
        center = ".oO@"[min(3, int(self._level * 4))]
        center = bc(center, color=color) if self.color else center
        for row in range(rows):
            for column in range(columns):
                x0, x1 = (
                    column * self._width // columns,
                    (column + 1) * self._width // columns,
                )
                y0, y1 = row * self._height // rows, (row + 1) * self._height // rows
                tile_w, tile_h = x1 - x0, y1 - y0
                minimum_w, minimum_h = min(3, tile_w), min(3, tile_h)
                width = minimum_w + round(self._bass * (tile_w - minimum_w))
                height = minimum_h + round(self._bass * (tile_h - minimum_h))
                slack_x, slack_y = tile_w - width, tile_h - height
                phase = self._object_phase + column * 1.7 + row * 2.3
                x = x0 + round(
                    slack_x / 2
                    + math.sin(phase) * min(1.5 * (0.2 + self._mid), slack_x / 2)
                )
                y = y0 + round(
                    slack_y / 2
                    + math.cos(phase) * min(0.75 * (0.2 + self._mid), slack_y / 2)
                )
                for dy in range(height):
                    for dx in range(width):
                        edge = dx in (0, width - 1) or dy in (0, height - 1)
                        self.buffer.put_char(x + dx, y + dy, body if edge else fill)
                self.buffer.put_char(x + width // 2, y + height // 2, center)
                if self._treble > 0.25:
                    dx = round((1 + math.cos(phase * 2)) * (width - 1) / 2)
                    dy = round((1 + math.sin(phase * 2)) * (height - 1) / 2)
                    spark = bc("+", color=231) if self.color else "+"
                    self.buffer.put_char(x + dx, y + dy, spark)

    def _render_tiles(self, audio: np.ndarray) -> None:
        """Luminous frequency tiles: low bands left, high bands right."""
        self._tiles_phase = (self._tiles_phase + 0.025 + self._level * 0.1) % (
            2 * math.pi
        )
        columns, rows = max(1, self._width // 8), max(1, self._height // 4)
        for column in range(columns):
            lo = column * len(self._bars) // columns
            hi = max(lo + 1, (column + 1) * len(self._bars) // columns)
            mag = float(self._bars[min(lo, len(self._bars) - 1) : hi].max())
            if mag < 0.02:
                continue
            hue = column / max(1, columns - 1)
            for row in range(rows):
                strength = mag * (
                    0.8 + 0.2 * math.cos(self._tiles_phase + row * 0.8 + column)
                )
                red = round(5 * strength * (1 - hue))
                green = round(4 * strength)
                blue = round(5 * strength * hue)
                color = 16 + 36 * red + 6 * green + blue
                glyph = " .:-=+*#%@"[min(9, max(1, int(strength * 9)))]
                cell = f"\x1b[48;5;{color}m \x1b[0m" if self.color else glyph
                x0, x1 = (
                    column * self._width // columns,
                    (column + 1) * self._width // columns,
                )
                y0, y1 = row * self._height // rows, (row + 1) * self._height // rows
                for y in range(y0, y1 - int(y1 - y0 > 1)):
                    for x in range(x0, x1 - int(x1 - x0 > 1)):
                        self.buffer.put_char(x, y, cell)

    def _render_glow(self, audio: np.ndarray) -> None:
        """Broad bass light, moving midrange pools and sharper treble highlights."""
        self._glow_phase = (self._glow_phase + 0.008 + self._mid * 0.055) % (
            2 * math.pi
        )
        if self._glow_grid is None:
            xs = (np.arange(self._width) + 0.5) / self._width * 2 - 1
            ys = (np.arange(self._height) + 0.5) / self._height * 2 - 1
            self._glow_grid = np.meshgrid(xs, ys)
        x, y = self._glow_grid
        rgb = np.zeros((self._height, self._width, 3))
        lights = (
            (self._bass, 0.7, (1.0, 0.4, 0.04)),
            (self._mid, 0.45, (0.6, 0.15, 1.0)),
            (self._treble, 0.25, (0.05, 0.8, 1.0)),
        )
        for i, (energy, spread, color) in enumerate(lights):
            angle = self._glow_phase + i * 2 * math.pi / 3
            cx, cy = math.sin(angle) * 0.6, math.cos(angle) * 0.5
            radius = spread + energy * 0.35
            light = energy * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (radius**2))
            rgb += light[:, :, None] * np.array(color)
        rgb = np.clip(rgb, 0, 1)
        brightness = rgb.max(axis=2)
        cube = np.rint(rgb * 5).astype(int)
        colors = 16 + cube[:, :, 0] * 36 + cube[:, :, 1] * 6 + cube[:, :, 2]
        # Reuse cells within this frame; silence remains background in both styles.
        cells = {}
        for y in range(self._height):
            for x in range(self._width):
                value = float(brightness[y, x])
                if value < 0.025:
                    continue
                if self.color:
                    color = int(colors[y, x])
                    if color not in cells:
                        cells[color] = f"\x1b[48;5;{color}m \x1b[0m"
                    cell = cells[color]
                else:
                    cell = " .:-=+*#%@"[min(9, max(1, int(value * 9)))]
                self.buffer.put_char(x, y, cell)

    def _render_bars(self, audio: np.ndarray):
        """Frequency bars with a height gradient and gently falling peak caps."""
        for i, mag in enumerate(self._bars):
            x0 = i * self._width // self._num_bars
            x1 = (i + 1) * self._width // self._num_bars
            if x1 <= x0:
                continue
            gap = int(not self.compact and x1 - x0 > 1)
            height = round(min(1.0, float(mag) * self.bar_gain) * self._height)
            for offset in range(height):
                glyph = (
                    bc(
                        self.bar_char,
                        color=self._height_color(offset / max(1, self._height - 1)),
                    )
                    if self.color
                    else self.bar_char
                )
                for x in range(x0, x1 - gap):
                    self.buffer.put_char(x, self._height - 1 - offset, glyph)
            peak = round(min(1.0, float(self._peaks[i]) * self.bar_gain) * self._height)
            if peak > height and peak > 0:
                for x in range(x0, x1 - gap):
                    self.buffer.put_char(
                        x,
                        max(0, self._height - peak),
                        bc("-", color=250) if self.color else "-",
                    )

    def _render_mirror(self, audio: np.ndarray):
        middle = (self._height - 1) / 2
        for i, mag in enumerate(self._bars):
            x0, x1 = (
                i * self._width // self._num_bars,
                (i + 1) * self._width // self._num_bars,
            )
            gap = int(not self.compact and x1 - x0 > 1)
            mag = min(1.0, float(mag) * self.bar_gain)
            if mag < 0.02:
                continue
            extent = max(1, math.ceil(mag * self._height / 2))
            for y in range(self._height):
                distance = abs(y - middle)
                if distance < extent:
                    glyph = (
                        bc(
                            self.bar_char,
                            color=self._height_color(distance / max(1, middle)),
                        )
                        if self.color
                        else self.bar_char
                    )
                    for x in range(x0, x1 - gap):
                        self.buffer.put_char(x, y, glyph)

    def _render_waveform(self, audio: np.ndarray):
        """Scrolling RMS amplitude envelope: each column = one frame, scrolls left over time."""
        amp = self._level

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
                self.buffer.put_char(x, row, ch if peak > 0 and offset <= peak else bg)

    def _render_spectrum(self, audio: np.ndarray):
        """Scroll one complete frequency column; low pitches at the bottom."""
        levels = np.interp(
            np.linspace(0, 1, self._height),
            np.linspace(0, 1, len(self._bars)),
            self._bars,
        )
        for y, mag in enumerate(levels[::-1]):
            row = self.buffer.buffer[y]
            row.pop(0)
            if mag < 0.02:
                row.append(self.background)
            else:
                glyph = " .:-=+*#%@"[min(9, max(1, int(mag * 9)))]
                row.append(
                    bc(glyph, color=self._heat_color(float(mag)))
                    if self.color
                    else glyph
                )

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

    def resize(self, size: tuple[int, int]) -> None:
        """Reflow caches without reading or restarting capture.

        Existing pixels remain until the next audio update. Wave history keeps
        newest samples on the right; automatic bar counts follow the width.
        """
        resized = raster(self.buffer, size, self.background)
        width, height = size
        history = np.zeros(width)
        count = min(width, self._width)
        history[-count:] = self._wave_history[-count:]
        self._wave_history = history
        if self._auto_bars:
            count = max(1, width // 2)
            self._bars = np.interp(
                np.linspace(0, 1, count), np.linspace(0, 1, len(self._bars)), self._bars
            )
            self._num_bars = count
        self._width, self._height = width, height
        self._analysis_cache = None
        self._glow_grid = None
        self._peaks = np.zeros(self._num_bars)
        self.buffer = resized
        super().resize(size)
