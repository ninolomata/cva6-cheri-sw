from __future__ import annotations

from pathlib import Path

from rich.console import Console

from .config import CONFIG, EXTERNAL
from .utils import run_cmd, resolve_sdk_root
from . import boot
from . import toolchain

import os
import shutil
import sys
import stat

console = Console()

def target_output_dir(tgt) -> Path:
    """
    Standard output dir for a software target:
    external/output/<target-name>
    """
    out = EXTERNAL / "output" / tgt.name
    out.mkdir(parents=True, exist_ok=True)
    return out

def _resolve_cheribuild_entry(source_root: Path) -> list[str]:
    """
    Prefer running cheribuild as a Python module via its repo copy:
      <source_root>/cheribuild/cheribuild.py
    Fallback to 'cheribuild' in PATH.
    Returns argv prefix to invoke cheribuild, e.g. [sys.executable, '/…/cheribuild.py'] or ['cheribuild'].
    """
    cb_py = source_root / "cheribuild.py"
    if cb_py.exists():
        return [sys.executable, str(cb_py)]
    # fallback
    return ["cheribuild"]

def build_cheribsd(
    tgt,
    jobs: int = 16,
    out_dir: Path | None = None,
) -> dict[str, Path]:
    """
    Build CheriBSD via cheribuild and copy artifacts to external/output/<target-name>/.

    Expects in tgt.params:
      - cheribuild_target  (e.g., 'cheribsd-riscv64-purecap')
      - kernel_elf         (e.g., 'kernel-riscv64-purecap.elf')
      - rootfs_img         (e.g., 'rootfs-riscv64-purecap.img')  # optional if not using rootfs
    """
    p = tgt.params
    cheribuild_target = p.get("cheribuild_target")
    if not cheribuild_target:
        raise SystemExit("build_cheribsd: 'cheribuild_target' is required in target params.")

    kernel_name = p.get("kernel_elf")

    # -------------------------------
    # Resolve SDK source-root
    # -------------------------------
    env_root = os.environ.get("CHERI_SDK_ROOT")
    if env_root:
        sdk_source_root = Path(env_root).expanduser().resolve()
    else:
        cfg_root = tgt.params.get("sdk_source_root")
        if cfg_root:
            sdk_source_root = Path(cfg_root).expanduser().resolve()
        else:
            sdk_source_root = Path.home() / "cheri"
    output_root = sdk_source_root / "output"

    if out_dir is None:
        out_dir = sw.target_output_dir(tgt)
    out_dir.mkdir(parents=True, exist_ok=True)

    console.print("[bold]Building CheriBSD via cheribuild[/]")
    console.print(f"  source root : [magenta]{sdk_source_root}[/]")
    console.print(f"  output root : [magenta]{output_root}[/]")
    console.print(f"  target      : [cyan]{cheribuild_target}[/]")
    console.print(f"  jobs        : [cyan]{jobs}[/]")

    cheribuild_cmd = EXTERNAL / "cheribuild/cheribuild.py"

    # 2) build CheriBSD target
    cmd = [
        str(cheribuild_cmd),
        "--source-root", str(sdk_source_root),
        cheribuild_target, 
        "-d", 
        f"-j{jobs}"
    ]

    run_cmd(cmd, cwd=sdk_source_root)

    # 3) resolve produced artifacts under <source_root>/output/
    artifacts: dict[str, Path] = {}

    if kernel_name:
        kernel_src = (output_root / kernel_name).resolve()
        if not kernel_src.exists():
            raise SystemExit(f"CheriBSD kernel not found: {kernel_src}")
        dst = out_dir / kernel_src.name
        if dst.exists():
            if dst.is_file() or dst.is_symlink():
                dst.unlink()
            else:
                shutil.rmtree(dst)
        shutil.copy2(kernel_src, dst)
        # 1. Make source writable (remove read-only bit if needed)
        try:
            print(f"⚠️ Warning: trying to chmod source {dst} to u+rw")
            os.chmod(dst, stat.S_IRUSR | stat.S_IWUSR)  # u+rw
        except Exception as e:
            print(f"⚠️ Warning: could not chmod source {dst}: {e}")
        console.print(f"  → kernel copied to [magenta]{dst}[/]")
        artifacts["kernel_elf"] = dst

    console.print(f"[bold green]✔ CheriBSD build complete[/] → [magenta]{out_dir}[/]")
    return artifacts

