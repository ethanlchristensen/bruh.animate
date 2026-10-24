Audio Demo
==========

Play music or a video, then run from the checkout:

.. code-block:: shell

   uv run --locked --extra audio python -m bruhanimate.demos.audio_demo

Windows uses PyAudioWPatch from the optional audio extra to capture system playback.
Keep ``--extra audio`` in the command so uv retains that dependency.

The visualizations play inside the original computer artwork from the TV demo,
with snow falling behind it at 15 updates/sec. The computer body and screen
hide flakes; changing audio modes or computer styles keeps the snow running.

Press **C** to cycle **classic → expanded → box**. Expanded keeps the original
corners, adds columns through the center, and inserts rows in the monitor's
straight sides. The bezel, keyboard, and angled screen opening expand together,
giving the audio more room without enlarging individual characters. It fits the
terminal with a small margin, so enlarge the terminal for a taller/wider screen.
Box is the rectangular computer with a monitor, stand, and keyboard.
Classic and expanded need at least 67 columns and 32 rows; smaller
terminals automatically use the rectangular frame. Enlarging the terminal
restores the original if that is your selected style.

Audio is rendered into a monitor-sized buffer. The original screen follows the
artwork's sloped edges, keeping every bar's base visible; it does not crop a
full-terminal animation. The rectangular screen grows with the terminal.
Captions and capture errors remain outside the monitor. Switching computer style
or resizing preserves the selected mode, simulation state, and capture worker.

The typed ``computer`` option accepts ``"classic"`` (default), ``"expanded"``,
or ``"box"``:

.. code-block:: python

   from bruhanimate import Buffer
   from bruhanimate.demos.audio_demo import build, run

   demo = build(Buffer(48, 120), computer="expanded")  # No device opens here.
   demo.close()
   # In your terminal: run(computer="expanded")

Use **Left** for the previous visualization and **Right** for the next. Navigation
wraps at either end. There is no automatic cycling: your selection stays active
until you press an arrow key. The current
mode and controls appear at the top. **q/Q**, **Escape**, or **Ctrl+C** quit.
Live resize preserves the selected mode and animation state. Switching closes the previous
capture worker before starting the next; no audio samples are recorded to disk.

The demo starts with **Objects**: blocks spread over the monitor. Bass
expands them from 3×3 cells until neighboring blocks touch and fill their regions.
Midrange energy moves them within the space left over, treble highlights their faces,
and volume controls brightness. Quiet audio leaves a dim, gently moving field.
The bottom line explains the selected mode's mapping to sound.

The seven modes are Objects, Tiles, Glow, Bars, Mirror, Waveform, and Spectrum.
Tiles makes a monitor-wide mosaic: low frequencies light the left columns and
high frequencies light the right, with brightness following volume in each band.
Glow blends broad amber bass pools, violet midrange pools, and smaller cyan
treble highlights; mids drive their movement. Both fade toward silence.
Bars/Mirror show low frequencies on the left, high on the right. They use a
2× display-height multiplier and fill column gaps so moderate audio occupies
more of the screen. The typed ``AudioSettings.bar_gain`` option controls height
independently of analysis; 1 restores the earlier height response. Waveform shows
volume history; Spectrum shows frequency history. See :doc:`../bruheffect/audio_effect` for
level/sensitivity settings and the removed-mode migration notes.

.. automodule:: bruhanimate.demos.audio_demo
   :members:
   :undoc-members:
   :show-inheritance:
