# CVA6-CHERI Demos (Genesys2 FPGA)

This repository presents a set of **reproducible demos** on a
CVA6-CHERI core deployed in a **Genesys2 FPGA board**:

- **CheriBSD path**: CheriBSD (FreeBSD with CHERI) running on CVA6-CHERI, booted via
  OpenSBI + U-Boot, with the CheriBSD rootfs stored on an SD card.
- **Bao path**: Bao hypervisor running on CVA6-CHERI, with a baremetal guest, all
  bundled together in a single binary (OpenSBI + Bao + guest) that can be used as a
  boot ROM / SPI flash image.
- **Baremetal path**: A single baremetal application (no hypervisor, no U-Boot),
  again bundled as a monolithic OpenSBI + baremetal binary.

The goal is that a user can:

1. Clone this repo
2. Run a small Python CLI (`cheridemo`) to:
   - clone all upstream projects,
   - build the CHERI toolchain + CheriBSD,
   - build OpenSBI, U-Boot, Bao, and a baremetal guest,
   - build the CVA6-CHERI bitstream for Genesys2,
   - prepare an SD card (for CheriBSD),
3. And then see **CheriBSD, Bao+guest, or a baremetal demo** booting on the same FPGA
   hardware.

> **NOTE:** All build commands here are templates. You will need to adjust the
> `make` arguments, OpenSBI platform names, U-Boot defconfig, and artifact paths
> to match your actual CVA6-CHERI, Bao, and CheriBSD integrations.


## Repository layout

- `cheridemo/` – Python package with the CLI and helper modules
  - `cli.py` – Typer-based CLI entrypoint (`cheridemo ...`)
  - `config.py` – Loads YAML config for repos, FPGA configs, and software targets
  - `utils.py` – Small helpers for running commands and cloning repos
  - `build.py` – Cloning repos and building the CHERI SDK via cheribuild
  - `fpga.py` – Building and flashing the FPGA bitstream for Genesys2
  - `boot.py` – Building OpenSBI, U-Boot, Bao bundles, baremetal bundles
  - `sw.py` – High-level software target builder (CheriBSD, Bao, baremetal)
  - `sdcard.py` – Preparing an SD card with a CheriBSD rootfs image
- `configs/`
  - `repos.yaml` – URLs and branches/commits for cheribuild, cheri-cva6, opensbi,
    u-boot, Bao, and your baremetal demo repo
  - `cva6_configs.yaml` – Named FPGA configurations (e.g., 1-core vs 2-core)
  - `software_targets.yaml` – Named software targets:
    - `cheribsd` (CheriBSD + OpenSBI + U-Boot + SD card rootfs)
    - `bao-baremetal` (OpenSBI + Bao + baremetal guest bundle)
    - `baremetal` (OpenSBI + baremetal bundle)
- `docs/`
  - `01-overview.md` – Short conceptual overview
  - `02-quickstart.md` – End-to-end command sequence
  - `03-boot-chains.md` – ASCII diagrams of the CheriBSD and Bao boot chains


## Installing the demo tool

You need Python 3.10+.

