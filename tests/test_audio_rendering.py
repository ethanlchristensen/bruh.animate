"""Deterministic synthetic audio: these tests do not open capture hardware."""

from types import SimpleNamespace
from typing import get_args
from unittest.mock import Mock

import numpy as np
import pytest

from bruhanimate import AudioEffect, AudioMode, AudioSettings, Buffer, effects
from bruhanimate.bruheffect import audio_effect
from bruhanimate.effects import AudioPreset


def tone(frequency=1000, amplitude=0.3, rate=44100):
    return (amplitude * np.sin(2 * np.pi * frequency * np.arange(1024) / rate)).astype(
        np.float32
    )


def effect(mode="bars", **settings):
    return AudioEffect(
        Buffer(24, 80), " ", AudioSettings(mode=mode, seed=42, **settings)
    )


def tick(animation, audio):
    animation._audio_chunk = audio.copy()
    animation.update(1 / 30)


def treble_noise(rms=0.008, rate=44100):
    """Energy spread across treble bins, unlike a single synthetic sine."""
    signal = np.random.default_rng(42).normal(size=1024)
    spectrum = np.fft.rfft(signal)
    spectrum[np.fft.rfftfreq(1024, 1 / rate) < 4000] = 0
    signal = np.fft.irfft(spectrum, n=1024)
    return signal * rms / np.sqrt(np.mean(signal**2))


@pytest.mark.parametrize("rate", [44100, 48000])
def test_bass_heavy_mix_keeps_quiet_mids_and_diffuse_treble_visible(rate):
    obj = effect(smoothing=0)
    obj._sample_rate = rate
    signal = tone(100, 0.3, rate) + tone(1200, 0.015, rate) + treble_noise(rate=rate)
    tick(obj, signal)
    assert obj._bass > obj._mid > 0.35
    assert 0.3 < obj._treble < obj._bass
    # Even with much stronger bass, the right-hand bars paint several rows.
    assert np.count_nonzero(obj._bars[-10:] > 0.12) >= 8
    loud_bars, loud_treble = obj._bars.copy(), obj._treble
    tick(obj, signal * 0.1)
    assert obj._treble < loud_treble - 0.25
    assert np.all(obj._bars <= loud_bars)


@pytest.mark.parametrize("rate", [44100, 48000])
def test_diffuse_and_tonal_treble_with_equal_energy_have_similar_response(rate):
    obj = effect(smoothing=0, noise_floor=-55)
    obj._sample_rate = rate
    tick(obj, tone(8000, 0.02 * np.sqrt(2), rate))
    tonal = obj._treble
    tick(obj, treble_noise(rms=0.02, rate=rate))
    assert obj._treble == pytest.approx(tonal, abs=0.03)
    # No spectral tilt or automatic gain should light up an absent bass band.
    assert obj._bass == 0


def test_low_frequency_resolution_does_not_fill_viewport_with_repeated_bass():
    obj = effect(smoothing=0)
    tick(obj, tone(100))
    assert 1 <= np.count_nonzero(obj._bars > 0.5) <= 6
    assert np.all(obj._bars[20:] == 0)


def test_display_floor_and_sensitivity_remain_user_controlled():
    detail = effect(smoothing=0)
    gated = effect(smoothing=0, noise_floor=-40)
    muted = effect(smoothing=0, sensitivity=0)
    signal = treble_noise(rms=0.003)
    for obj in (detail, gated, muted):
        tick(obj, signal)
    assert detail._treble > 0.2
    for obj in (gated, muted):
        assert obj._treble == 0 and obj._bars.max() == 0 and obj._level == 0


def test_absolute_levels_keep_quiet_sound_quiet_and_reject_dc_and_noise():
    quiet, loud = effect(smoothing=0), effect(smoothing=0)
    tick(quiet, tone(amplitude=0.01))
    tick(loud, tone(amplitude=0.8))
    assert loud._bars.max() > quiet._bars.max() + 0.5
    assert loud._level > quiet._level + 0.5
    for signal in (np.zeros(1024), np.ones(1024) * 0.5, tone(amplitude=1e-5)):
        tick(quiet, signal)
        assert quiet._bars.max() == 0 and quiet._level == 0


