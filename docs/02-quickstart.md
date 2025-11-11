# Quickstart

Assuming a reasonably recent Ubuntu with Python 3.10+:

```bash
git clone <this-repo>
cd cheribsd-on-cva6-cheri-genesys2
python -m venv .venv
source .venv/bin/activate
pip install -e .

cheridemo clone
cheridemo list-configs
cheridemo list-sw
```

Then follow the steps in the top-level README for:

- building the FPGA bitstream,
- building the CheriBSD / Bao / baremetal software stacks,
- preparing an SD card (for CheriBSD),
- flashing the FPGA.

