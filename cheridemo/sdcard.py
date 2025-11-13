from __future__ import annotations
from pathlib import Path
import math, os

from rich.console import Console
from .config import CONFIG
from .utils import target_output_dir
from . import run_cmd  # your helper

console = Console()

def _part_suffix(dev: str) -> tuple[str,str]:
    # /dev/sdX -> /dev/sdX1,/dev/sdX2 ; /dev/mmcblk0 -> /dev/mmcblk0p1,/dev/mmcblk0p2
    if os.path.basename(dev).startswith("mmcblk"):
        return dev + "p1", dev + "p2"
    return dev + "1", dev + "2"

def _assert_dev_is_disk(dev: str):
    base = os.path.basename(dev)
    if base[-1:].isdigit():
        raise SystemExit(f"{dev} looks like a partition. Pass the disk node (e.g., /dev/sdX or /dev/mmcblk0)")
    if base == "sda":
        raise SystemExit("Refusing to touch /dev/sda for safety.")

def _payload_path_for(tgt) -> Path:
    out = target_output_dir(tgt)
    # Name matches what your bundle produces
    fw = out / "opensbi-fw.bin"
    if not fw.exists():
        raise SystemExit(f"opensbi-fw.bin not found: {fw}")
    return fw

def _uimage_path_for(tgt) -> Path:
    out = target_output_dir(tgt)
    # You’ve been calling it CheriBSD
    uimg = out / "CheriBSD"
    if not uimg.exists():
        raise SystemExit(f"UImage (CheriBSD) not found: {uimg}")
    return uimg

def _payload_sectors(payload: Path) -> int:
    # ceil(bytes / 512)
    size_bytes = payload.stat().st_size
    return math.ceil(size_bytes / 512)

def format_sd(target_name: str, device: str):
    """
    Partition the SD like cva6-sdk:
      - p1 sized exactly for fw_payload.bin (type 3000)
      - p2 starting at 512M to end (type 8300)
    """
    _assert_dev_is_disk(device)
    tgt = CONFIG.get_sw_target(target_name)

    payload = _payload_path_for(tgt)
    sectorsize = _payload_sectors(payload)

    FWPAYLOAD_SECTORSTART = 2048
    FWPAYLOAD_SECTOREND   = FWPAYLOAD_SECTORSTART + sectorsize  # matches your Makefile

    UIMAGE_SECTORSTART = "512M"  # literal, like the Makefile

    console.print("[bold]Formatting SD[/] "
                  f"(p1: start={FWPAYLOAD_SECTORSTART}, end={FWPAYLOAD_SECTOREND}, type=3000"
                  + (f"; p2: start={UIMAGE_SECTORSTART}, type=8300" if make_p2 else "")
                  + f") on [red]{device}[/]")

    # Wipe and partition
    run_cmd(["sudo", "sgdisk", "--clear", "-g", device])
    cmd = [
        "sudo", "sgdisk",
        f"--new=1:{FWPAYLOAD_SECTORSTART}:{FWPAYLOAD_SECTOREND}",
        f"--new=2:{UIMAGE_SECTORSTART}:0",
        "--typecode=1:3000",
        "--typecode=2:8300",
        device,
        "-g"
    ]
    run_cmd(cmd)
    # re-read partition table
    run_cmd(["sudo", "partprobe", device])
    console.print("[green]✔ SD partitioned[/]")

def flash_sd(target_name: str, device: str):
    """
    Flash artifacts to the SD partitions (raw dd):
      - baremetal: opensbi-fw.bin -> p1
      - cheribsd : opensbi-fw.bin -> p1, CheriBSD -> p2
    """
    _assert_dev_is_disk(device)
    tgt = CONFIG.get_sw_target(target_name)
    p1, p2 = _part_suffix(device)

    fw = _payload_path_for(tgt)
    console.print(f"[bold]Flashing[/] opensbi-fw.bin → [cyan]{p1}[/]")
    run_cmd(["sudo", "dd", f"if={fw}", f"of={p1}", "bs=4M", "status=progress", "conv=fsync"])

    if tgt.kind == "cheribsd":
        uimg = _uimage_path_for(tgt)
        console.print(f"[bold]Flashing[/] CheriBSD → [cyan]{p2}[/]")
        run_cmd(["sudo", "dd", f"if={uimg}", f"of={p2}", "bs=4M", "status=progress", "conv=fsync"])

    run_cmd(["sudo", "sync"])
    console.print("[green]✔ Flash complete[/]")