@pytest.mark.parametrize(
    "frequency,band", [(100, "bass"), (1000, "mid"), (8000, "treble")]
)
def test_objects_separate_low_mid_and_high_frequency_reactions(frequency, band):
    obj = effect("objects", smoothing=0)
    tick(obj, tone(frequency))
    levels = {name: getattr(obj, "_" + name) for name in ("bass", "mid", "treble")}
    assert levels[band] > 0.6
    assert all(
        value < levels[band] - 0.2 for name, value in levels.items() if name != band
    )


def test_attack_release_peak_fall_and_cached_analysis():
    obj = effect(smoothing=0.8)
    tick(obj, tone())
    first, cache = obj._bars.copy(), obj._analysis_cache
    assert first.max() > 0.5
    tick(obj, np.zeros(1024))
    assert obj._analysis_cache is cache
    np.testing.assert_allclose(obj._bars, first * 0.8)
    assert obj._peaks.max() > obj._bars.max()
    for _ in range(100):
        tick(obj, np.zeros(1024))
    assert obj._bars.max() < 1e-8 and obj._peaks.max() < 1e-8


def test_analysis_uses_device_rate_and_invalid_samples_remain_finite():
    obj = effect(smoothing=0, num_bars=40)
    obj._sample_rate = 48000
    tick(obj, tone(6000, rate=48000))
    reference = effect(smoothing=0, num_bars=40)
    tick(reference, tone(6000))
    assert np.argmax(obj._bars) == np.argmax(reference._bars)
    tick(obj, np.full(1024, np.nan))
    assert np.isfinite(obj._bars).all() and obj._level == 0


def test_objects_fill_quadrants_and_resize_preserves_phase_and_draw_is_pure():
    obj = effect("objects", smoothing=0, color=False)
    tick(obj, tone(100) + tone(1000) * 0.4 + tone(8000) * 0.2)
    points = [
        (x, y)
        for y, row in enumerate(obj.buffer.buffer)
        for x, cell in enumerate(row)
        if cell != " "
    ]
    assert {(x >= 40, y >= 12) for x, y in points} == {
        (False, False),
        (False, True),
        (True, False),
        (True, True),
    }
    assert len(points) > 100
    assert any(cell == "+" for row in obj.buffer.buffer for cell in row)
    phase = obj._object_phase
    rng_state = obj.rng.getstate()
    first, second = Buffer(24, 80), Buffer(24, 80)
    obj.draw(first)
    obj.draw(second)
    assert first.buffer == second.buffer and obj._object_phase == phase
    obj.resize((30, 12))
    assert obj._object_phase == phase and obj.rng.getstate() == rng_state
    obj.update(1 / 30)
    assert obj.buffer.width() == 30


