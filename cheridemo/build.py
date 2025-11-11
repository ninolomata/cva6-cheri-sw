from __future__ import annotations

from pathlib import Path

from rich.console import Console

from .config import CONFIG, EXTERNAL
from .utils import clone_repo, run_cmd

console = Console()


def clone_all():
    """Clone all repos defined in configs/repos.yaml into external/."""
    EXTERNAL.mkdir(exist_ok=True)
    for name, repo in CONFIG.repos.items():
        dest = EXTERNAL / name
        console.print(f"[bold]Cloning {name}[/]")
        clone_repo(repo.url, dest, repo.branch, repo.commit)


def build_sdk(jobs: int = 8):
    """Build CHERI SDK via cheribuild (used for CheriBSD)."""
    cheribuild = EXTERNAL / "cheribuild"
    if not cheribuild.exists():
        raise SystemExit("cheribuild repo not found, run 'cheridemo clone' first.")

    console.print("[bold]Building CHERI SDK via cheribuild[/]")
    cmd = ["./cheribuild.py", "sdk-riscv64-purecap", "-d", f"-j{jobs}"]
    run_cmd(cmd, cwd=cheribuild)

