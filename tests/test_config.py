"""Testes do loader/validator de configuração."""
from __future__ import annotations

from pathlib import Path

import pytest

from space_marine.config import ConfigError, load_config


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "config.yaml"


def test_default_config_loads() -> None:
    cfg = load_config(DEFAULT_CONFIG)
    assert cfg.sample_rate == 44100
    assert cfg.block_size == 256
    assert cfg.pitch.semitones == -1
    assert cfg.echo.apply_times == 2
    assert cfg.echo.delay_ms == 28
    assert len(cfg.fat_snare) == 2
    assert cfg.limiter.threshold_db == -1


def test_malformed_yaml_raises_clear_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("foo: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigError) as excinfo:
        load_config(bad)
    assert "YAML malformado" in str(excinfo.value)


def test_missing_required_field_names_the_field(tmp_path: Path) -> None:
    incomplete = tmp_path / "incomplete.yaml"
    incomplete.write_text(
        """
sample_rate: 44100
block_size: 256
pitch:
  semitones: -1
  formant_compensation: { freq: 500, gain_db: 1.5, q: 1.2 }
# echo intencionalmente ausente
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError) as excinfo:
        load_config(incomplete)
    assert "echo" in str(excinfo.value)


def test_missing_nested_field_names_path(tmp_path: Path) -> None:
    src = DEFAULT_CONFIG.read_text(encoding="utf-8")
    bad = tmp_path / "no_feedback.yaml"
    # remove a linha de feedback dentro de echo
    new = "\n".join(line for line in src.splitlines() if "feedback:" not in line)
    bad.write_text(new, encoding="utf-8")
    with pytest.raises(ConfigError) as excinfo:
        load_config(bad)
    assert "feedback" in str(excinfo.value)


def test_missing_file_raises() -> None:
    with pytest.raises(ConfigError):
        load_config("/tmp/does/not/exist.yaml")
