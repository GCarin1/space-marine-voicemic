"""Testes utilitários do módulo devices que não exigem PortAudio."""
from __future__ import annotations

import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _stub_sounddevice(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stuba ``sounddevice`` para que `devices.py` importe sem PortAudio."""
    if "sounddevice" in sys.modules:
        return
    fake = types.ModuleType("sounddevice")
    fake.query_devices = lambda: []  # type: ignore[attr-defined]
    fake.query_hostapis = lambda i: {"name": "?"}  # type: ignore[attr-defined]
    fake.default = types.SimpleNamespace(device=None)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sounddevice", fake)


def test_coerce_handles_tuple() -> None:
    from space_marine.devices import _coerce_device_index

    assert _coerce_device_index((3, 7)) == 3


def test_coerce_handles_list() -> None:
    from space_marine.devices import _coerce_device_index

    assert _coerce_device_index([2, 5]) == 2


def test_coerce_handles_bare_int() -> None:
    from space_marine.devices import _coerce_device_index

    assert _coerce_device_index(4) == 4


def test_coerce_handles_indexable_non_sequence() -> None:
    """Simula o `_InputOutputPair` do sounddevice no Windows."""
    from space_marine.devices import _coerce_device_index

    class _Pair:
        def __init__(self, i: int, o: int) -> None:
            self._items = (i, o)

        def __getitem__(self, idx: int) -> int:
            return self._items[idx]

    assert _coerce_device_index(_Pair(9, 5)) == 9


def test_coerce_handles_none() -> None:
    from space_marine.devices import _coerce_device_index

    assert _coerce_device_index(None) is None


def test_coerce_handles_negative_default() -> None:
    from space_marine.devices import _coerce_device_index

    assert _coerce_device_index((-1, -1)) == -1
