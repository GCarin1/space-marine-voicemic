"""Loop de áudio em tempo real e processamento offline."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
import soundfile as sf
from pedalboard import Pedalboard

from .config import SpaceMarineConfig
from .effects import build_pedalboard


class RealtimeEngine:
    """Captura áudio do mic, aplica a Pedalboard e escreve no output."""

    def __init__(
        self,
        cfg: SpaceMarineConfig,
        input_device: int,
        output_device: int,
        *,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        self.cfg = cfg
        self.board: Pedalboard = build_pedalboard(cfg, realtime=True)
        self.pitch_shift_active: bool = cfg.pitch.realtime_enabled
        # Quando o PitchShift está ativo em realtime, ele precisa de blocos
        # grandes pra emitir samples — usa o block_size dedicado. Senão,
        # mantém o block_size global (baixa latência).
        self.stream_block_size: int = (
            cfg.pitch.realtime_block_size if self.pitch_shift_active else cfg.block_size
        )
        self.input_device = input_device
        self.output_device = output_device
        self._on_status = on_status or (lambda _msg: None)
        self._stream = None  # sd.Stream | None — adiamos import de sounddevice
        # FIFO de saída: PitchShift e Delay têm latência interna; em tempo
        # real os primeiros blocos saem com menos samples que entraram
        # (até zero). Sem buffer, broadcasting (0,) -> (256,) explode.
        self._out_fifo = np.zeros(0, dtype=np.float32)

    def _callback(
        self,
        indata: np.ndarray,
        outdata: np.ndarray,
        frames: int,
        time_info,  # noqa: ANN001 — assinatura imposta por sounddevice
        status,
    ) -> None:
        if status:
            self._on_status(str(status))
        # indata vem como float32 (N, channels). A cadeia trabalha mono.
        mono = indata[:, 0] if indata.ndim == 2 else indata
        processed = self.board(
            mono.astype(np.float32, copy=False),
            self.cfg.sample_rate,
            reset=False,
        ).astype(np.float32, copy=False).reshape(-1)

        # Empilha no FIFO. Se ainda não temos `frames` samples acumulados,
        # preenche o restante com silêncio (acontece só nos primeiros
        # ~poucos blocos enquanto a cadeia se acomoda).
        self._out_fifo = np.concatenate([self._out_fifo, processed])
        if self._out_fifo.size >= frames:
            chunk = self._out_fifo[:frames]
            self._out_fifo = self._out_fifo[frames:]
        else:
            chunk = np.zeros(frames, dtype=np.float32)
            if self._out_fifo.size:
                chunk[: self._out_fifo.size] = self._out_fifo
                self._out_fifo = np.zeros(0, dtype=np.float32)

        if outdata.ndim == 2:
            for ch in range(outdata.shape[1]):
                outdata[:, ch] = chunk
        else:
            outdata[:] = chunk

    def open(self) -> None:
        """Abre o stream. Use o objeto como context manager preferencialmente."""
        import sounddevice as sd

        self._stream = sd.Stream(
            samplerate=self.cfg.sample_rate,
            blocksize=self.stream_block_size,
            device=(self.input_device, self.output_device),
            channels=(1, 1),
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def close(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    @property
    def latency_ms(self) -> float:
        """Latência reportada pelo PortAudio (input + output) em milissegundos."""
        if self._stream is None:
            return float("nan")
        lat = self._stream.latency
        if isinstance(lat, (tuple, list)):
            return float(sum(lat)) * 1000.0
        return float(lat) * 1000.0

    def __enter__(self) -> "RealtimeEngine":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def process_file(input_path: str | Path, output_path: str | Path, cfg: SpaceMarineConfig) -> None:
    """Processa um WAV offline. Mantém a taxa de amostragem do input."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    audio, sr = sf.read(str(input_path), always_2d=False, dtype="float32")
    if audio.ndim == 2:
        # mistura para mono
        audio = audio.mean(axis=1).astype(np.float32, copy=False)
    board = build_pedalboard(cfg)
    processed = board(audio, sr, reset=True)
    sf.write(str(output_path), processed, sr, subtype="PCM_16")
