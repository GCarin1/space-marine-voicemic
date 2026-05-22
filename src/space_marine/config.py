"""Carrega e valida `config.yaml`."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Erro de configuração com mensagem humana."""


@dataclass(frozen=True)
class PeakSpec:
    freq: float
    gain_db: float
    q: float = 1.0


@dataclass(frozen=True)
class ShelfSpec:
    freq: float
    gain_db: float


@dataclass(frozen=True)
class CompressorSpec:
    threshold_db: float
    ratio: float
    attack_ms: float
    release_ms: float


@dataclass(frozen=True)
class EchoDamping:
    low_shelf: ShelfSpec
    mid_peak: PeakSpec
    high_shelf: ShelfSpec


@dataclass(frozen=True)
class EchoSpec:
    apply_times: int
    delay_ms: float
    feedback: float
    mix: float
    damping: EchoDamping


@dataclass(frozen=True)
class VoiceBandSpec:
    enabled: bool = True
    hp_freq: float = 110.0
    lp_freq: float = 7500.0


@dataclass(frozen=True)
class NoiseGateSpec:
    enabled: bool = True
    threshold_db: float = -38.0
    ratio: float = 10.0
    attack_ms: float = 1.0
    release_ms: float = 100.0


@dataclass(frozen=True)
class PitchSpec:
    semitones: float
    formant_compensation: PeakSpec
    realtime_enabled: bool = False
    realtime_block_size: int = 4096


@dataclass(frozen=True)
class HomeTheaterSpec:
    low_shelf: ShelfSpec
    high_shelf: ShelfSpec


@dataclass(frozen=True)
class BrightAndPunchySpec:
    compressor: CompressorSpec
    presence: PeakSpec


@dataclass(frozen=True)
class LimiterSpec:
    threshold_db: float
    release_ms: float


@dataclass(frozen=True)
class SpaceMarineConfig:
    sample_rate: int
    block_size: int
    voice_band: VoiceBandSpec
    noise_gate: NoiseGateSpec
    pitch: PitchSpec
    echo: EchoSpec
    fat_snare: list[PeakSpec]
    home_theater: HomeTheaterSpec
    boomy_kick: PeakSpec
    bright_and_punchy: BrightAndPunchySpec
    possible_bass: ShelfSpec
    subtle_clarity: PeakSpec
    deesser: PeakSpec
    limiter: LimiterSpec
    source_path: Path = field(default=Path("config.yaml"))


_REQUIRED_TOP_LEVEL = (
    "sample_rate",
    "block_size",
    "pitch",
    "echo",
    "fat_snare",
    "home_theater",
    "boomy_kick",
    "bright_and_punchy",
    "possible_bass",
    "subtle_clarity",
    "deesser",
    "limiter",
)


def _require(d: dict[str, Any], key: str, ctx: str) -> Any:
    if not isinstance(d, dict) or key not in d:
        raise ConfigError(f"Campo obrigatório ausente: '{ctx}.{key}'" if ctx else f"Campo obrigatório ausente: '{key}'")
    return d[key]


def _peak(d: Any, ctx: str) -> PeakSpec:
    if not isinstance(d, dict):
        raise ConfigError(f"'{ctx}' deve ser um mapeamento com freq/gain_db/q")
    return PeakSpec(
        freq=float(_require(d, "freq", ctx)),
        gain_db=float(_require(d, "gain_db", ctx)),
        q=float(d.get("q", 1.0)),
    )


def _shelf(d: Any, ctx: str) -> ShelfSpec:
    if not isinstance(d, dict):
        raise ConfigError(f"'{ctx}' deve ser um mapeamento com freq/gain_db")
    return ShelfSpec(
        freq=float(_require(d, "freq", ctx)),
        gain_db=float(_require(d, "gain_db", ctx)),
    )


