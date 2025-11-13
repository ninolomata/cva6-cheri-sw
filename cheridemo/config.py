from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from rich.console import Console
import yaml
import subprocess
import shutil
import time
import psutil


from .utils import run_cmd

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = BASE_DIR / "configs"


@dataclass
class RepoConfig:
    url: str
    branch: str | None = None
    commit: str | None = None


@dataclass
class Cva6FpgaConfig:
    name: str
    description: str
    board: str
    target: str
    make_target: str
    bitfile: str
    flash_script: str


@dataclass
class SoftwareTarget:
    name: str
    kind: str
    params: dict

@dataclass
class SdkProfile:
    name: str
    description: str
    source_root: str | None
    enable_hybrid_targets: bool
    cheribuild_targets: list[str]
    extra_args: list[str]

class Config:
    def __init__(self):
        self._repos: dict[str, RepoConfig] | None = None
        self._cva6_configs: dict[str, Cva6FpgaConfig] | None = None
        self._cva6_default: str | None = None
        self._sw_targets: dict[str, SoftwareTarget] | None = None
        self._sw_default: str | None = None
        self._sdk_default: str | None = None
        self._sdk_profiles: dict[str, SdkProfile] | None = None

    # --- Repos ---

    @property
    def repos(self) -> dict[str, RepoConfig]:
        if self._repos is None:
            data = yaml.safe_load((CONFIG_DIR / "repos.yaml").read_text())
            self._repos = {
                name: RepoConfig(
                    url=repo["url"],
                    branch=repo.get("branch"),
                    commit=repo.get("commit"),
                )
                for name, repo in data["repos"].items()
            }
        return self._repos

    # --- CVA6 FPGA configs ---

    @property
    def cva6_default_name(self) -> str:
        if self._cva6_default is None:
            data = yaml.safe_load((CONFIG_DIR / "cva6_configs.yaml").read_text())
            self._cva6_default = data["default"]
        return self._cva6_default

    @property
    def cva6_configs(self) -> dict[str, Cva6FpgaConfig]:
        if self._cva6_configs is None:
            data = yaml.safe_load((CONFIG_DIR / "cva6_configs.yaml").read_text())
            self._cva6_configs = {}
            for name, cfg in data["configs"].items():
                self._cva6_configs[name] = Cva6FpgaConfig(
                    name=name,
                    description=cfg.get("description", ""),
                    board=cfg.get("board", "genesys2"),
                    target=cfg.get("target", "cv64a6_imafdchzcheri_sv39"),
                    make_target=cfg.get("make_target", "fpga"),
                    bitfile=cfg.get("bitfile", "build/fpga/cv64a6_imafdchzcheri_sv39/genesys2.bit"),
                    flash_script=cfg.get("flash_script", "fpga/scripts/program_genesys2.tcl"),
                )
        return self._cva6_configs

    def get_cva6_config(self, name: str | None) -> Cva6FpgaConfig:
        if name is None:
            name = self.cva6_default_name
        cfg = self.cva6_configs.get(name)
        if cfg is None:
            raise SystemExit(f"Unknown CVA6 FPGA config: {name}")
        return cfg

    # --- Software targets ---

    def _load_sw_raw(self) -> dict:
        data = yaml.safe_load((CONFIG_DIR / "software_targets.yaml").read_text())
        return data

    @property
    def sw_default_name(self) -> str:
        if self._sw_default is None:
            data = self._load_sw_raw()
            self._sw_default = data["default"]
        return self._sw_default

    @property
    def sw_targets(self) -> dict[str, SoftwareTarget]:
        if self._sw_targets is None:
            raw = self._load_sw_raw()
            targets: dict[str, SoftwareTarget] = {}
            for name, cfg in raw["targets"].items():
                kind = cfg["kind"]
                params = {k: v for k, v in cfg.items() if k not in ("kind",)}
                targets[name] = SoftwareTarget(name=name, kind=kind, params=params)
            self._sw_targets = targets
        return self._sw_targets

    def get_sw_target(self, name: str | None) -> SoftwareTarget:
        if name is None:
            name = self.sw_default_name
        tgt = self.sw_targets.get(name)
        if tgt is None:
            raise SystemExit(f"Unknown software target: {name}")
        return tgt

    @property
    def sdk_default_name(self) -> str:
        if self._sdk_default is None:
            data = yaml.safe_load((CONFIG_DIR / "sdk_profiles.yaml").read_text())
            self._sdk_default = data["default"]
        return self._sdk_default

    @property
    def sdk_profiles(self) -> dict[str, SdkProfile]:
        if self._sdk_profiles is None:
            data = yaml.safe_load((CONFIG_DIR / "sdk_profiles.yaml").read_text())
            self._sdk_profiles = {}
            for name, prof in data["profiles"].items():
                self._sdk_profiles[name] = SdkProfile(
                    name=name,
                    description=prof.get("description", ""),
                    source_root=prof.get("source_root"),
                    enable_hybrid_targets=bool(prof.get("enable_hybrid_targets", True)),
                    cheribuild_targets=list(prof.get("cheribuild_targets", [])),
                    extra_args=list(prof.get("extra_args", [])),
                )
        return self._sdk_profiles

    def get_sdk_profile(self, name: str | None) -> SdkProfile:
        if name is None:
            name = self.sdk_default_name
        prof = self.sdk_profiles.get(name)
        if prof is None:
            raise SystemExit(f"Unknown SDK profile: {name}")
        return prof

CONFIG = Config()
EXTERNAL = BASE_DIR / "external"

