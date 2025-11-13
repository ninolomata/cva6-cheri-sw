from __future__ import annotations

from pathlib import Path

from rich.console import Console

from .config import CONFIG, EXTERNAL
from .utils import clone_repo, run_cmd

import os

console = Console()


def clone_all():
    """Clone all repos defined in configs/repos.yaml into external/."""
    EXTERNAL.mkdir(exist_ok=True)
    for name, repo in CONFIG.repos.items():
        dest = EXTERNAL / name
        console.print(f"[bold]Cloning {name}[/]")
        clone_repo(repo.url, dest, repo.branch, repo.commit)


def build_sdk(
    profile_name: str | None = None,
    jobs: int = 16,
):
    """
    Build the SDK via cheribuild using a data-driven profile.

    The profile comes from configs/sdk_profiles.yaml and defines:
      - cheribuild_targets (list)
      - enable_hybrid_targets (bool)
      - source_root (default; can be overridden by $CHERI_SYS_ROOT)
      - extra_args (list of additional cheribuild args)
    """
    cheribuild = EXTERNAL / "cheribuild"
    if not cheribuild.exists():
        raise SystemExit("cheribuild repo not found, run 'cheridemo clone' first.")

    profile = CONFIG.get_sdk_profile(profile_name)

    # Resolve source root: env > profile > default ~/cheri
    env_source_root = os.environ.get("CHERI_SYS_ROOT")
    if env_source_root:
        source_root_path = Path(env_source_root).expanduser().resolve()
    elif profile.source_root:
        source_root_path = Path(profile.source_root).expanduser().resolve()
    else:
        source_root_path = Path.home() / "cheri"

    if not source_root_path.exists():
        console.print(f"[yellow]Source root {source_root_path} does not exist — creating it.[/]")
        source_root_path.mkdir(parents=True, exist_ok=True)

    if not profile.cheribuild_targets:
        raise SystemExit(f"SDK profile {profile.name} has no cheribuild_targets configured.")

    console.print("[bold]Building SDK via cheribuild[/]")
    console.print(f"  profile: [cyan]{profile.name}[/]")
    console.print(f"  desc   : {profile.description}")
    console.print(f"  source-root: [magenta]{source_root_path}[/]")
    console.print(f"  targets: [cyan]{', '.join(profile.cheribuild_targets)}[/]")
    console.print(f"  make-jobs: [cyan]{jobs}[/]")

    cmd: list[str] = [
        "./cheribuild.py",
        *profile.cheribuild_targets,
        f"--source-root={source_root_path}",
        f"--make-jobs={jobs}",
    ]

    if profile.enable_hybrid_targets:
        cmd.append("--enable-hybrid-targets")

    # Add any extra args from the profile, e.g. "-d"
    cmd.extend(profile.extra_args)

    run_cmd(cmd, cwd=cheribuild)


def build_sw(target_name: str | None = None, jobs: int = 8):
    """
    Build a software stack (CheriBSD, Bao+baremetal bundle, or baremetal).

    For kind == "baremetal":
      - builds the baremetal app
      - builds OpenSBI with that baremetal payload
      - copies all artifacts to external/output/<target-name>/
    """
    if target_name is None:
        target_name = CONFIG.sw_default_name

    tgt = CONFIG.get_sw_target(target_name)

    console.print(f"[bold]Building software target[/] [cyan]{tgt.name}[/]")
    console.print(f"  kind: [cyan]{tgt.kind}[/]")

    # ------------------------------------------------------------
    # Baremetal flow: baremetal guest + OpenSBI with payload
    # ------------------------------------------------------------
    if tgt.kind == "baremetal":
        out_dir = target_output_dir(tgt)

        # 1) Build baremetal app (ELF/BIN copied to out_dir)

        console.print("[bold]Step 1/2:[/] Building baremetal app")
        app_artifacts = build_baremetal_app(tgt, jobs=jobs, out_dir=out_dir)

        payload = app_artifacts.get("bin") or app_artifacts.get("elf")
        if payload is None:
            raise SystemExit("Baremetal build produced no payload ELF/BIN.")

        # 2) Build OpenSBI with that payload (artifacts copied to out_dir)
        console.print("[bold]Step 2/2:[/] Building OpenSBI with baremetal payload")
        fw_artifacts = build_opensbi_for_baremetal(
            tgt,
            jobs=jobs,
            payload=payload,
            out_dir=out_dir,
        )

        console.print("")
        console.print(f"[bold green]✔ Baremetal stack built successfully[/]")
        console.print(f"  Output directory: [magenta]{out_dir}[/]")
        console.print("  Contains:")
        if app_artifacts.get("elf"):
            console.print(f"    - baremetal ELF : {app_artifacts['elf']}")
        if app_artifacts.get("bin"):
            console.print(f"    - baremetal BIN : {app_artifacts['bin']}")
        if fw_artifacts.get("fw_bin"):
            console.print(f"    - OpenSBI fw BIN: {fw_artifacts['fw_bin']}")
        if fw_artifacts.get("fw_elf"):
            console.print(f"    - OpenSBI fw ELF: {fw_artifacts['fw_elf']}")

        return

    # ------------------------------------------------------------
    # Other kinds (fill in with your existing logic)
    # ------------------------------------------------------------
    elif tgt.kind == "cheribsd":
        # TODO: call your existing CheriBSD build logic here
        raise SystemExit("build_sw: 'cheribsd' handling not yet implemented here.")
    elif tgt.kind == "bao_bundle":
        # TODO: call your existing Bao+guest bundle logic here
        raise SystemExit("build_sw: 'bao_bundle' handling not yet implemented here.")
    else:
        raise SystemExit(f"Unknown software target kind: {tgt.kind}")