from __future__ import annotations

from pathlib import Path

from rich.console import Console

from .utils import run_cmd
from .config import CONFIG, EXTERNAL
from . import sw

import subprocess

console = Console()



def package_opensbi_uboot(tgt, jobs: int = 8) -> dict[str, Path]:
    """
    Build U-Boot and then build OpenSBI with U-Boot as payload.
    Returns {"fw_bin": ..., "fw_elf": optional, "uboot_bin": ..., "uboot_elf": optional}.
    """
    out_dir = sw.target_output_dir(tgt)

    console.print("[bold]Step 1/2:[/] Build U-Boot")
    ub = sw.build_uboot(tgt, jobs=jobs, out_dir=out_dir)
    uboot_bin = ub["uboot_bin"]

    console.print("[bold]Step 2/2:[/] Build OpenSBI (payload = U-Boot)")
    fw = sw.build_opensbi(
        tgt,
        jobs=jobs,
        payload=uboot_bin,
        out_dir=out_dir,
    )

    console.print(f"[bold green]✔ OpenSBI+U-Boot bundle ready[/] in [magenta]{out_dir}[/]")
    return {**fw, **ub}


def make_cheribsd_uimage(tgt, kernel_src: Path, out_name: str = "CheriBSD",
                         load_addr: str = "0x80200000", entry_addr: str = "0x80200000",
                         gzip: bool = False, mkimage_path: Path | None = None) -> Path:
    """
    Create a U-Boot image for CheriBSD kernel.
    If gzip=True, expects kernel_src to be a raw bin (will be wrapped with -C gzip).
    """
    out_dir = sw.target_output_dir(tgt)
    out_path = out_dir / out_name
    mkimage_path = sw.build_uboot_tools(tgt)

    # Prefer the mkimage built with your U-Boot tree, else fallback to system mkimage
    if mkimage_path is None:
        # adjust if you keep mkimage elsewhere
        mkimage_path = Path(CONFIG.paths.get("uboot_mkimage", "")) if hasattr(CONFIG, "paths") else None
    if not mkimage_path:
        mkimage_path = shutil.which("mkimage")
        if not mkimage_path:
            raise SystemExit("mkimage not found. Install u-boot-tools or set CONFIG.paths.uboot_mkimage.")

    cmd = [
        str(mkimage_path),
        "-A", "riscv",
        "-O", "freebsd",
        "-T", "kernel",
        "-a", load_addr,
        "-e", entry_addr,
    ]
    if gzip:
        cmd += ["-C", "gzip"]
    cmd += ["-n", "\"CheriBSD\""]
    cmd += ["-d", str(kernel_src), str(out_path)]
    console.print(f"[bold]mkimage[/] → {' '.join(cmd)}")
    run_cmd(cmd)
    console.print(f"[green]✔ CheriBSD created[/]: {out_path}")
    return out_path

def package_baremetal_bundle(tgt, jobs: int = 8) -> Path:
    """
    Compose a 'baremetal' software stack:

      - builds the baremetal guest app
      - builds OpenSBI with that app as FW_PAYLOAD_PATH
      - copies everything into external/output/<target-name>/

    Returns the path to the main firmware binary (OpenSBI fw with payload).
    """
    console.print(f"[bold]Building baremetal bundle for target[/] [cyan]{tgt.name}[/]")
    out_dir = sw.target_output_dir(tgt)
    # 1) Build baremetal app and get its ELF/BIN (already copied to out_dir)
    console.print("[bold]Step 1/2:[/] Building baremetal app")
    app_artifacts = sw.build_baremetal_app(tgt, jobs=jobs, out_dir=out_dir)

    payload = app_artifacts.get("bin") or app_artifacts.get("elf")
    if payload is None:
        raise SystemExit("Baremetal build produced no payload ELF/BIN.")

    # 2) Build OpenSBI firmware using this payload (copies firmware into out_dir)
    console.print("[bold]Step 2/2:[/] Building OpenSBI with baremetal payload")
    fw_artifacts = sw.build_opensbi(
        tgt,
        jobs=jobs,
        payload=payload,
        out_dir=out_dir,
    )

    fw_bin = fw_artifacts.get("fw_bin")
    if fw_bin is None:
        raise SystemExit("OpenSBI build did not produce a firmware binary.")

    console.print("")
    console.print(f"[bold green]✔ Baremetal bundle ready[/]")
    console.print(f"  Output directory: [magenta]{out_dir}[/]")
    console.print(f"  Main firmware bin: [magenta]{fw_bin}[/]")

    return fw_bin

