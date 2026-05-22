<div align="center">

<img src="img/GH_Icons_SpaceMarines2-300x300.png" alt="Space Marine helmet" width="180" />

# Space Marine Voice

**Real-time voice changer that turns your voice into a Warhammer 40k Astartes.**

[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![pedalboard](https://img.shields.io/badge/DSP-pedalboard-1DB954.svg)](https://github.com/spotify/pedalboard)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D6.svg)](https://vb-audio.com/Cable/)
[![Tests](https://img.shields.io/badge/tests-9%20passing-brightgreen.svg)](#-tests)
[![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)](#-license)

CLI · Python 3.11+ · `pedalboard` · `sounddevice` · `typer` · `rich`

</div>

---

## Table of contents

- [Overview](#-overview)
- [Demo (effects chain)](#-demo-effects-chain)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [Usage](#-usage)
- [Setting up Discord (or OBS, games…)](#-setting-up-discord-or-obs-games)
- [The 9-effect chain](#-the-9-effect-chain)
- [Customization (`config.yaml`)](#-customization-configyaml)
- [Architecture](#-architecture)
- [Tests](#-tests)
- [Known limitations](#-known-limitations)
- [Contributing](#-contributing)
- [Credits](#-credits)
- [License](#-license)

---

## Overview

`space-marine` is a **real-time** voice changer that applies a fixed DSP
chain to your voice — modeled faithfully on the Adobe Audition tutorial
for the Astartes sound (Space Marine 2 / official cinematics) — and routes
the processed audio to a virtual device (**VB-CABLE**), ready to be picked
up as a microphone by Discord, OBS, games, Zoom, etc.

> **One effect, fixed.** No robot, demon, or alien presets.
> No AI cloning. Just the aesthetic of a sealed helmet, a deep voice, and
> metallic resonance.

### Features

- **Low latency** — target < 30 ms (configurable, default `block_size=256` @ 44.1 kHz ≈ 5.8 ms per block)
- **Faithful DSP chain** — 9 stages + limiter, in the exact order of the tutorial
- **100% configurable via YAML** — edit and re-run, no code changes
- **Auto-detects VB-CABLE** — if not installed, fails with a clear message
- **Tested** — 9 tests covering loader, validation, and the DSP chain
- **Clean CLI** — `devices`, `run`, `process`, `show-chain` with `rich`

---

## Demo (effects chain)

```text
$ space-marine show-chain
Space Marine chain · config.yaml
├── 1. Pitch shift · semitones=-1.0, formant +1.5 dB @ 500.0 Hz
├── 2. Echo x2 · delay=28.0 ms, fb=0.6, mix=0.5
│   ├── low_shelf -3.0 dB @ 200.0 Hz
│   ├── mid_peak -4.0 dB @ 3000.0 Hz (q=1.0)
│   └── high_shelf -7.0 dB @ 7000.0 Hz
├── 3. Fat Snare
│   ├── peak +4.0 dB @ 200.0 Hz (q=1.0)
│   └── peak +2.0 dB @ 5000.0 Hz (q=1.2)
├── 4. Home Theater
│   ├── low_shelf +4.0 dB @ 80.0 Hz
│   └── high_shelf +2.0 dB @ 10000.0 Hz
├── 5. Boomy Kick · peak +5.0 dB @ 70.0 Hz (q=0.8)
├── 6. Bright and Punchy
│   ├── compressor th=-18.0 dB, ratio=3.5, atk=5.0 ms, rel=80.0 ms
│   └── presence peak +3.0 dB @ 4000.0 Hz (q=1.0)
├── 7. Possible Bass · low_shelf +3.0 dB @ 120.0 Hz
├── 8. Subtle Clarity · peak +2.0 dB @ 6000.0 Hz (q=1.5)
├── 9. DeEsser Light · peak -3.0 dB @ 7000.0 Hz (q=3.0)
└── Limiter · threshold=-1.0 dB, release=60.0 ms
```

---

## Requirements

| Requirement                        | Version / Source                                                  |
|------------------------------------|-------------------------------------------------------------------|
| **Python**                         | 3.11 or higher                                                    |
| **Operating system**               | Windows (tested); macOS/Linux work for offline `process`          |
| **VB-CABLE Virtual Audio Device**  | Free · <https://vb-audio.com/Cable/> · **reboot after install**   |
| **PortAudio**                      | Ships with `sounddevice` on Windows; on Linux: `apt install libportaudio2` |

> The program **does not install** VB-CABLE — it only detects it. If not
> found, it aborts with a clear message pointing to the download link.

---

## Installation

```bash
# 1. Clone
git clone https://github.com/GCarin1/space-marine-voicemic.git
cd space-marine-voicemic

# 2. (Recommended) Virtual environment
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

# 3. Install in editable mode (recommended — registers the `space-marine` command)
pip install -e .

# 4. (Optional) Test dependencies
pip install -e .[dev]
```

> If you prefer the `requirements.txt` style, there is one at the project root:
> ```bash
> pip install -r requirements.txt          # runtime
> pip install -r requirements-dev.txt      # runtime + pytest
> ```
> Note that this mode **does not** register the `space-marine` command on
> PATH; use `python -m space_marine.cli ...` or prefer `pip install -e .`.

After installing in editable mode, the `space-marine` command becomes available on PATH.

---

## Usage

### List audio devices

```bash
space-marine devices
```

Shows a table with index, name, input/output channels, and API for each
device. Use this to find the index of your microphone.

### Run in real time (typical case)

```bash
space-marine run
```

Auto-detects your default microphone as **input** and the `CABLE Input`
of VB-CABLE as **output**. Speak, and your processed voice goes to the
virtual cable. Press `Ctrl-C` to stop.

### Force specific devices

```bash
space-marine run --input 1 --output 7
```

Useful if you have multiple interfaces or want to route to a device
other than VB-CABLE (e.g., to monitor directly through headphones).

### Process a `.wav` file offline

```bash
space-marine process my_voice.wav my_voice_space_marine.wav
```

Applies the entire chain to the file. Great for testing configurations
without speaking live.

### Inspect the loaded chain

```bash
space-marine show-chain
```

Prints the effects tree with all parameters read from `config.yaml` —
verify what is about to run before opening the stream.

### Debug

In any command, pass `--debug` to see the full stack trace on error.
Without `--debug`, errors appear as short, human-friendly messages.

---

## Setting up Discord (or OBS, games…)

After installing VB-CABLE and running `space-marine run`:

1. **Discord** → User Settings → **Voice & Video**
2. **Input Device** → select **`CABLE Output (VB-Audio Virtual Cable)`**
3. (Optional) To **hear yourself** while speaking:
   - Windows: Sound Panel → **Recording** tab → `CABLE Output` →
     Properties → **Listen** tab → check "Listen to this device" →
     play back through your **headphones** (never speakers, it will
     cause feedback).

The same logic applies to OBS (Mic/Aux Audio = `CABLE Output`), games
with mic selection, Zoom, Google Meet, etc.

---

## The 9-effect chain

The order faithfully replicates the Adobe Audition tutorial. All
parameters are editable in `config.yaml`.

| #  | Stage                  | DSP                                          | Purpose                                                        |
|----|------------------------|----------------------------------------------|----------------------------------------------------------------|
| 1  | **Lower Pitch**        | `PitchShift(-1 st)` + peak +1.5 dB @ 500 Hz  | Deeper voice; formant boost to avoid the "giant rat" effect    |
| 2  | **Echo x2**            | `Delay(28 ms, fb=0.6, mix=0.5)` + EQ damping | **Heart of the sound**: sealed-helmet resonance                |
| 3  | **Fat Snare**          | Peak +4 dB @ 200 Hz, +2 dB @ 5 kHz           | Body reinforcement                                             |
| 4  | **Home Theater**       | LowShelf +4 dB @ 80 Hz, HighShelf +2 dB @ 10 kHz | Simulates large cabinet / sub + air                        |
| 5  | **Boomy Kick**         | Peak +5 dB @ 70 Hz, q=0.8                    | Weight in kick-drum frequencies                                |
| 6  | **Bright and Punchy**  | `Compressor(-18 dB, 3.5:1)` + peak +3 dB @ 4 kHz | Compression + vocal presence                               |
| 7  | **Possible Bass**      | LowShelf +3 dB @ 120 Hz                      | Sub-bass reinforcement                                         |
| 8  | **Subtle Clarity**     | Peak +2 dB @ 6 kHz, q=1.5                    | Articulation                                                   |
| 9  | **DeEsser Light**      | Peak -3 dB @ 7 kHz, q=3.0                    | Attenuates sibilance                                           |
| —  | **Limiter**            | `Limiter(threshold=-1 dB)`                   | Locks output at -1 dBFS — nothing clips                        |

> **About Echo x2:** each repetition is followed by a low-shelf /
> mid-peak / high-shelf trio that approximates the "Successive Echo
> Equalization" of Audition's *Shower* preset — it darkens the repeats
> and gives the claustrophobic timbre of an armored helmet.

---

## Customization (`config.yaml`)

All chain behavior lives in `config.yaml` at the project root. Edit
values and run `space-marine run` again — no need to restart anything
besides the program itself.

Examples:

```yaml
# Deeper voice (careful, can turn cartoonish below -3)
pitch:
  semitones: -2

# More "cathedral" echo
echo:
  apply_times: 3
  delay_ms: 45
  feedback: 0.65

# Lower latency (costs CPU; default 256 is comfortable)
block_size: 128   # ~2.9 ms per block at 44.1 kHz
```

After editing, validate with:

```bash
space-marine show-chain
```

If the YAML has an error, the message points exactly to the missing or
invalid field.

---

## Architecture

```
space-marine-voicemic/
├── config.yaml                  # Chain parameters (editable)
├── prompt.md                    # Original prompt that spawned the project
├── memoria.md                   # Development diary
├── pyproject.toml               # Package + metadata + entry point
├── requirements.txt             # Runtime dependencies (alternative to install -e .)
├── requirements-dev.txt         # Runtime + pytest
├── LICENSE
├── README.md
├── src/space_marine/
│   ├── __init__.py
│   ├── cli.py                   # Typer + rich — commands
│   ├── audio_engine.py          # sounddevice.Stream + process_file
│   ├── effects.py               # build_pedalboard(cfg) → Pedalboard
│   ├── devices.py               # Mic and VB-CABLE detection
│   └── config.py                # YAML loader/validator
└── tests/
    ├── test_config.py
    └── test_effects.py
```

**Real-time flow:**

```
[Microphone] → sounddevice.Stream → callback ─┐
                                              ▼
                              board(indata, sr, reset=False)
                                              │
                                              ▼
                              sounddevice.Stream → [CABLE Input]
                                                        │
                                                        ▼
                                                  [Discord / OBS]
                                                  reads CABLE Output
```

> `reset=False` is **critical**: it ensures the Echo tail is not
> truncated each block, preserving the metallic resonance.

---

## Tests

```bash
pip install -e .[dev]
pytest -v
```

The suite covers:

- **`test_config.py`** — malformed YAML produces a clear error; missing
  required fields name the field; the default config loads.
- **`test_effects.py`** — chain preserves sample count, RMS > threshold,
  peak ≤ 1.0 (no clipping), `pitch.semitones=-1` shifts the FFT
  fundamental in the expected direction.

---

## Known limitations

- **Pitch shift disabled in realtime by default.** `pedalboard.PitchShift`
  buffers audio internally and only releases it with `reset=True` —
  behavior documented by Spotify. This makes it unusable in streams.
  Adopted solution: in `space-marine run`, stage 1 is **skipped**; in
  `space-marine process` (offline) it is applied normally (it works
  perfectly there because the entire audio is fed at once). The formant
  boost (+1.5 dB @ 500 Hz) is kept in both modes. To force pitch shift
  in realtime, set `pitch.realtime_enabled: true` in `config.yaml` —
  prepared for >1 s of initial silence.
- **Latency depends on hostapi (Windows).** WASAPI typically gives 5–20 ms;
  DirectSound goes to 200+ ms; MME is the worst case. The auto-detect
  prefers WASAPI when possible. If running with manual `--input/--output`,
  pick indices with API "Windows WASAPI" (run `space-marine devices`).
- **Formants are not preserved** by the original `PitchShift`; the 500 Hz
  peak filter partially compensates. For real preservation you would
  need a phase vocoder or an external VST plugin.
- **Approximate DeEsser.** Implemented as a narrow -3 dB peak filter
  @ 7 kHz. Works for normal speech; may not be enough on very sibilant
  mics.
- **Mono.** The chain works on a single channel — voice is mono in
  practice.
- **VB-CABLE is Windows-only** (officially). macOS can use BlackHole or
  Loopback; just point `--output` at the equivalent index.

---

## Contributing

1. Fork → branch (`feat/my-feature` or `fix/some-bug`)
2. `pip install -e .[dev]`
3. Make sure `pytest -v` passes
4. Type hints on new code, short docstrings
5. Pull request describing **what** changed and **why**

### Style

- **No extra presets** (the project is deliberately a single effect)
- **No GUI** (CLI by design)
- **Errors become human messages**, stack trace only with `--debug`

---

## Credits

- Effects chain adapted from the **Adobe Audition → Space Marine** tutorial
- Built on [`pedalboard`](https://github.com/spotify/pedalboard) (Spotify)
- Real-time I/O via [`sounddevice`](https://python-sounddevice.readthedocs.io/) (PortAudio)
- Virtual routing via [VB-CABLE](https://vb-audio.com/Cable/) (VB-Audio Software)
- **Warhammer 40,000**, **Space Marine**, and **Astartes** are registered
  trademarks of Games Workshop Ltd. This project is an unofficial fan
  work, with no affiliation to Games Workshop or Adobe.

---

## License

[MIT](LICENSE) — use, modify, distribute. No warranties.

<div align="center">

<img src="img/GH_Icons_SpaceMarines2-300x300.png" alt="Space Marine helmet" width="80" />

**For the Emperor.**

</div>
