# Overview

This demo shows how to run different software stacks on the same CHERI-enabled
CVA6 core implemented on a Genesys2 FPGA board:

- CheriBSD (full OS) via OpenSBI + U-Boot + SD card
- Bao hypervisor + baremetal guest via a monolithic OpenSBI+Bao bundle
- Pure baremetal app via a monolithic OpenSBI+baremetal bundle

The Python CLI (`cheridemo`) hides most of the build complexity and provides
a reproducible path from:

```text
git clone → cheridemo clone → cheridemo build-fpga / build-sw → boot on FPGA
```

