from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from rich.console import Console

console = Console()


def run_cmd(
    cmd: list[str],
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
):
    """Run a subprocess, printing the command and failing fast on error.

    If *env* is provided, it is used as the environment for the subprocess.
    """
    console.print(f"[bold blue]→[/] {' '.join(cmd)}")
    if env is not None:
        env_dict: MutableMapping[str, str] = dict(env)
    else:
        env_dict = None

    result = subprocess.run(cmd, cwd=cwd, env=env_dict)
    if result.returncode != 0:
        console.print(f"[bold red]✖ Command failed[/]: {' '.join(cmd)}")
        sys.exit(result.returncode)


def clone_repo(url: str, dest: Path, branch: str | None = None, commit: str | None = None):
    """Clone a git repo (or update if it already exists) and initialise submodules."""
    if dest.exists():
        console.print(f"[green]✔ Repo already present:[/] {dest}")
    else:
        run_cmd(["git", "clone", url, str(dest)])

    if branch:
        run_cmd(["git", "checkout", branch], cwd=dest)
    if commit:
        run_cmd(["git", "checkout", commit], cwd=dest)

    # Submodules (if any)
    run_cmd(["git", "submodule", "update", "--init", "--recursive"], cwd=dest)