def build_sw(target_name: str | None = None, jobs: int = 8):
    """Build a software stack (CheriBSD, Bao bundle, or baremetal bundle)."""
    tgt = CONFIG.get_sw_target(target_name)
    console.print(f"[bold]Building software target[/] [cyan]{tgt.name}[/] (kind={tgt.kind})")

    if tgt.kind == "cheribsd":
        return package_cheribsd_demo_bundle(target_name, jobs=jobs)
    elif tgt.kind == "baremetal":
        return package_baremetal_bundle(tgt, jobs)
    else:
        raise SystemExit(f"Unknown software kind: {tgt.kind}")

def package_cheribsd_demo_bundle(
    target_name: str,
    jobs: int = 16,
    load_addr: str = "0x80200000",
    entry_addr: str = "0x80200000",
    use_bin: bool = True,
    gzip: bool = True,
):
    """
    Pipeline:
      1) U-Boot
      2) OpenSBI (payload = u-boot.bin)
      3) CheriBSD (cheribuild)
      4) ELF → BIN (llvm-objcopy)
      5) mkimage → CheriBSD  (from u-boot/tools/mkimage)

    Outputs land in: external/output/<target-name>/
    """
    tgt = CONFIG.get_sw_target(target_name)
    out_dir = sw.target_output_dir(tgt)
    console.print(f"[bold]Building CheriBSD demo bundle[/] [cyan]{tgt.name}[/]")
    console.print(f"  output dir: [magenta]{out_dir}[/]")

    # 1) Build U-Boot
    console.print("[bold]Step 1/5:[/] U-Boot")
    ub = sw.build_uboot(tgt, jobs=jobs, out_dir=out_dir)
    uboot_bin = ub["uboot_bin"]

    # 2) Build OpenSBI with U-Boot payload
    console.print("[bold]Step 2/5:[/] OpenSBI (payload = U-Boot)")
    fw = sw.build_opensbi(tgt, jobs=jobs, payload=uboot_bin, out_dir=out_dir)

    # 3) Build CheriBSD via cheribuild
    console.print("[bold]Step 3/5:[/] CheriBSD (cheribuild)")
    ch = sw.build_cheribsd(tgt, jobs=jobs, out_dir=out_dir)
    kernel_elf = ch.get("kernel_elf")
    if kernel_elf is None:
        raise SystemExit("CheriBSD kernel ELF not found after build.")

    # 4) Convert ELF → BIN (optional)
    console.print("[bold]Step 4/5:[/] ELF → BIN")
    kernel_bin = None
    mkimage_input = kernel_elf
    mkimage_gzip = False
    if use_bin:
        kernel_bin = out_dir / (kernel_elf.stem + ".bin")
        sw._elf_to_bin_with_llvm_objcopy(tgt, kernel_elf, kernel_bin)
        mkimage_input = kernel_bin
        mkimage_gzip = gzip  # follow your usual 'mkimage -C gzip' usage

    # 5) mkimage → CheriBSD
    console.print("[bold]Step 5/5:[/] mkimage → CheriBSD")
    uimage = make_cheribsd_uimage(
        tgt,
        mkimage_input,
        out_name="CheriBSD",
        load_addr=load_addr,
        entry_addr=entry_addr,
        gzip=mkimage_gzip,
    )

    console.print("")
    console.print("[bold green]✔ CheriBSD demo bundle complete[/]")
    console.print(f"  OpenSBI fw : {fw.get('fw_bin')}")
    console.print(f"  U-Boot bin : {uboot_bin}")
    console.print(f"  Kernel ELF : {kernel_elf}")
    if kernel_bin:
        console.print(f"  Kernel BIN : {kernel_bin}")
    console.print(f"  UImage     : {uimage}")

    return {
        "fw_bin": fw.get("fw_bin"),
        "uboot_bin": uboot_bin,
        "kernel_elf": kernel_elf,
        "kernel_bin": kernel_bin,
        "uimage": uimage,
    }