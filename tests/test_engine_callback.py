"""Testes do callback do RealtimeEngine sem precisar de PortAudio."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from space_marine.audio_engine import RealtimeEngine
from space_marine.config import load_config


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "config.yaml"


def _make_engine() -> RealtimeEngine:
    cfg = load_config(DEFAULT_CONFIG)
    # input/output device irrelevantes — não vamos chamar open()
    return RealtimeEngine(cfg, input_device=0, output_device=0)


def test_callback_handles_pitchshift_priming_silence() -> None:
    """Os primeiros blocos podem sair vazios; o callback deve produzir
    `frames` samples (silêncio) sem crashar."""
    engine = _make_engine()
    frames = engine.cfg.block_size

    indata = np.zeros((frames, 1), dtype=np.float32)
    outdata = np.full((frames, 1), 7.0, dtype=np.float32)  # canary

    # roda vários blocos seguidos — replica o cenário real onde os
    # primeiros vêm com < frames samples por causa da latência interna
    # do PitchShift.
    for _ in range(8):
        engine._callback(indata, outdata, frames, None, None)
        assert outdata.shape == (frames, 1)
        # nenhuma posição ficou com o canary 7.0 (todas foram escritas)
        assert not np.any(outdata == 7.0)


def test_callback_with_real_signal_outputs_audio() -> None:
    """Depois de alguns blocos de aquecimento, o FIFO deve estar cheio
    e o output deve conter áudio não-trivial."""
    engine = _make_engine()
    frames = engine.cfg.block_size
    sr = engine.cfg.sample_rate

    # Sinal contínuo — fatiamos em blocos consecutivos para simular o
    # fluxo real do PortAudio (sem descontinuidade entre blocos, que
    # confundiria o phase vocoder do PitchShift).
    total_blocks = 80
    n = frames * total_blocks
    rng = np.random.default_rng(0)
    t = np.arange(n) / sr
    full = (0.3 * np.sin(2 * np.pi * 200 * t) + 0.02 * rng.standard_normal(n)).astype(np.float32)

    outdata = np.zeros((frames, 1), dtype=np.float32)
    rms_blocks: list[float] = []
    for b in range(total_blocks):
        chunk = full[b * frames : (b + 1) * frames].reshape(-1, 1)
        engine._callback(chunk, outdata, frames, None, None)
        rms_blocks.append(float(np.sqrt(np.mean(outdata**2))))

    # pelo menos um bloco no final deve ter sinal de verdade
    assert max(rms_blocks[-20:]) > 1e-3, f"Sem sinal no final do warmup; rms={rms_blocks[-20:]}"


def test_callback_handles_mono_outdata() -> None:
    """Stream pode entregar outdata 1D em alguns cenários — não pode crashar."""
    engine = _make_engine()
    frames = engine.cfg.block_size
    indata = np.zeros((frames, 1), dtype=np.float32)
    outdata = np.zeros(frames, dtype=np.float32)
    engine._callback(indata, outdata, frames, None, None)
    assert outdata.shape == (frames,)


def test_callback_handles_oversized_processed_output() -> None:
    """Se a Pedalboard devolver MAIS samples que o esperado, o FIFO segura
    o excedente para o próximo callback (não perde áudio)."""
    engine = _make_engine()
    frames = engine.cfg.block_size
    indata = np.zeros((frames, 1), dtype=np.float32)
    outdata = np.zeros((frames, 1), dtype=np.float32)

    # roda muitos blocos — em algum momento o FIFO acumula. Apenas garante
    # que não crasha e produz outputs do tamanho certo.
    for _ in range(60):
        engine._callback(indata, outdata, frames, None, None)
        assert outdata.shape == (frames, 1)