```bash
git clone <this-repo>
cd cheribsd-on-cva6-cheri-genesys2

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
- `cheri-cva6` (CVA6-CHERI fork)
- `opensbi`
- `uboot`
- `bao`
- `baremetal-demo`


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

> Edit `cheridemo/fpga.py` and `configs/cva6_configs.yaml` to match your actual
> CVA6-CHERI build (board name, config file, make target, bitfile path).


### Flashing the FPGA

The `flash-fpga` command is a placeholder, because different environments use
different tools (Vivado, openFPGALoader, etc.):

```bash
cheridemo flash-fpga --config cva6_cheri_1core
```

Update `cheridemo/fpga.py` to call your preferred tool with the correct bitstream
(or SPI flash image).


## CheriBSD path (OpenSBI + U-Boot + SD rootfs)

This software target is called **`cheribsd`** in `software_targets.yaml`.

### 1. Build the CHERI SDK + CheriBSD + boot chain

```bash
cheridemo build-sdk            # optional; build-sw will also build the SDK
cheridemo build-sw --target cheribsd
```

This does three things:

1. Builds the RISC-V CHERI SDK via cheribuild (`sdk-riscv64-purecap`)
2. Builds CheriBSD for RISC-V CHERI (`cheribsd-riscv64-purecap`)
3. Builds the **boot chain**:
   - U-Boot for your CVA6-CHERI Genesys2 platform
   - OpenSBI using U-Boot as the `FW_PAYLOAD_PATH`, producing a single
     `fw_payload.bin` that you can use as a ROM/SPI flash image in your FPGA design


### 2. Prepare the SD card

Cheribuild produces a CheriBSD rootfs image (by default under `~/cheri/output/`).
The `software_targets.yaml` entry for `cheribsd` tells the tool which image to use.

Write it to an SD card (**this will erase the card**):

```bash
cheridemo prepare-sd --device /dev/sdX --target cheribsd
```

### 3. Boot chain diagram

CheriBSD path:

```text
Reset
  ↓
OpenSBI (fw_payload.bin)
  └─ payload: U-Boot
         ↓
    U-Boot
      └─ loads kernel + FDT from SD
           and mounts CheriBSD rootfs from SD
              ↓
        CheriBSD (FreeBSD with CHERI)
```


## Bao path (OpenSBI + Bao + baremetal guest bundle)

This software target is called **`bao-baremetal`** in `software_targets.yaml`.

### 1. Build the bundle

```bash
cheridemo build-sw --target bao-baremetal
```

This:

1. Builds the **baremetal guest** in `external/baremetal-demo` (e.g., a small
   CHERI-aware application)
2. Builds the **Bao hypervisor** using a configuration file that describes your
   CVA6-CHERI / Genesys2 platform and the guest layout
3. Builds **OpenSBI** using Bao as `FW_PAYLOAD_PATH`, producing one monolithic
   `bao_bundle.bin` that contains:
   - OpenSBI
   - Bao hypervisor
   - embedded baremetal guest image (according to your Bao config)

You can then use this bundle as the ROM/SPI flash contents in your FPGA flow.

### 2. Boot chain diagram

Bao bundle path:

```text
Reset
  ↓
OpenSBI (bao_bundle.bin)
  └─ payload: Bao hypervisor
         ↓
       Bao
        └─ boots baremetal guest
              ↓
      Baremetal guest (no OS, runs on CVA6-CHERI)
```


## Baremetal path (OpenSBI + baremetal bundle)

This software target is called **`baremetal`**.

```bash
cheridemo build-sw --target baremetal
```

This:

1. Builds a baremetal app in `external/baremetal-demo`
2. Builds OpenSBI with that app as `FW_PAYLOAD_PATH`, producing
   `baremetal_bundle.bin`

Boot chain:

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

# 1. Build FPGA bitstream for Genesys2
cheridemo build-fpga --config cva6_cheri_1core

# 2-a. CheriBSD demo:
cheridemo build-sw --target cheribsd
cheridemo prepare-sd --device /dev/sdX --target cheribsd
# → flash bitstream + OpenSBI+U-Boot fw_payload into your ROM/SPI
# → power on, CheriBSD boots from SD

# 2-b. Bao + baremetal demo:
cheridemo build-sw --target bao-baremetal
# → use bao_bundle.bin as ROM/SPI image in your FPGA design

# 2-c. Pure baremetal demo:
cheridemo build-sw --target baremetal
# → use baremetal_bundle.bin as ROM/SPI image
```

From here you can:

- Fill in the real `make` commands for your CVA6-CHERI FPGA flow
- Pin concrete commits in `configs/repos.yaml`
- Point `software_targets.yaml` to your actual Bao config files and baremetal ELF paths
- Add more CVA6 configs (e.g., 2-core, different memory maps)