def load_config(path: str | Path) -> SpaceMarineConfig:
    """Carrega e valida o YAML. Levanta ``ConfigError`` em qualquer erro."""
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Arquivo de config não encontrado: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML malformado em {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"Conteúdo de {path} deve ser um mapeamento YAML no topo")

    for key in _REQUIRED_TOP_LEVEL:
        if key not in raw:
            raise ConfigError(f"Campo obrigatório ausente: '{key}'")

    # voice_band e noise_gate são opcionais pra não quebrar configs antigos
    vb_raw = raw.get("voice_band") or {}
    if not isinstance(vb_raw, dict):
        raise ConfigError("'voice_band' deve ser um mapeamento")
    voice_band = VoiceBandSpec(
        enabled=bool(vb_raw.get("enabled", True)),
        hp_freq=float(vb_raw.get("hp_freq", 110.0)),
        lp_freq=float(vb_raw.get("lp_freq", 7500.0)),
    )

    ng_raw = raw.get("noise_gate") or {}
    if not isinstance(ng_raw, dict):
        raise ConfigError("'noise_gate' deve ser um mapeamento")
    noise_gate = NoiseGateSpec(
        enabled=bool(ng_raw.get("enabled", True)),
        threshold_db=float(ng_raw.get("threshold_db", -38.0)),
        ratio=float(ng_raw.get("ratio", 10.0)),
        attack_ms=float(ng_raw.get("attack_ms", 1.0)),
        release_ms=float(ng_raw.get("release_ms", 100.0)),
    )

    pitch_raw = raw["pitch"]
    pitch = PitchSpec(
        semitones=float(_require(pitch_raw, "semitones", "pitch")),
        formant_compensation=_peak(
            _require(pitch_raw, "formant_compensation", "pitch"),
            "pitch.formant_compensation",
        ),
        realtime_enabled=bool(pitch_raw.get("realtime_enabled", False)),
        realtime_block_size=int(pitch_raw.get("realtime_block_size", 4096)),
    )

    echo_raw = raw["echo"]
    damping_raw = _require(echo_raw, "damping", "echo")
    echo = EchoSpec(
        apply_times=int(_require(echo_raw, "apply_times", "echo")),
        delay_ms=float(_require(echo_raw, "delay_ms", "echo")),
        feedback=float(_require(echo_raw, "feedback", "echo")),
        mix=float(_require(echo_raw, "mix", "echo")),
        damping=EchoDamping(
            low_shelf=_shelf(_require(damping_raw, "low_shelf", "echo.damping"), "echo.damping.low_shelf"),
            mid_peak=_peak(_require(damping_raw, "mid_peak", "echo.damping"), "echo.damping.mid_peak"),
            high_shelf=_shelf(_require(damping_raw, "high_shelf", "echo.damping"), "echo.damping.high_shelf"),
        ),
    )

    fat_snare_raw = raw["fat_snare"]
    if not isinstance(fat_snare_raw, list) or not fat_snare_raw:
        raise ConfigError("'fat_snare' deve ser uma lista não-vazia de PeakFilters")
    fat_snare = [_peak(item, f"fat_snare[{i}]") for i, item in enumerate(fat_snare_raw)]

    home_theater_raw = raw["home_theater"]
    home_theater = HomeTheaterSpec(
        low_shelf=_shelf(_require(home_theater_raw, "low_shelf", "home_theater"), "home_theater.low_shelf"),
        high_shelf=_shelf(_require(home_theater_raw, "high_shelf", "home_theater"), "home_theater.high_shelf"),
    )

    boomy_kick = _peak(raw["boomy_kick"], "boomy_kick")

    bp_raw = raw["bright_and_punchy"]
    comp_raw = _require(bp_raw, "compressor", "bright_and_punchy")
    bright_and_punchy = BrightAndPunchySpec(
        compressor=CompressorSpec(
            threshold_db=float(_require(comp_raw, "threshold_db", "bright_and_punchy.compressor")),
            ratio=float(_require(comp_raw, "ratio", "bright_and_punchy.compressor")),
            attack_ms=float(_require(comp_raw, "attack_ms", "bright_and_punchy.compressor")),
            release_ms=float(_require(comp_raw, "release_ms", "bright_and_punchy.compressor")),
        ),
        presence=_peak(
            _require(bp_raw, "presence", "bright_and_punchy"),
            "bright_and_punchy.presence",
        ),
    )

    possible_bass = _shelf(raw["possible_bass"], "possible_bass")
    subtle_clarity = _peak(raw["subtle_clarity"], "subtle_clarity")
    deesser = _peak(raw["deesser"], "deesser")

    limiter_raw = raw["limiter"]
    limiter = LimiterSpec(
        threshold_db=float(_require(limiter_raw, "threshold_db", "limiter")),
        release_ms=float(_require(limiter_raw, "release_ms", "limiter")),
    )

    return SpaceMarineConfig(
        sample_rate=int(raw["sample_rate"]),
        block_size=int(raw["block_size"]),
        voice_band=voice_band,
        noise_gate=noise_gate,
        pitch=pitch,
        echo=echo,
        fat_snare=fat_snare,
        home_theater=home_theater,
        boomy_kick=boomy_kick,
        bright_and_punchy=bright_and_punchy,
        possible_bass=possible_bass,
        subtle_clarity=subtle_clarity,
        deesser=deesser,
        limiter=limiter,
        source_path=path,
    )
