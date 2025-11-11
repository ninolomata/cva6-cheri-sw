from __future__ import annotations

import os
import tarfile
import urllib.request
from pathlib import Path

from rich.console import Console

console = Console()

# --- Directories ---
# Use repo-local cache folder (beside 'external')
REPO_ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_DIR = REPO_ROOT / "external"
CACHE_DIR = EXTERNAL_DIR / "cache"

# Default install root for the downloaded toolchain
DEFAULT_INSTALL_ROOT = EXTERNAL_DIR / "toolchains" / "corev-gcc-ubuntu2204"

# CORE-V GCC toolchain from Embecosm (Ubuntu 22.04)
EMBECOSM_COREV_GCC_URL = (
    "https://buildbot.embecosm.com/job/corev-gcc-ubuntu2204/47/"
    "artifact/corev-openhw-gcc-ubuntu2204-20240530.tar.gz"
)


def _looks_like_riscv_root(root: Path) -> bool:
    """Heuristic: does this directory look like a CORE-V / RISC-V cross toolchain root?"""
    bin_dir = root / "bin"
    if not bin_dir.is_dir():
        return False
    candidates = [
        "riscv64-corev-elf-gcc",
        "riscv32-corev-elf-gcc",
        "riscv64-unknown-elf-gcc",
        "riscv32-unknown-elf-gcc",
    ]
    return any((bin_dir / name).exists() for name in candidates)


def _download_embecosm_corev(dest_root: Path) -> Path:
    """
    Download and extract the Embecosm CORE-V GCC toolchain into dest_root.

    Returns the directory that should be used as $RISCV.
    """
    dest_root = dest_root.expanduser().resolve()
    dest_root.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    tar_path = CACHE_DIR / "corev-gcc-ubuntu2204.tar.gz"

    console.print("[bold yellow]No local RISCV toolchain found, fetching CORE-V GCC from Embecosm…[/]")
    console.print(f"  URL: [cyan]{EMBECOSM_COREV_GCC_URL}[/]")
    console.print(f"  → [magenta]{tar_path}[/]")

    urllib.request.urlretrieve(EMBECOSM_COREV_GCC_URL, tar_path)

    console.print(f"[bold]Extracting toolchain[/] → [magenta]{dest_root}[/]")
    with tarfile.open(tar_path, "r:gz") as tf:
        tf.extractall(dest_root)

    # Some tarballs contain a top-level directory; pick the one that looks like a toolchain root
    for candidate in dest_root.iterdir():
        if candidate.is_dir() and _looks_like_riscv_root(candidate):
            return candidate

    return dest_root


def ensure_riscv_toolchain() -> Path:
    """
    Ensure a RISC-V / CORE-V toolchain exists and return its root directory.

    Priority:
      1. If $RISCV is set and valid → use it.
      2. If external/toolchains/corev-gcc-ubuntu2204 exists → reuse it.
      3. Otherwise → download from Embecosm.
    """
    env_riscv = os.environ.get("RISCV")
    if env_riscv:
        root = Path(env_riscv).expanduser().resolve()
        if _looks_like_riscv_root(root):
            console.print(f"[green]Using existing RISCV toolchain at[/] [magenta]{root}[/]")
            return root
        console.print(f"[yellow]RISCV set but not valid:[/] {root}")

    # Already installed locally?
    if DEFAULT_INSTALL_ROOT.exists():
        for c in DEFAULT_INSTALL_ROOT.iterdir():
            if c.is_dir() and _looks_like_riscv_root(c):
                console.print(f"[green]Using cached CORE-V toolchain at[/] [magenta]{c}[/]")
                return c

    # Download fresh
    installed_root = _download_embecosm_corev(DEFAULT_INSTALL_ROOT)
    console.print(f"[green]Installed CORE-V RISCV toolchain at[/] [magenta]{installed_root}[/]")
    return installed_root
