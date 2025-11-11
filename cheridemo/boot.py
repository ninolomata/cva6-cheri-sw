from __future__ import annotations

from pathlib import Path

from rich.console import Console

from .config import EXTERNAL
from .utils import run_cmd

console = Console()


def build_opensbi(platform: str, payload: Path | None = None, output: Path | None = None):
    """Build OpenSBI for a given platform, optionally with a payload (fw_payload)."""
    repo = EXTERNAL / "opensbi"
    if not repo.exists():
        raise SystemExit("OpenSBI repo not found, run 'cheridemo clone' first.")

    console.print(f"• Building OpenSBI for platform [cyan]{platform}[/]")

    run_cmd(["make", "distclean"], cwd=repo)
    cmd = ["make", f"PLATFORM={platform}"]
    if payload is not None:
        cmd.append(f"FW_PAYLOAD_PATH={payload}")
    run_cmd(cmd, cwd=repo)

    if output is not None:
        # This is the standard OpenSBI fw_payload output path.
        built = repo / "build" / platform / "firmware" / "fw_payload.bin"
        if not built.exists():
            raise SystemExit(f"Expected OpenSBI output not found: {built}")
        output.parent.mkdir(parents=True, exist_ok=True)
        run_cmd(["cp", str(built), str(output)])


def build_uboot(defconfig: str, jobs: int = 8):
    """Build U-Boot for CVA6-CHERI / Genesys2."""
    repo = EXTERNAL / "uboot"
    if not repo.exists():
        raise SystemExit("U-Boot repo not found, run 'cheridemo clone' first.")

    console.print(f"• Building U-Boot with defconfig [cyan]{defconfig}[/]")

    run_cmd(["make", "distclean"], cwd=repo)
    run_cmd(["make", defconfig], cwd=repo)
    run_cmd(["make", f"-j{jobs}"], cwd=repo)


def build_cheribsd_boot_chain(tgt, jobs: int = 8):
    """Build OpenSBI + U-Boot boot chain for CheriBSD-on-SD flow."""
    platform = tgt.params["opensbi_platform"]
    defconfig = tgt.params["uboot_defconfig"]

    console.print("[bold]Building CheriBSD boot chain (OpenSBI + U-Boot)[/]")

    # 1) Build U-Boot
    build_uboot(defconfig, jobs=jobs)
    uboot_repo = EXTERNAL / "uboot"
    uboot_bin = uboot_repo / "u-boot.bin"  # adjust if your tree uses a different file name
    if not uboot_bin.exists():
        raise SystemExit(f"U-Boot binary not found: {uboot_bin}")

    # 2) Build OpenSBI using U-Boot as fw_payload
    output = EXTERNAL / "boot-artifacts" / "opensbi_uboot_fw_payload.bin"
    build_opensbi(platform=platform, payload=uboot_bin, output=output)
    console.print(f"  OpenSBI+U-Boot fw_payload: [magenta]{output}[/]")


def package_bao_bundle(tgt, jobs: int = 8):
    """Build Bao + baremetal guest + OpenSBI monolithic bundle."""
    bao_repo = EXTERNAL / tgt.params["bao_repo"]
    guest_repo = EXTERNAL / tgt.params["guest_repo"]
    platform = tgt.params["opensbi_platform"]
    bundle_output = (EXTERNAL / tgt.params["bundle_output"]).resolve()

    if not guest_repo.exists():
        raise SystemExit(f"Guest repo not found: {guest_repo}")
    if not bao_repo.exists():
        raise SystemExit(f"Bao repo not found: {bao_repo}")

    console.print(f"[bold]Building Bao + baremetal guest bundle[/]")

    # 1) Guest baremetal app
    console.print(f"• Building Bao guest in [cyan]{guest_repo.name}[/]")
    run_cmd(["make", tgt.params.get("guest_make_target", "all"), f"-j{jobs}"], cwd=guest_repo)
    guest_elf = guest_repo / tgt.params["guest_elf"]
    if not guest_elf.exists():
        raise SystemExit(f"Guest ELF not found: {guest_elf}")

    # 2) Bao hypervisor (typically its build incorporates the guest image)
    console.print(f"• Building Bao hypervisor in [cyan]{bao_repo.name}[/]")
    run_cmd(["make", f"CONFIG={tgt.params['bao_config']}", f"-j{jobs}"], cwd=bao_repo)
    bao_elf = bao_repo / tgt.params["bao_elf"]
    if not bao_elf.exists():
        raise SystemExit(f"Bao ELF not found: {bao_elf}")

    # 3) OpenSBI bundle (Bao is used as FW_PAYLOAD)
    console.print(f"• Building OpenSBI fw_payload bundle → [magenta]{bundle_output}[/]")
    build_opensbi(platform=platform, payload=bao_elf, output=bundle_output)


def package_baremetal_bundle(tgt, jobs: int = 8):
    """Build OpenSBI + baremetal monolithic bundle (no Bao, no U-Boot)."""
    app_repo = EXTERNAL / tgt.params["app_repo"]
    platform = tgt.params["opensbi_platform"]
    bundle_output = (EXTERNAL / tgt.params["bundle_output"]).resolve()

    if not app_repo.exists():
        raise SystemExit(f"Baremetal app repo not found: {app_repo}")

    console.print(f"[bold]Building OpenSBI + baremetal bundle[/]")

    console.print(f"• Building baremetal app in [cyan]{app_repo.name}[/]")
    run_cmd(["make", tgt.params.get("app_make_target", "all"), f"-j{jobs}"], cwd=app_repo)
    app_elf = app_repo / tgt.params["app_elf"]
    if not app_elf.exists():
        raise SystemExit(f"App ELF not found: {app_elf}")

    console.print(f"• Building OpenSBI+baremetal bundle → [magenta]{bundle_output}[/]")
    build_opensbi(platform=platform, payload=app_elf, output=bundle_output)

