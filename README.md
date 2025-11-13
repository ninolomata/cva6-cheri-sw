# CVA6-CHERI Demos (Genesys2 FPGA)

This repository presents a set of **reproducible demos** on a
CVA6-CHERI core deployed in a **Genesys2 FPGA board**:

- **CheriBSD path**: CheriBSD (FreeBSD with CHERI) running on CVA6-CHERI, booted via
  OpenSBI + U-Boot, with the CheriBSD rootfs stored on an SD card.
- **Baremetal path**: A single baremetal application (no hypervisor, no U-Boot),
  again bundled as a monolithic OpenSBI + baremetal binary.

The goal is that a user can:

1. Clone this repo
2. Run a small Python CLI (`cheridemo`) to:
   - clone all upstream projects,
   - build the CHERI toolchain + CheriBSD,
   - build OpenSBI, U-Boot, and a baremetal application,
   - build the CVA6-CHERI bitstream for Genesys2,
   - prepare an SD card (for CheriBSD),
3. And then see **CheriBSD or a baremetal demo** booting on the same FPGA
   hardware.

## Repository layout

- `cheridemo/` – Python package with the CLI and helper modules
  - `cli.py` – Typer-based CLI entrypoint (`cheridemo ...`)
  - `config.py` – Loads YAML config for repos, FPGA configs, and software targets
  - `utils.py` – Small helpers for running commands and cloning repos
  - `build.py` – Cloning repos and building the CHERI SDK via cheribuild
  - `fpga.py` – Building and flashing the FPGA bitstream for Genesys2
  - `boot.py` – Building OpenSBI, U-Boot, Bao bundles, baremetal bundles
  - `sw.py` – High-level software target builder (CheriBSD, OpenSBI, U-Boot, baremetal)
  - `sdcard.py` – SD Card utils
- `configs/`
  - `repos.yaml` – URLs and branches/commits for cheribuild, cheri-cva6, opensbi,
    u-boot, Bao, and your baremetal demo repo
  - `cva6_configs.yaml` – Named FPGA configurations
  - `software_targets.yaml` – Named software targets:
    - `cheribsd-demop` (CheriBSD + OpenSBI + U-Boot + SD card)
    - `baremetal-demo` (OpenSBI + Baremetal Application bundle)


## Installing the demo tool

You need Python 3.10+.

```bash
git clone <this-repo>
cd cva6-cheri-sw

# (Optional) Create a virtualenv
python -m venv .venv
source .venv/bin/activate

# Install the CLI in editable mode
pip install -e .
```

You should now have a `cheridemo` command available.

Check it works:

```bash
cheridemo --help
```

## Cloning upstream repos

All upstream repos are defined in `configs/repos.yaml`.

```bash
cheridemo clone
```

This creates an `external/` directory and clones:

- `cheribuild`
- `cheri-cva6` (CVA6-CHERI)
- `opensbi`
- `bao-baremetal-guest`
- `u-boot-cva6-cheri`

## Building SDK

Builds sdk profiles located at `sdk_profiles.yaml`.

```bash
cheridemo build-sdk
```

## Building the FPGA bitstream (Genesys2 only)

You can list available CVA6 FPGA configs:

```bash
cheridemo list-configs
```

By default, the tool uses `cva6_cheri_1core` from `configs/cva6_configs.yaml`.

Build the bitstream:

```bash
cheridemo build-fpga
# or explicitly:
cheridemo build-fpga --config cva6_cheri_1core
```


### Flashing the FPGA

The `flash-fpga` command is a placeholder, because different environments use
different tools (Vivado, openFPGALoader, etc.):

```bash
cheridemo flash-fpga --config cva6_cheri_1core
```

## CheriBSD Demo (OpenSBI + U-Boot + SD rootfs)

This software target is called **`cheribsd`** in `software_targets.yaml`.

### 1. Build the CheriBSD + boot chain

```bash
cheridemo build-sw --t cheribsd-demo
```

This does three things:

1. Builds CheriBSD for RISC-V CHERI (`cheribsd-mfs-root-kernel-riscv64-purecap`)
2. Builds the **boot chain**:
   - U-Boot for your CVA6-CHERI Genesys2 platform
   - OpenSBI using U-Boot as the `FW_PAYLOAD_PATH`, producing a single
     `fw_payload.bin` that you can use as a ROM/SPI flash image in your FPGA design

### 2. Prepare the SD card

Cheribuild produces a CheriBSD U-Boot image (by default under `~/cheri/output/cheribsd-demo`).
The `software_targets.yaml` entry for `cheribsd` tells the tool which image to use.

Write it to an SD card (**this will erase the card**):

```bash
cheridemo format-sd -t cheribsd-demo --device /dev/sdX
cheridemo flash-sd -t cheribsd-demo --device /dev/sdX
```

### 3. Boot chain diagram

CheriBSD boot chain path:

```text
Reset
  ↓
OpenSBI (fw_payload.bin)
  └─ payload: U-Boot
         ↓
    U-Boot
      └─ loads kernel + FDT from SD
              ↓
        CheriBSD (FreeBSD with CHERI)
```

## Baremetal Application Demo (OpenSBI + baremetal bundle)

This software target is called **`baremetal-demo`**.

### 1. Build the Baremetal Applcation Boot Chain
```bash
cheridemo build-sw --t baremetal-demo
```

This:

1. Builds a baremetal app in `external/baremetal-demo`
2. Builds OpenSBI with that app as `FW_PAYLOAD_PATH`, producing
   `opensbi-fw.bin`

### 2. Prepare the SD card

Writes the `opensbi-fw.bin` produced by opensbi to the SD card (**this will erase the card**):

```bash
cheridemo format-sd -t baremetal-demo --device /dev/sdX
cheridemo flash-sd -t baremetal-demo --device /dev/sdX
```

### 3. Boot chain diagram

Baremetal application boot chain path:

```text
Reset
  ↓
OpenSBI (baremetal_bundle.bin)
  └─ payload: baremetal app
         ↓
      Baremetal app
```


## Quick start summary

Just to collect everything in one place:

```bash
# 0. Install and clone
pip install -e .
cheridemo clone

# 1. Install sdk
cheridemo build-sdk


# 2. Build FPGA bitstream for Genesys2
cheridemo build-fpga --config cva6_cheri_1core

# 3-a. CheriBSD demo:
cheridemo build-sw --target cheribsd
cheridemo format-sd -t cheribsd-demo --device /dev/sdX
cheridemo flash-sd -t cheribsd-demo --device /dev/sdX
# → power on, CheriBSD boots from SD

# 2-b. baremetal demo:
cheridemo build-sw --target bao-baremetal
cheridemo format-sd -t baremetal-demo --device /dev/sdX
cheridemo flash-sd -t baremetal-demo --device /dev/sdX
# → use opensbi-fw.bin as the image to boot from SD

```