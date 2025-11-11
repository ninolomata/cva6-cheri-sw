from __future__ import annotations

from pathlib import Path

from rich.console import Console

from .config import CONFIG, EXTERNAL
from .utils import run_cmd
from . import toolchain
import os
import subprocess
import psutil, shutil
from pathlib import Path
import time


console = Console()


def build_fpga(config_name: str | None = None, jobs: int = 8):
    """Build FPGA bitstream for CVA6-CHERI on the Genesys2 board."""
    cva6 = EXTERNAL / "cheri-cva6"
    if not cva6.exists():
        raise SystemExit("cheri-cva6 repo not found, run 'cheridemo clone' first.")

    cfg = CONFIG.get_cva6_config(config_name)
    console.print(f"[bold]Building FPGA bitstream[/] for config [cyan]{cfg.name}[/]")
    console.print(f"  CVA6 target: [cyan]{cfg.target}[/]")
    console.print(f"  make target: [cyan]{cfg.make_target}[/]")
    # 1. Ensure we have a RISCV toolchain (download from Embecosm if needed)
    riscv_root = toolchain.ensure_riscv_toolchain()

    env = os.environ.copy()
    env["RISCV"] = str(riscv_root)
    env["CROSSCOMPILE"] = "riscv32-corev-elf-"

    console.print(f"  Using RISCV = [magenta]{env['RISCV']}[/]")
    console.print(f"  Using CROSSCOMPILE = [magenta]{env['CROSSCOMPILE']}[/]")

    #   make BOARD=genesys2 target=<target> fpga -jN
    cmd = [
        "make",
        f"BOARD={cfg.board}",
        f"target={cfg.target}",
        cfg.make_target,
        f"-j{jobs}",
    ]
    run_cmd(cmd, cwd=cva6, env=env)


def flash_fpga(config_name: str | None = None):
    """Flash the Genesys2 FPGA using the existing Vivado TCL script in cheri-cva6."""
    cva6 = EXTERNAL / "cheri-cva6"
    if not cva6.exists():
        raise SystemExit("cheri-cva6 repo not found, run 'cheridemo clone' first.")

    cfg = CONFIG.get_cva6_config(config_name)

    script_path = cva6 / cfg.flash_script
    if not script_path.exists():
        raise SystemExit(
            f"Flash script not found for config {cfg.name}:\n"
            f"  {script_path}\n"
            "Make sure 'flash_script' in configs/cva6_configs.yaml points to your Vivado TCL file."
        )

    console.print("[bold]Flashing FPGA via Vivado TCL script[/]")
    console.print(f"  board: [cyan]{cfg.board}[/]")
    console.print(f"  script: [magenta]{script_path}[/]")

    env = os.environ.copy()

    # 1️⃣ Ensure hw_server is running
    ensure_hw_server(env)

    # 2️⃣ Set HW_SERVER_URL if missing
    if "HW_SERVER_URL" not in env:
        env["HW_SERVER_URL"] = "localhost:3121"

    cmd = [
        "vivado",
        "-mode", "batch",
        "-source", str(script_path),
    ]
    run_cmd(cmd, cwd=script_path.parent, env=env)

def ensure_hw_server(env: dict[str, str]) -> None:
    """Start Vivado's hw_server if not already running."""
    console.print("[bold blue]→ Checking for hw_server[/]")

    # 1. Detect existing hw_server process
    for proc in psutil.process_iter(attrs=["name", "cmdline"]):
        try:
            if "hw_server" in proc.info["name"]:
                console.print("[green]✔ hw_server already running[/]")
                return
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # 2. Not running → launch it
    console.print("[yellow]hw_server not running, starting one...[/]")
    hw_server_bin = shutil.which("hw_server")
    if not hw_server_bin:
        raise SystemExit(
            "Vivado hw_server not found in PATH. "
            "Please source Vivado settings64.sh or set VIVADO_PATH."
        )

    log_path = Path("external") / "logs" / "hw_server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    subprocess.Popen(
        [hw_server_bin, "-s", "tcp::3121"],
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
        env=env,
    )

    console.print(f"[green]Started hw_server[/] → logs: {log_path}")
    time.sleep(3)  # give it a few seconds to initialize

