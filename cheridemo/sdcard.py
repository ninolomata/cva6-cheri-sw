from __future__ import annotations

from pathlib import Path

from rich.console import Console

from .config import CONFIG
from .utils import run_cmd

console = Console()


def prepare_sd_for(target_name: str, device: str):
    """Prepare an SD card with a CheriBSD rootfs image for the given target.

    For this demo, only the 'cheribsd' target makes sense: it uses U-Boot + OpenSBI
    to boot a kernel and rootfs from the SD card.
    """
    tgt = CONFIG.get_sw_target(target_name)
    if tgt.kind != "cheribsd":
        raise SystemExit(
            f"Target {tgt.name} (kind={tgt.kind}) does not use an SD card in this demo.\n"
            "Only the 'cheribsd' target writes a rootfs image to SD."
        )

    # By default cheribuild puts images under ~/cheri/output/.
    cheribuild_out = Path.home() / "cheri" / "output"
    rootfs_name = tgt.params.get("rootfs_img", "rootfs-riscv64-purecap.img")
    rootfs_img = cheribuild_out / rootfs_name

    if not rootfs_img.exists():
        raise SystemExit(f"Rootfs image not found: {rootfs_img}\n"
                         "Make sure you've built the CheriBSD target first.")

    console.print(f"[bold]Preparing SD card for target[/] [cyan]{tgt.name}[/]")
    console.print(f"  Using rootfs image: [magenta]{rootfs_img}[/]")
    console.print(f"  Writing to device: [red]{device}[/] (this will erase it!)")

    # You may want to add an extra confirmation step in real use.
    cmd = [
        "sudo",
        "dd",
        f"if={rootfs_img}",
        f"of={device}",
        "bs=4M",
        "status=progress",
        "conv=fsync",
    ]
    run_cmd(cmd)
    console.print("[green]✔ SD card prepared[/]")

