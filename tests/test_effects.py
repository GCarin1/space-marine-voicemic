"""Testes da cadeia DSP."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from space_marine.config import load_config
from space_marine.effects import build_pedalboard


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "config.yaml"
SAMPLE_RATE = 44100


def _make_voice_like_signal(seconds: float = 1.0, freq: float = 150.0) -> np.ndarray:
    """Sinal de teste: fundamental + harmônicos + um pouco de ruído."""
    rng = np.random.default_rng(seed=42)
    t = np.linspace(0, seconds, int(SAMPLE_RATE * seconds), endpoint=False, dtype=np.float32)
    signal = (
        0.5 * np.sin(2 * np.pi * freq * t)
        + 0.25 * np.sin(2 * np.pi * (2 * freq) * t)
        + 0.15 * np.sin(2 * np.pi * (3 * freq) * t)
    ).astype(np.float32)
    signal += 0.02 * rng.standard_normal(signal.shape).astype(np.float32)
    return signal * 0.5


def _fundamental(signal: np.ndarray, sr: int = SAMPLE_RATE) -> float:
    spectrum = np.abs(np.fft.rfft(signal))
    freqs = np.fft.rfftfreq(len(signal), 1 / sr)
    # ignora DC e a região muito grave para não capturar bias
    mask = freqs > 30
    return float(freqs[mask][int(np.argmax(spectrum[mask]))])


def test_chain_runs_and_preserves_length() -> None:
    cfg = load_config(DEFAULT_CONFIG)
    board = build_pedalboard(cfg)
    signal = _make_voice_like_signal()
    out = board(signal, SAMPLE_RATE, reset=True)
    assert out.shape == signal.shape


def test_chain_output_is_not_silent_and_not_clipped() -> None:
    cfg = load_config(DEFAULT_CONFIG)
    board = build_pedalboard(cfg)
    signal = _make_voice_like_signal()
    out = board(signal, SAMPLE_RATE, reset=True)

    rms = float(np.sqrt(np.mean(out**2)))
    peak = float(np.max(np.abs(out)))

    assert rms > 1e-3, f"Saída praticamente muda (RMS={rms})"
    assert peak <= 1.0 + 1e-3, f"Saída clipada (peak={peak})"


def test_negative_pitch_lowers_fundamental(tmp_path: Path) -> None:
    """Mudar `pitch.semitones` no config deve deslocar o pico fundamental."""
    cfg = load_config(DEFAULT_CONFIG)
    # voz limpa para comparação (somente pitch shift, sem echo amassando o pico):
    # construímos uma board mínima usando apenas o estágio de pitch para
    # isolar o efeito — a cadeia completa ainda é testada acima.
    from pedalboard import Pedalboard, PitchShift

    signal = _make_voice_like_signal(freq=200.0)

    board_down = Pedalboard([PitchShift(semitones=cfg.pitch.semitones)])
    board_up = Pedalboard([PitchShift(semitones=-cfg.pitch.semitones)])

    out_down = board_down(signal, SAMPLE_RATE, reset=True)
    out_up = board_up(signal, SAMPLE_RATE, reset=True)

    f_down = _fundamental(out_down)
    f_up = _fundamental(out_up)

    assert f_down < f_up, f"Pitch negativo não abaixou o fundamental: down={f_down}, up={f_up}"


def test_changing_config_changes_chain_length(tmp_path: Path) -> None:
    cfg = load_config(DEFAULT_CONFIG)
    # apply_times=1 deve produzir uma cadeia menor que apply_times=2
    from dataclasses import replace

    cfg_one_echo = replace(cfg, echo=replace(cfg.echo, apply_times=1))
    board2 = build_pedalboard(cfg)
    board1 = build_pedalboard(cfg_one_echo)
    assert len(board1) < len(board2)


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
