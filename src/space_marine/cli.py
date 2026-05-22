"""Interface de linha de comando."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from dataclasses import replace

from .config import ConfigError, SpaceMarineConfig, load_config

app = typer.Typer(
    add_completion=False,
    help="Space Marine real-time voice changer.",
    no_args_is_help=True,
)
console = Console()


DEFAULT_CONFIG = Path("config.yaml")


def _load_or_die(path: Path, debug: bool) -> SpaceMarineConfig:
    try:
        return load_config(path)
    except ConfigError as exc:
        console.print(f"[bold red]Erro de configuração:[/] {exc}")
        if debug:
            console.print_exception()
        raise typer.Exit(code=2) from exc


def _devices_table() -> Table:
    from .devices import list_devices

    table = Table(title="Dispositivos de áudio", header_style="bold cyan")
    table.add_column("#", justify="right")
    table.add_column("Nome")
    table.add_column("In", justify="right")
    table.add_column("Out", justify="right")
    table.add_column("API")
    for dev in list_devices():
        table.add_row(
            str(dev.index),
            dev.name,
            str(dev.max_input_channels),
            str(dev.max_output_channels),
            dev.hostapi,
        )
    return table


@app.command()
def devices(debug: bool = typer.Option(False, "--debug")) -> None:
    """Lista dispositivos de áudio."""
    try:
        console.print(_devices_table())
    except Exception as exc:  # noqa: BLE001
        console.print(f"[bold red]Erro ao listar dispositivos:[/] {exc}")
        if debug:
            console.print_exception()
        raise typer.Exit(code=1) from exc


@app.command(name="show-chain")
def show_chain(
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    """Exibe a cadeia de efeitos atual a partir do YAML."""
    cfg = _load_or_die(config, debug)
    tree = Tree(f"[bold]Space Marine chain[/] · {config}")

    vb = cfg.voice_band
    if vb.enabled:
        tree.add(f"0a. Voice bandpass · HPF {vb.hp_freq} Hz · LPF {vb.lp_freq} Hz")
    else:
        tree.add("0a. Voice bandpass · [yellow]desativado[/]")

    ng = cfg.noise_gate
    if ng.enabled:
        tree.add(
            f"0b. Noise gate · threshold={ng.threshold_db} dB, ratio={ng.ratio}, "
            f"atk={ng.attack_ms} ms, rel={ng.release_ms} ms"
        )
    else:
        tree.add("0b. Noise gate · [yellow]desativado[/]")

    if cfg.pitch.realtime_enabled:
        rt_note = f" [green](realtime ON, block={cfg.pitch.realtime_block_size})[/]"
    else:
        rt_note = " [yellow](só offline; use --pitch-shift no run pra ligar)[/]"
    tree.add(
        f"1. Pitch shift · semitones={cfg.pitch.semitones}, "
        f"formant +{cfg.pitch.formant_compensation.gain_db} dB @ "
        f"{cfg.pitch.formant_compensation.freq} Hz{rt_note}"
    )
    echo_node = tree.add(
        f"2. Echo x{cfg.echo.apply_times} · delay={cfg.echo.delay_ms} ms, fb={cfg.echo.feedback}, mix={cfg.echo.mix}"
    )
    echo_node.add(f"low_shelf {cfg.echo.damping.low_shelf.gain_db} dB @ {cfg.echo.damping.low_shelf.freq} Hz")
    echo_node.add(f"mid_peak {cfg.echo.damping.mid_peak.gain_db} dB @ {cfg.echo.damping.mid_peak.freq} Hz (q={cfg.echo.damping.mid_peak.q})")
    echo_node.add(f"high_shelf {cfg.echo.damping.high_shelf.gain_db} dB @ {cfg.echo.damping.high_shelf.freq} Hz")

    fs_node = tree.add("3. Fat Snare")
    for peak in cfg.fat_snare:
        fs_node.add(f"peak {peak.gain_db:+} dB @ {peak.freq} Hz (q={peak.q})")

    ht = tree.add("4. Home Theater")
    ht.add(f"low_shelf {cfg.home_theater.low_shelf.gain_db:+} dB @ {cfg.home_theater.low_shelf.freq} Hz")
    ht.add(f"high_shelf {cfg.home_theater.high_shelf.gain_db:+} dB @ {cfg.home_theater.high_shelf.freq} Hz")

    tree.add(f"5. Boomy Kick · peak {cfg.boomy_kick.gain_db:+} dB @ {cfg.boomy_kick.freq} Hz (q={cfg.boomy_kick.q})")

    bp = tree.add("6. Bright and Punchy")
    c = cfg.bright_and_punchy.compressor
    bp.add(f"compressor th={c.threshold_db} dB, ratio={c.ratio}, atk={c.attack_ms} ms, rel={c.release_ms} ms")
    pr = cfg.bright_and_punchy.presence
    bp.add(f"presence peak {pr.gain_db:+} dB @ {pr.freq} Hz (q={pr.q})")

    tree.add(f"7. Possible Bass · low_shelf {cfg.possible_bass.gain_db:+} dB @ {cfg.possible_bass.freq} Hz")
    tree.add(f"8. Subtle Clarity · peak {cfg.subtle_clarity.gain_db:+} dB @ {cfg.subtle_clarity.freq} Hz (q={cfg.subtle_clarity.q})")
    tree.add(f"9. DeEsser Light · peak {cfg.deesser.gain_db:+} dB @ {cfg.deesser.freq} Hz (q={cfg.deesser.q})")
    tree.add(f"Limiter · threshold={cfg.limiter.threshold_db} dB, release={cfg.limiter.release_ms} ms")

    console.print(tree)


@app.command()
def run(
    input: Optional[int] = typer.Option(None, "--input", "-i", help="Índice do dispositivo de entrada"),
    output: Optional[int] = typer.Option(None, "--output", "-o", help="Índice do dispositivo de saída"),
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
    pitch_shift: bool = typer.Option(
        False,
        "--pitch-shift",
        "-p",
        help="Habilita o PitchShift em realtime (som idêntico ao tutorial; "
        "aumenta o block_size pra ~93 ms — latência total ~100-150 ms).",
    ),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    """Roda o efeito Space Marine em tempo real."""
    cfg = _load_or_die(config, debug)
    if pitch_shift and not cfg.pitch.realtime_enabled:
        cfg = replace(cfg, pitch=replace(cfg.pitch, realtime_enabled=True))
    # Importa engine + devices só aqui para não puxar sounddevice/portaudio
    # em comandos que não precisam (ex.: show-chain em CI sem libs nativas).
    from .audio_engine import RealtimeEngine
    from .devices import (
        DeviceNotFoundError,
        find_default_input,
        find_vb_cable_output,
        resolve_device,
    )

    try:
        in_dev = resolve_device(input, want_input=True) if input is not None else find_default_input()
        out_dev = resolve_device(output, want_input=False) if output is not None else find_vb_cable_output()
    except DeviceNotFoundError as exc:
        console.print(f"[bold red]{exc}[/]")
        if debug:
            console.print_exception()
        raise typer.Exit(code=2) from exc

    effective_bs = cfg.pitch.realtime_block_size if cfg.pitch.realtime_enabled else cfg.block_size
    block_ms = 1000.0 * effective_bs / cfg.sample_rate
    console.print(f"[green]Input :[/] [{in_dev.index}] {in_dev.name}  ({in_dev.hostapi})")
    console.print(f"[green]Output:[/] [{out_dev.index}] {out_dev.name}  ({out_dev.hostapi})")
    console.print(
        f"[dim]sample_rate={cfg.sample_rate} Hz, block_size={effective_bs} frames "
        f"({block_ms:.1f} ms/bloco)[/]"
    )
    if cfg.pitch.realtime_enabled:
        console.print(
            f"[green]Pitch shift ativo[/] ({cfg.pitch.semitones:+g} semitons) — "
            f"som idêntico ao tutorial. Latência por bloco ~{block_ms:.0f} ms; "
            "total tipicamente 100-150 ms. Use sem o flag pra latência mínima."
        )
    else:
        console.print(
            "[yellow]Pitch shift desativado em realtime[/] (default — prioriza "
            "latência). Rode com [bold]--pitch-shift[/] (ou [bold]-p[/]) pra "
            "ligar e ter o timbre idêntico ao tutorial. O comando "
            "[bold]process[/] sempre aplica a cadeia completa."
        )
    if "directsound" in out_dev.hostapi.lower() or "mme" in out_dev.hostapi.lower():
        console.print(
            "[yellow]Dica de latência:[/] hostapi "
            f"'{out_dev.hostapi}' tem latência alta (~200 ms+). Use um "
            "dispositivo WASAPI no Windows — execute [bold]space-marine "
            "devices[/] e procure por entradas com API 'Windows WASAPI'."
        )

    def _on_status(msg: str) -> None:
        console.print(f"[yellow]stream status:[/] {msg}")

    try:
        with RealtimeEngine(cfg, in_dev.index, out_dev.index, on_status=_on_status) as engine:
            console.print(f"[bold green]Rodando.[/] Latência reportada: {engine.latency_ms:.1f} ms. Ctrl-C para parar.")
            while True:
                time.sleep(0.5)
    except KeyboardInterrupt:
        console.print("\n[dim]Encerrado.[/]")
    except Exception as exc:  # noqa: BLE001
        console.print(f"[bold red]Erro no stream:[/] {exc}")
        if debug:
            console.print_exception()
        raise typer.Exit(code=1) from exc


@app.command()
def process(
    input_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    output_path: Path = typer.Argument(...),
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    """Processa um arquivo .wav offline aplicando a cadeia."""
    cfg = _load_or_die(config, debug)
    from .audio_engine import process_file

    try:
        process_file(input_path, output_path, cfg)
        console.print(f"[green]Processado:[/] {input_path} → {output_path}")
    except Exception as exc:  # noqa: BLE001
        console.print(f"[bold red]Erro ao processar arquivo:[/] {exc}")
        if debug:
            console.print_exception()
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