def build_opensbi(
    tgt,
    jobs: int = 8,
    payload: Path | None = None,
    out_dir: Path | None = None,
) -> dict[str, Path]:
    """
    Build OpenSBI firmware with the given payload (baremetal ELF/BIN),
    and copy final artifacts to external/output/<target-name>.
    Returns dict with at least {"fw_bin": Path, "fw_elf": Optional[Path]}.
    """
    from pathlib import Path

    params = tgt.params
    opensbi_repo = EXTERNAL / params["opensbi_repo"]
    opensbi_platform = params.get("opensbi_platform", "ariane")
    opensbi_flags = params.get("opensbi_flags", "")

    if not opensbi_repo.exists():
        raise SystemExit(f"OpenSBI repo not found: {opensbi_repo}")

    if payload is None:
        # if payload not provided, rebuild baremetal to get it
        bare = build_baremetal_app(tgt, jobs=jobs, out_dir=out_dir)
        payload = bare.get("bin") or bare.get("elf")
        if payload is None:
            raise SystemExit("No baremetal payload (ELF/BIN) produced.")
    # Resolve SDK + clang from SDK
    sdk_root = resolve_sdk_root(tgt)
    sdk_bin = sdk_root / "bin"

    console.print("[bold]Building OpenSBI for baremetal payload[/]")
    console.print(f"  target   : [cyan]{tgt.name}[/]")
    console.print(f"  repo     : [magenta]{opensbi_repo}[/]")
    console.print(f"  platform : [cyan]{opensbi_platform}[/]")
    console.print(f"  payload  : [magenta]{payload}[/]")
    console.print(f"  flags    : {opensbi_flags}")

    env = os.environ.copy()
    env["FW_PAYLOAD_PATH"] = str(payload)
    env["FW_PAYLOAD"] = str('y')

    # Make sure LLVM tools come from the SDK
    env["CC"] = str(sdk_bin / "clang")
    env["AR"] = str(sdk_bin / "llvm-ar")
    env["LD"] = str(sdk_bin / "ld.lld")
    env["OBJCOPY"] = str(sdk_bin / "llvm-objcopy")
    env["LLVM"] = "" # to disable clang version check in OpenSBI

    console.print(f"  Using CC = [magenta]{env['CC']}[/]")
    console.print(f"  Using AR = [magenta]{env['AR']}[/]")
    console.print(f"  Using LD = [magenta]{env['LD']}[/]")
    console.print(f"  Using OBJCOPY = [magenta]{env['OBJCOPY']}[/]")

    cmd = [
        "make",
        f"PLATFORM={opensbi_platform}",
        opensbi_flags,
        f"-j{jobs}",
    ]

    run_cmd(cmd, cwd=opensbi_repo, env=env)

    fw_dir = opensbi_repo / "build/platform" / opensbi_platform / "firmware"
    fw_bin = fw_dir / "fw_payload.bin"
    fw_elf = fw_dir / "fw_payload.elf"

    if not fw_bin.exists():
        alt = fw_dir / "firmware.bin"
        if alt.exists():
            fw_bin = alt
        else:
            raise SystemExit(
                f"OpenSBI firmware binary not found in {fw_dir} "
                "(expected fw_payload.bin)"
            )

    if not fw_elf.exists():
        fw_elf = None

    console.print(f"[green]✔ OpenSBI firmware built[/]: {fw_bin}")

    if out_dir is None:
        out_dir = target_output_dir(tgt)
    else:
        out_dir = Path(out_dir).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

    artifacts: dict[str, Path] = {}

    # copy fw_bin
    dst_bin = out_dir / "opensbi-fw.bin"
    shutil.copy2(fw_bin, dst_bin)
    console.print(f"  → copied fw_bin to [magenta]{dst_bin}[/]")
    artifacts["fw_bin"] = dst_bin

    if fw_elf is not None:
        dst_elf = out_dir / "opensbi-fw.elf"
        shutil.copy2(fw_elf, dst_elf)
        console.print(f"  → copied fw_elf to [magenta]{dst_elf}[/]")
        artifacts["fw_elf"] = dst_elf

    return artifacts


