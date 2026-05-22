"""Detecção de dispositivos de áudio (mic e VB-CABLE)."""
from __future__ import annotations

from dataclasses import dataclass

import sounddevice as sd


class DeviceNotFoundError(RuntimeError):
    """Levantado quando um dispositivo esperado não é encontrado."""


VB_CABLE_HINT = (
    "VB-CABLE não detectado. Instale em https://vb-audio.com/Cable/ e "
    "reinicie o PC."
)


@dataclass(frozen=True)
class DeviceInfo:
    index: int
    name: str
    max_input_channels: int
    max_output_channels: int
    hostapi: str


def _hostapi_name(index: int) -> str:
    try:
        return sd.query_hostapis(index)["name"]
    except Exception:
        return "?"


def list_devices() -> list[DeviceInfo]:
    """Retorna todos os dispositivos disponíveis."""
    out: list[DeviceInfo] = []
    for i, d in enumerate(sd.query_devices()):
        out.append(
            DeviceInfo(
                index=i,
                name=str(d.get("name", "?")),
                max_input_channels=int(d.get("max_input_channels", 0)),
                max_output_channels=int(d.get("max_output_channels", 0)),
                hostapi=_hostapi_name(int(d.get("hostapi", 0))),
            )
        )
    return out


# Ordem de preferência das hostapis no Windows. WASAPI dá latência típica
# ~5–20 ms; DirectSound vai a 200+ ms; MME é o pior caso. Em macOS/Linux
# os nomes não batem e o ranking simplesmente não filtra nada.
_HOSTAPI_PRIORITY = ("wasapi", "core audio", "alsa", "jack", "directsound", "mme")


def _hostapi_rank(name: str) -> int:
    lower = name.lower()
    for i, key in enumerate(_HOSTAPI_PRIORITY):
        if key in lower:
            return i
    return len(_HOSTAPI_PRIORITY)


def find_vb_cable_output() -> DeviceInfo:
    """Localiza o dispositivo de saída do VB-CABLE ("CABLE Input").

    Prefere WASAPI por dar latência drasticamente menor que DirectSound/MME.
    """
    candidates = [
        d for d in list_devices()
        if "cable input" in d.name.lower() and d.max_output_channels > 0
    ]
    if not candidates:
        raise DeviceNotFoundError(VB_CABLE_HINT)
    candidates.sort(key=lambda d: _hostapi_rank(d.hostapi))
    return candidates[0]


def _coerce_device_index(value: object) -> int | None:
    """Normaliza ``sd.default.device`` (tupla, lista, _InputOutputPair, int) num índice.

    Em Windows o `sounddevice` devolve um `_InputOutputPair` que não é
    `tuple` nem `list` mas suporta indexação. Tratamos os três casos.
    """
    if value is None:
        return None
    # tenta acesso por índice (cobre tuple/list/_InputOutputPair)
    try:
        first = value[0]  # type: ignore[index]
    except (TypeError, KeyError, IndexError):
        first = value
    try:
        idx = int(first)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return idx


def find_default_input() -> DeviceInfo:
    """Retorna o melhor dispositivo de entrada — prefere WASAPI no Windows.

    Estratégia: pega o default do sistema e, se ele existir em outra
    hostapi de menor latência (WASAPI), prefere a versão WASAPI. Isso
    evita a armadilha do DirectSound (200+ ms) quando o usuário não
    passou ``--input``.
    """
    devices = list_devices()

    # 1) Tenta achar a *mesma* placa do default em uma hostapi melhor.
    idx = _coerce_device_index(sd.default.device)
    default_dev: DeviceInfo | None = None
    if idx is not None and 0 <= idx < len(devices) and devices[idx].max_input_channels > 0:
        default_dev = devices[idx]
        same_name = [
            d for d in devices
            if d.max_input_channels > 0 and d.name.strip().lower() == default_dev.name.strip().lower()
        ]
        if same_name:
            same_name.sort(key=lambda d: _hostapi_rank(d.hostapi))
            if _hostapi_rank(same_name[0].hostapi) < _hostapi_rank(default_dev.hostapi):
                return same_name[0]
            return default_dev

    # 2) Fallback: qualquer dispositivo com input, preferindo WASAPI e
    #    deixando o VB-CABLE de fora (não queremos capturar do próprio cabo).
    inputs = [
        d for d in devices
        if d.max_input_channels > 0 and "cable output" not in d.name.lower()
    ]
    if not inputs:
        raise DeviceNotFoundError("Nenhum dispositivo de entrada disponível.")
    inputs.sort(key=lambda d: _hostapi_rank(d.hostapi))
    return inputs[0]


def _suggest_outputs() -> list[DeviceInfo]:
    """Devices que servem como saída para o VB-CABLE (i.e. 'CABLE Input')."""
    return [
        d for d in list_devices()
        if "cable input" in d.name.lower() and d.max_output_channels > 0
    ]


def resolve_device(index: int, *, want_input: bool) -> DeviceInfo:
    """Valida um índice manual e confirma que tem canais do tipo certo."""
    devices = list_devices()
    if index < 0 or index >= len(devices):
        raise DeviceNotFoundError(f"Índice de dispositivo inválido: {index}")
    dev = devices[index]
    needed = dev.max_input_channels if want_input else dev.max_output_channels
    kind = "entrada" if want_input else "saída"
    if needed <= 0:
        msg = f"Dispositivo {index} ('{dev.name}') não tem canais de {kind}."
        # Dica específica: se o usuário escolheu "CABLE Output" como output,
        # ele provavelmente queria "CABLE Input" (o nome confunde mesmo).
        if not want_input and "cable output" in dev.name.lower():
            hints = _suggest_outputs()
            if hints:
                bullets = "\n".join(
                    f"  - {h.index}: {h.name}  ({h.hostapi})" for h in hints
                )
                msg += (
                    "\n\nDica: o nome confunde — 'CABLE Output' é onde apps "
                    "leem áudio (vira microfone do Discord). Para enviar áudio "
                    "ao VB-CABLE, use um 'CABLE Input' como --output. "
                    f"Candidatos detectados:\n{bullets}"
                )
        raise DeviceNotFoundError(msg)
    return dev
