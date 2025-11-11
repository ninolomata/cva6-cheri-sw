from __future__ import annotations

from pathlib import Path

from rich.console import Console

from .config import CONFIG, EXTERNAL
from .utils import run_cmd
from . import boot

console = Console()


def build_sw(target_name: str | None = None, jobs: int = 8):
    """Build a software stack (CheriBSD, Bao bundle, or baremetal bundle)."""
    tgt = CONFIG.get_sw_target(target_name)
    console.print(f"[bold]Building software target[/] [cyan]{tgt.name}[/] (kind={tgt.kind})")

    if tgt.kind == "cheribsd":
        _build_cheribsd(tgt, jobs)
    elif tgt.kind == "bao_bundle":
        boot.package_bao_bundle(tgt, jobs)
    elif tgt.kind == "baremetal":
        boot.package_baremetal_bundle(tgt, jobs)
    else:
        raise SystemExit(f"Unknown software kind: {tgt.kind}")


def _build_cheribsd(tgt, jobs: int = 8):
    """Build CheriBSD (via cheribuild) and its OpenSBI+U-Boot boot chain."""
    cheribuild = EXTERNAL / "cheribuild"
    if not cheribuild.exists():
        raise SystemExit("cheribuild repo not found, run 'cheridemo clone' first.")

    sdk_target = tgt.params.get("sdk_target", "sdk-riscv64-purecap")
    cheribsd_target = tgt.params["cheribuild_target"]

    console.print(f"• Building SDK via cheribuild target [cyan]{sdk_target}[/]")
    run_cmd(["./cheribuild.py", sdk_target, "-d", f"-j{jobs}"], cwd=cheribuild)

    console.print(f"• Building CheriBSD via cheribuild target [cyan]{cheribsd_target}[/]")
    run_cmd(["./cheribuild.py", cheribsd_target, "-d", f"-j{jobs}"], cwd=cheribuild)

    # Boot chain: OpenSBI + U-Boot (used as ROM / SPI flash image in your FPGA design).
    boot.build_cheribsd_boot_chain(tgt, jobs=jobs)