@pytest.mark.parametrize("size", [(80, 24), (83, 27), (1, 1), (2, 8), (11, 2)])
@pytest.mark.parametrize("color", [False, True])
def test_objects_grow_from_three_by_three_to_touching_blocks_after_resize(size, color):
    obj = effect("objects", color=color)
    obj.resize(size)
    width, height = size
    columns, rows = max(1, width // 10), max(1, height // 5)
    obj._mid, obj._treble, obj._level = 1.0, 1.0, 1.0
    counts = []
    for bass in (0, 0.5, 1):
        obj._bass = bass
        obj.buffer.clear_buffer(val=" ")
        obj._render_objects(np.zeros(1024))
        counts.append(sum(cell != " " for row in obj.buffer.buffer for cell in row))
        for row in range(rows):
            for col in range(columns):
                x0, x1 = col * width // columns, (col + 1) * width // columns
                y0, y1 = row * height // rows, (row + 1) * height // rows
                points = {
                    (x, y)
                    for y in range(y0, y1)
                    for x in range(x0, x1)
                    if obj.buffer.get_char(x, y) != " "
                }
                xs, ys = {x for x, _ in points}, {y for _, y in points}
                assert len(points) == len(xs) * len(ys)  # Filled rectangles.
                if bass == 0:
                    assert len(xs) == min(3, x1 - x0)
                    assert len(ys) == min(3, y1 - y0)
        if bass == 1:
            assert counts[-1] == width * height  # No margins or inter-block gaps.
    assert counts == sorted(counts)
    if width >= 3 and height >= 3:
        assert counts[0] < counts[1] < counts[2]


@pytest.mark.parametrize("mode", ["bars", "mirror"])
@pytest.mark.parametrize("height", [1, 23, 24])
def test_bar_gain_fills_height_without_changing_analysis_or_amplifying_silence(
    mode, height
):
    obj = AudioEffect(
        Buffer(height, 7),
        " ",
        AudioSettings(mode=mode, num_bars=1, compact=True, color=False),
    )
    renderer = getattr(obj, "_render_" + mode)
    counts = []
    for level in (0, 0.2, 0.4, 0.5, 1):
        obj._bars[:] = level
        obj.buffer.clear_buffer(val=" ")
        renderer(np.zeros(1024))
        counts.append(sum(row[0] != " " for row in obj.buffer.buffer))
        assert obj._bars[0] == level  # Display gain never feeds back into DSP.
        if mode == "mirror":
            assert obj.buffer.buffer == obj.buffer.buffer[::-1]
    assert counts[0] == 0
    assert counts == sorted(counts)
    assert counts[-2:] == [height, height]
    assert counts[2] >= round(height * 0.8)
    obj.bar_gain = 0
    obj._peaks[:] = 1
    obj.buffer.clear_buffer(val=" ")
    renderer(np.zeros(1024))
    assert all(cell == " " for row in obj.buffer.buffer for cell in row)


def test_bar_gain_scales_peak_caps_and_can_restore_original_height():
    obj = effect(color=False, compact=True, num_bars=1, bar_gain=1)
    obj._bars[:] = 0.25
    obj._peaks[:] = 0.5
    obj._render_bars(np.zeros(1024))
    assert sum(row[0] == "|" for row in obj.buffer.buffer) == 6
    assert obj.buffer.get_char(0, 12) == "-"
    obj.bar_gain = 2
    obj.buffer.clear_buffer(val=" ")
    obj._render_bars(np.zeros(1024))
    assert sum(row[0] == "|" for row in obj.buffer.buffer) == 12
    assert obj.buffer.get_char(0, 0) == "-"
    for value in (-1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            AudioSettings(bar_gain=value)


@pytest.mark.parametrize("mode", ["bars", "mirror"])
def test_narrow_bars_and_odd_width_use_the_last_column(mode):
    obj = AudioEffect(
        Buffer(5, 7),
        " ",
        AudioSettings(mode=mode, num_bars=3, smoothing=0, color=False),
    )
    obj._bars[:] = 1
    obj._peaks[:] = 1
    obj.compact = True
    getattr(obj, "_render_" + mode)(np.zeros(1024))
    assert any(row[-1] != " " for row in obj.buffer.buffer)
    one = AudioEffect(Buffer(1, 1), " ", AudioSettings(mode=mode, smoothing=0))
    tick(one, tone())
    assert one.buffer.get_char(0, 0) != " "


def test_spectrogram_covers_tall_viewport_and_waveform_silence_is_blank():
    obj = AudioEffect(
        Buffer(40, 2), " ", AudioSettings(mode="spectrum", num_bars=1, color=False)
    )
    obj._bars[:] = 0.8
    obj._render_spectrum(np.zeros(1024))
    assert all(row[-1] != " " for row in obj.buffer.buffer)
    obj = effect("waveform", smoothing=0)
    tick(obj, np.zeros(1024))
    assert all(cell == " " for row in obj.buffer.buffer for cell in row)


def test_public_catalog_and_setters_reject_removed_modes():
    expected = {
        "objects",
        "bars",
        "mirror",
        "waveform",
        "spectrum",
        "tiles",
        "glow",
    }
    assert set(get_args(AudioMode)) == expected
    assert set(get_args(AudioPreset)) == expected | {"minimal"}
    assert set(effects.audio.presets()) == expected | {"minimal"}
    obj = effect()
    for mode in (
        "starfield",
        "bounce",
        "fireworks",
        "radial",
        "rain",
        "tunnel",
        "ripple",
        "vortex",
        "wave",
        "interference",
        "lightning",
        "aurora",
        "orbit",
        "orbit_gradient",
        "scope",
        "grid",
        "helix",
        "lissajous",
        "sunburst",
        "mandala",
        "comet",
        "weave",
    ):
        with pytest.raises(ValueError):
            AudioSettings(mode=mode)
        with pytest.raises(ValueError):
            obj.set_mode(mode)
    assert obj.mode == "bars"
    with pytest.raises(ValueError):
        obj.set_sensitivity(-1)
    with pytest.raises(ValueError):
        obj.set_smoothing(1.1)
    with pytest.raises(ValueError):
        AudioSettings(noise_floor=0)


def test_windows_capture_uses_right_channel_when_left_is_silent(monkeypatch):
    obj = effect()
    pa, stream = Mock(), Mock()
    pa.get_host_api_info_by_type.return_value = {"defaultOutputDevice": 0}
    pa.get_device_info_by_index.return_value = {"name": "Speakers"}
    pa.get_loopback_device_info_generator.return_value = [
        {
            "name": "Speakers [Loopback]",
            "index": 1,
            "maxInputChannels": 2,
            "defaultSampleRate": 48000,
        }
    ]
    pa.open.return_value = stream
    monkeypatch.setattr(audio_effect, "_HAS_PAW", True)
    monkeypatch.setattr(
        audio_effect,
        "_pa_mod",
        SimpleNamespace(PyAudio=lambda: pa, paWASAPI=1, paFloat32=2, paContinue=3),
    )
    obj._capture_windows()
    callback = pa.open.call_args.kwargs["stream_callback"]
    right = tone(rate=48000)
    callback(
        np.column_stack((np.zeros(1024), right)).astype(np.float32).tobytes(),
        1024,
        None,
        None,
    )
    np.testing.assert_array_equal(obj._audio_chunk, right)
    assert obj._sample_rate == 48000


def test_switching_mode_validates_before_mutation_and_clears_old_pixels():
    obj = effect("waveform")
    obj.buffer.clear_buffer(val="X")
    obj.set_mode("objects")
    assert obj._thread is None and obj.mode == "objects"
    assert all(cell == " " for row in obj.buffer.buffer for cell in row)
    before = obj.buffer.buffer.copy()
    with pytest.raises(ValueError):
        obj.set_mode("orbit")
    assert obj.mode == "objects" and obj.buffer.buffer == before


@pytest.mark.parametrize("mode", ["tiles", "glow"])
@pytest.mark.parametrize("color", [True, False])
def test_new_modes_react_to_bands_fade_to_silence_and_draw_purely(mode, color):
    bass, treble = (
        effect(mode, color=color, smoothing=0),
        effect(mode, color=color, smoothing=0),
    )
    tick(bass, tone(100))
    tick(treble, tone(8000))
    assert bass.buffer.buffer != treble.buffer.buffer
    assert any(cell != " " for row in bass.buffer.buffer for cell in row)
    first, second = Buffer(24, 80), Buffer(24, 80)
    phase = getattr(bass, f"_{mode}_phase")
    bass.draw(first)
    bass.draw(second)
    assert first.buffer == second.buffer
    assert getattr(bass, f"_{mode}_phase") == phase
    for size in ((1, 1), (39, 17), (80, 24)):
        bass.resize(size)
        assert getattr(bass, f"_{mode}_phase") == phase
        bass.update(1 / 30)
        phase = getattr(bass, f"_{mode}_phase")
        assert any(cell != " " for row in bass.buffer.buffer for cell in row)
    tick(bass, np.zeros(1024))
    assert all(cell == " " for row in bass.buffer.buffer for cell in row)


def test_tiles_frequency_position_and_glow_cover_the_viewport():
    low, high = (
        effect("tiles", color=False, smoothing=0),
        effect("tiles", color=False, smoothing=0),
    )
    tick(low, tone(100))
    tick(high, tone(8000))

    def mean_column(obj):
        return np.mean(
            [
                x
                for row in obj.buffer.buffer
                for x, cell in enumerate(row)
                if cell != " "
            ]
        )

    assert mean_column(low) < mean_column(high)
    obj = effect("glow", smoothing=0)
    tick(obj, tone(100) + tone(1000) * 0.5 + tone(8000) * 0.3)
    points = [
        (x, y)
        for y, row in enumerate(obj.buffer.buffer)
        for x, cell in enumerate(row)
        if cell != " "
    ]
    assert {(x >= 40, y >= 12) for x, y in points} == {
        (False, False),
        (False, True),
        (True, False),
        (True, True),
    }
    cache = obj._glow_grid
    obj.update(1 / 30)
    assert obj._glow_grid is cache
    obj.resize((40, 12))
    assert obj._glow_grid is None
