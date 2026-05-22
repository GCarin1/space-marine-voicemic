"""Constrói a `Pedalboard` com a cadeia de efeitos Space Marine."""
from __future__ import annotations

from pedalboard import (
    Compressor,
    Delay,
    HighpassFilter,
    HighShelfFilter,
    Limiter,
    LowpassFilter,
    LowShelfFilter,
    NoiseGate,
    Pedalboard,
    PeakFilter,
    PitchShift,
    Plugin,
)

from .config import SpaceMarineConfig


def build_pedalboard(cfg: SpaceMarineConfig, *, realtime: bool = False) -> Pedalboard:
    """Monta a cadeia DSP completa a partir da configuração.

    Args:
        cfg: configuração validada.
        realtime: se True, omite estágios incompatíveis com streaming —
            atualmente apenas o ``PitchShift``, que bufferiza áudio
            internamente e nunca libera samples sem ``reset=True``.
            O estágio de compensação de formante é mantido em ambos os
            modos (ele é só um peak filter, sem latência).
    """
    plugins: list[Plugin] = []

    # 0a. Voice bandpass — corta tudo fora da banda da voz humana ANTES
    # do gate. Mata hum de rede (60/120 Hz), rumble de mesa, ventoinha
    # de PC (todos vivem abaixo de ~100 Hz) e chiado agudo de alto-falante
    # / fonte chaveada (>8 kHz). Voz inteligível mora em 100-6000 Hz —
    # o LPF em 7500 deixa folga pra sibilantes naturais sem dar passagem
    # pra ruído eletrônico. Vem ANTES do gate porque o gate decide
    # threshold no sinal já limpo dessa banda.
    if cfg.voice_band.enabled:
        plugins.append(HighpassFilter(cutoff_frequency_hz=cfg.voice_band.hp_freq))
        plugins.append(LowpassFilter(cutoff_frequency_hz=cfg.voice_band.lp_freq))

    # 0b. Noise gate — silencia o mic abaixo do threshold para que echo +
    # bass boosts a seguir não amplifiquem ruído de fundo (vent., hum,
    # chiado). Vem ANTES de tudo (mas DEPOIS do bandpass): gatear depois
    # do echo seria inútil porque a cauda já espalhou o ruído pelo bloco.
    if cfg.noise_gate.enabled:
        plugins.append(
            NoiseGate(
                threshold_db=cfg.noise_gate.threshold_db,
                ratio=cfg.noise_gate.ratio,
                attack_ms=cfg.noise_gate.attack_ms,
                release_ms=cfg.noise_gate.release_ms,
            )
        )

    # 1. Lower Pitch + compensação de formante
    if not realtime or cfg.pitch.realtime_enabled:
        plugins.append(PitchShift(semitones=cfg.pitch.semitones))
    fc = cfg.pitch.formant_compensation
    plugins.append(PeakFilter(cutoff_frequency_hz=fc.freq, gain_db=fc.gain_db, q=fc.q))

    # 2. Echo (aplicado N vezes) — coração do som de capacete
    delay_seconds = cfg.echo.delay_ms / 1000.0
    for _ in range(cfg.echo.apply_times):
        plugins.append(
            Delay(
                delay_seconds=delay_seconds,
                feedback=cfg.echo.feedback,
                mix=cfg.echo.mix,
            )
        )
        d = cfg.echo.damping
        plugins.append(LowShelfFilter(cutoff_frequency_hz=d.low_shelf.freq, gain_db=d.low_shelf.gain_db))
        plugins.append(PeakFilter(cutoff_frequency_hz=d.mid_peak.freq, gain_db=d.mid_peak.gain_db, q=d.mid_peak.q))
        plugins.append(HighShelfFilter(cutoff_frequency_hz=d.high_shelf.freq, gain_db=d.high_shelf.gain_db))

    # 3. Fat Snare
    for peak in cfg.fat_snare:
        plugins.append(PeakFilter(cutoff_frequency_hz=peak.freq, gain_db=peak.gain_db, q=peak.q))

    # 4. Home Theater
    plugins.append(
        LowShelfFilter(
            cutoff_frequency_hz=cfg.home_theater.low_shelf.freq,
            gain_db=cfg.home_theater.low_shelf.gain_db,
        )
    )
    plugins.append(
        HighShelfFilter(
            cutoff_frequency_hz=cfg.home_theater.high_shelf.freq,
            gain_db=cfg.home_theater.high_shelf.gain_db,
        )
    )

    # 5. Boomy Kick
    bk = cfg.boomy_kick
    plugins.append(PeakFilter(cutoff_frequency_hz=bk.freq, gain_db=bk.gain_db, q=bk.q))

    # 6. Bright and Punchy: compressor + presence
    c = cfg.bright_and_punchy.compressor
    plugins.append(
        Compressor(
            threshold_db=c.threshold_db,
            ratio=c.ratio,
            attack_ms=c.attack_ms,
            release_ms=c.release_ms,
        )
    )
    p = cfg.bright_and_punchy.presence
    plugins.append(PeakFilter(cutoff_frequency_hz=p.freq, gain_db=p.gain_db, q=p.q))

    # 7. Possible Bass
    pb = cfg.possible_bass
    plugins.append(LowShelfFilter(cutoff_frequency_hz=pb.freq, gain_db=pb.gain_db))

    # 8. Subtle Clarity
    sc = cfg.subtle_clarity
    plugins.append(PeakFilter(cutoff_frequency_hz=sc.freq, gain_db=sc.gain_db, q=sc.q))

    # 9. DeEsser Light (aproximação)
    de = cfg.deesser
    plugins.append(PeakFilter(cutoff_frequency_hz=de.freq, gain_db=de.gain_db, q=de.q))

    # Final: limiter anti-clipping
    plugins.append(Limiter(threshold_db=cfg.limiter.threshold_db, release_ms=cfg.limiter.release_ms))

    return Pedalboard(plugins)
