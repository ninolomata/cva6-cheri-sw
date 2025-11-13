from __future__ import annotations

import typer
from rich.console import Console
from pathlib import Path

from . import build, fpga, sw, sdcard, boot
from .config import CONFIG

app = typer.Typer(help="CheriBSD / Bao baremetal demo on CVA6-CHERI (Genesys2 FPGA)")
console = Console()


@app.command()
def clone():
    """Clone all upstream repositories (cheribuild, cheri-cva6, opensbi, u-boot, bao, baremetal demo)."""
    build.clone_all()


@app.command("list-configs")
def list_configs():
    """List available CVA6 FPGA configurations."""
    console.print("[bold]Available CVA6 FPGA configs:[/]")
    default = CONFIG.cva6_default_name
    for name, cfg in CONFIG.cva6_configs.items():
        marker = "[green](default)[/]" if name == default else ""
        console.print(f"  - [cyan]{name}[/] {marker}")
        console.print(f"      board: {cfg.board}")
        console.print(f"      target: {cfg.target}")
        console.print(f"      desc: {cfg.description}")


@app.command("list-sw")
def list_sw():
    """List available software targets (CheriBSD, Bao+baremetal, baremetal)."""
    console.print("[bold]Available software targets:[/]")
    default = CONFIG.sw_default_name
    for name, tgt in CONFIG.sw_targets.items():
        marker = "[green](default)[/]" if name == default else ""
        console.print(f"  - [cyan]{name}[/] {marker}")
        console.print(f"      kind: {tgt.kind}")
        if tgt.kind == "cheribsd":
            console.print(f"      cheribuild target: {tgt.params['cheribuild_target']}")
        elif tgt.kind == "bao_bundle":
            console.print(f"      bao config: {tgt.params['bao_config']}")
        elif tgt.kind == "baremetal":
            console.print(f"      repo: {tgt.params['app_repo']}")


@app.command("build-sw")
def build_sw_cmd(
    target: str = typer.Option(
        None,
        "--target",
        "-t",
        help="Software target name (see 'cheridemo list-sw'). "
             "If omitted, uses the default from the config.",
    ),
    jobs: int = typer.Option(
        8,
        "--jobs",
        "-j",
        help="Number of parallel jobs for the build.",
    ),
):
    """
    Build a software stack:

      - For kind 'baremetal': baremetal app + OpenSBI (with payload),
        artifacts in external/output/<target-name>/
      - Other kinds: behavior depends on sw.build_sw implementation.
    """
    boot.build_sw(target_name=target, jobs=jobs)


@app.command("build-fpga")
def build_fpga_cmd(
    config: str = typer.Option(
        None,
        "--config",
        "-c",
        help="CVA6 FPGA config name (see 'cheridemo list-configs')",
    ),
    jobs: int = typer.Option(8, "--jobs", "-j", help="Number of parallel jobs"),
):
    """Build FPGA bitstream for CVA6-CHERI on Genesys2."""
    fpga.build_fpga(config_name=config, jobs=jobs)


@app.command("flash-fpga")
def flash_fpga_cmd(
    config: str = typer.Option(
        None,
        "--config",
        "-c",
        help="CVA6 FPGA config name (see 'cheridemo list-configs')",
    ),
):
    """Flash the Genesys2 board with the built bitstream (placeholder command)."""
    fpga.flash_fpga(config_name=config)

@app.command("format-sd")
def format_sd_cmd(
    device: str = typer.Option(..., "--device", help="Disk node, e.g. /dev/mmcblk0 or /dev/sdX"),
    target: str = typer.Option(..., "--target", "-t", help="Software target (e.g., baremetal-demo, cheribsd-demo)"),
):
    """Partition SD like cva6-sdk (p1 sized to fw_payload.bin; p2 at 512M for CheriBSD)."""
    from . import sdcard
    sdcard.format_sd(target_name=target, device=device)

@app.command("flash-sd")
def flash_sd_cmd(
    device: str = typer.Option(..., "--device", help="Disk node, e.g. /dev/mmcblk0 or /dev/sdX"),
    target: str = typer.Option(..., "--target", "-t", help="Software target (e.g., baremetal-demo, cheribsd-demo)"),
):
    """dd the payload(s) to the SD partitions (p1=fw_payload, p2=UImage if CheriBSD)."""
    from . import sdcard
    sdcard.flash_sd(target_name=target, device=device)


@app.command("build-sdk")
def build_sdk_cmd(
    profile: str = typer.Option(
        None,
        help="SDK profile name (see configs/sdk_profiles.yaml). "
             "Defaults to the 'default' profile in that file.",
    ),
    jobs: int = typer.Option(16, "--jobs", "-j", help="Parallel build jobs for cheribuild."),
):
    """Build the CHERI/CORE-V SDK via cheribuild using a named profile."""
    build.build_sdk(profile_name=profile, jobs=jobs)

if __name__ == "__main__":
    app()