def build_baremetal_app(tgt, jobs: int = 8, out_dir: Path | None = None):
    """
    Build Baremetal Application, and copy artifacts to external/output/<target-name>.
    """
    app_repo = EXTERNAL / tgt.params["app_repo"]
    app_target = tgt.params.get("app_make_target", "all")
    app_elf_rel = tgt.params.get("app_elf", "build/app.elf")
    app_elf = app_repo / app_elf_rel
    app_bin_rel = tgt.params.get("app_bin", app_elf_rel.replace(".elf", ".bin"))
    app_bin = app_repo / app_bin_rel
    app_abi = tgt.params.get("app_abi", "purecap")
    app_arch_sub = tgt.params.get("app_arch_sub", "riscv64xcheri")

    if not app_repo.exists():
        raise SystemExit(f"Baremetal app repo not found: {app_repo}")

    # -------------------------------
    # Resolve SDK source-root
    # -------------------------------
    env_root = os.environ.get("CHERI_SDK_ROOT")
    if env_root:
        sdk_source_root = Path(env_root).expanduser().resolve()
    else:
        cfg_root = tgt.params.get("sdk_source_root")
        if cfg_root:
            sdk_source_root = Path(cfg_root).expanduser().resolve()
        else:
            sdk_source_root = Path.home() / "cheri"

    # SDK root where cheribuild puts toolchains/sysroots
    sdk_root = sdk_source_root / "output" / "sdk"


    # -------------------------------
    # Pick SYSROOT
    # -------------------------------

    sysroot_rel = tgt.params.get("sdk_sysroot", "baremetal")

    sysroot_path = sdk_root / sysroot_rel

    if not sysroot_path.exists():
        raise SystemExit(
            f"SYSROOT for baremetal app not found:\n"
            f"  {sysroot_path}\n"
            "Make sure you ran 'cheridemo build-sdk' with matching source-root, "
            "and that sdk_sysroot_* in software_targets.yaml matches cheribuild's layout."
        )
    app_platform = tgt.params.get("app_platform", "cva6")

    console.print("[bold]Building baremetal app[/]")
    console.print(f"  repo     : [magenta]{app_repo}[/]")
    console.print(f"  target   : [cyan]{app_target}[/]")
    console.print(f"  ABI      : [cyan]{app_abi}[/]")
    console.print(f"  PLATFORM : [cyan]{app_platform}[/]")
    console.print(f"  ARCH_SUB : [cyan]{app_arch_sub}[/]")
    console.print(f"  SYSROOT  : [magenta]{sysroot_path}[/]")

    env = os.environ.copy()
    env["SYSROOT"] = str(sysroot_path)

    # Set CROSSCOMPILE
    cross_compile = sdk_root / "bin/clang"
    env["CROSS_COMPILE"] = str(cross_compile)
    run_cmd(["make", "clean"], cwd=app_repo, env=env)
    cmd = [
        "make",
        f"PLATFORM={app_platform}",
        f"ARCH_SUB={app_arch_sub}",
        f"SINGLE_CORE=y",
        app_target,
        f"-j{jobs}",
    ]
    run_cmd(cmd, cwd=app_repo, env=env)

    #initialize returned artifacts
    artifacts: dict[str, Path] = {}

    if app_elf.exists():
        console.print(f"[green]✔ Build successful[/]: {app_elf}")
        artifacts["elf"] = app_elf
    else:
        console.print(f"[yellow]⚠ Build finished, but ELF not found[/]: {app_elf}")
    
    if app_bin.exists():
        console.print(f"[green]✔ BIN found[/]: {app_bin}")
        artifacts["bin"] = app_bin
    else:
        console.print(f"[yellow]⚠ BIN not found (optional)[/]: {app_bin}")
    
    if out_dir is None:
        out_dir = target_output_dir(tgt)

    if out_dir and artifacts:
        out_dir = Path(out_dir).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        for kind, path in list(artifacts.items()):
            dst = out_dir / path.name
            shutil.copy2(path, dst)
            console.print(f"  → copied {kind} to [magenta]{dst}[/]")
            artifacts[kind] = dst  # update to point to copied location

    return artifacts


