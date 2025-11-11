# Boot chains

## CheriBSD path

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

## Bao bundle path

```text
Reset
  ↓
OpenSBI (bao_bundle.bin)
  └─ payload: Bao hypervisor
         ↓
       Bao
        └─ boots baremetal guest
              ↓
      Baremetal guest (no OS)
```

## Baremetal bundle path

```text
Reset
  ↓
OpenSBI (baremetal_bundle.bin)
  └─ payload: baremetal app
         ↓
      Baremetal app (no OS)
```