def build_uboot(tgt, jobs: int = 8, out_dir: Path | None = None) -> dict[str, Path]:
    """
    Build U-Boot with the CHERI/LLVM toolchain and copy u-boot.{bin,elf} to external/output/<target>/.
    """
    p = tgt.params
    uboot_repo = EXTERNAL / p["uboot_repo"]
    uboot_defconfig = p.get("uboot_defconfig", "defconfig")
    uboot_flags = p.get("uboot_flags", "")

    if not uboot_repo.exists():
        raise SystemExit(f"U-Boot repo not found: {uboot_repo}")

    # 1. Ensure we have a RISCV Linux toolchain (download from Embecosm if needed)
    riscv_linux_toolchain = toolchain.ensure_riscv_linux_toolchain()

    env = os.environ.copy()
    env["CROSS_COMPILE"] = str(riscv_linux_toolchain) + "/bin/riscv64-unknown-linux-gnu-"

    console.print("[bold]Building U-Boot[/]")
    console.print(f"  repo   : [magenta]{uboot_repo}[/]")
    console.print(f"  config : [cyan]{uboot_defconfig}[/]")
    if uboot_flags:
        console.print(f"  flags  : {uboot_flags}")

    # 1) defconfig
    cmd = ["make", uboot_defconfig]
    if uboot_flags:
        cmd += uboot_flags.split()
    run_cmd(cmd, cwd=uboot_repo, env=env)

    # 2) build
    cmd = ["make", f"-j{jobs}"]
    if uboot_flags:
        cmd += uboot_flags.split()
    run_cmd(cmd, cwd=uboot_repo, env=env)

    # find outputs (adjust if your tree differs)
    uboot_bin = uboot_repo / "u-boot.bin"
    uboot_elf = uboot_repo / "u-boot"

    if not uboot_bin.exists():
        # Some trees drop in ./build/...; add fallback if needed
        raise SystemExit("U-Boot build succeeded but u-boot.bin not found.")
    if not uboot_elf.exists():
        uboot_elf = None

    if out_dir is None:
        out_dir = target_output_dir(tgt)
    out_dir.mkdir(parents=True, exist_ok=True)

    artifacts = {}
    dst_bin = out_dir / "u-boot.bin"
    shutil.copy2(uboot_bin, dst_bin)
    artifacts["uboot_bin"] = dst_bin
    console.print(f"  → copied u-boot.bin to [magenta]{dst_bin}[/]")

    if uboot_elf:
        dst_elf = out_dir / "u-boot.elf"
        shutil.copy2(uboot_elf, dst_elf)
        artifacts["uboot_elf"] = dst_elf
        console.print(f"  → copied u-boot (ELF) to [magenta]{dst_elf}[/]")

    return artifacts

def build_uboot_tools(tgt) -> Path:
    """Return path to U-Boot's tools/mkimage, building it if needed."""
    p = tgt.params
    uboot_repo = EXTERNAL / p["uboot_repo"]
    mkimage = uboot_repo / "tools" / "mkimage"
    if mkimage.exists():
        return mkimage

    console.print("[yellow]mkimage not found in u-boot/tools — building tools...[/]")

    # Build u-boot tools
    env = os.environ.copy()
    env["CROSS_COMPILE"] = str(riscv_linux_toolchain) + "/bin/riscv64-unknown-linux-gnu-"
    subprocess.check_call(["make", "tools"], cwd=uboot_repo, env=env)

    if not mkimage.exists():
        raise SystemExit(f"Failed to build mkimage at {mkimage}")
    return mkimage

def _elf_to_bin_with_llvm_objcopy(tgt, elf_path: Path, out_bin: Path) -> Path:
    """Convert ELF → raw BIN via llvm-objcopy from the SDK."""
    # -------------------------------
    # Resolve SDK source-root
    # -------------------------------
    env_root = os.environ.get("CHERI_SDK_ROOT")
    if env_root:
        sdk_source_root = Path(env_root).expanduser().resolve()
    else:
        cfg_root = tgt.params.get("sdk_source_root")
        if cfg_root:
            sdk_source_root = Path(cfg_root).expanduser().resolve()
        else:
            sdk_source_root = Path.home() / "cheri"
    objcopy = sdk_source_root / "output" / "sdk" / "bin" / "llvm-objcopy"
    if not objcopy.exists():
        raise SystemExit(f"llvm-objcopy not found at {objcopy}")
    cmd = [
        str(objcopy),
        "-D",
        "-O",
        "binary",
        str(elf_path),
        str(out_bin)
        ]
    run_cmd(cmd)
    return out_bin