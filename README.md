# TVAC Ethernet Remote Control

Last reviewed: 2026-09-28

Tools and notes for connecting the University of Illinois LACO thermal vacuum
chamber (VC/HVC-3500 controller) to a computer over Ethernet for monitoring
and, after commissioning, control.

## Status

**The HVC-3500 driver, its command-line tool, simulator, tests and protocol
notes now live in formsLabCLI** (https://github.com/phi-a/formsLabCLI):
`src/formslab/devices/hvc3500/`, `docs/HVC3500.md`. That is the one maintained
copy; this repo's `hvc3500/` package was removed (2026-10-02), and its history
keeps the commissioning versions.

This repo is the commissioning record: dated notes (`Notebook/`), raw frame
logs (`logs/`), the manuals (`docs/`), the confirmed bench profile as found
(`bench/tvac_bench.toml`, superseded by formsLabCLI's `tvac_bench.json`), and
HMI helpers (`tools/`).

Milestones: read path proven 2026-09-17 (CPU 10.1.2.121, ASCII port 1);
configuration confirmed 2026-09-24; first autonomous rough pump-down
2026-09-24 (82 -> 1.95 Torr); remote vent and pump-down from formsLabCLI
2026-10-01. See `Notebook/TVAC_ETHERNET_PROGRESS.md`.

## Connection model

The controller enclosure RJ45 port labelled **Ethernet** exposes two addresses:

| Service | Address | Purpose |
| --- | --- | --- |
| ASCII over TCP | CPU IP | Programmatic monitoring and control (this package) |
| VNC | Panel IP | Human HMI view and operation |
| FTP, port 21 | Panel IP | Controller logs (`DT/`) and screenshots (`Media/`) |

Read the real addresses and the **CPU TCP** port from the HMI: *UniApps ->
Network -> Ethernet*. The manual's `172.16.21.74/.75` are screenshot examples.

## Quick start

From a formsLabCLI checkout's venv (the PC needs 10.1.2.x on Ethernet 3; see
`tools\find_hvc.ps1`):

```powershell
python -m formslab.devices.hvc3500 simulate --port 20256      # fake controller (separate window)
python -m formslab.devices.hvc3500 probe --host 127.0.0.1 --port 20256
python -m formslab.devices.hvc3500 probe                      # the real chamber, from the bench profile
python -m formslab.devices.hvc3500 snapshot
python -m formslab.devices.hvc3500 watch --interval 5
python tools\vnc_shot.py 10.1.2.120 --password <HMI VNC password> --out hmi.png
```

For operation use the formsLabCLI console: `run tvac`, then the cast tab
(`hvc ...`), or the `laco_pumpdown` / `laco_vent` plans.

## Layout

| Path | Contents |
| --- | --- |
| `bench/tvac_bench.example.toml` | Endpoint, units, zone and sensor mapping template |
| `tools/find_hvc.ps1` | Elevated helper to find the controller's subnet from ARP traffic |
| `Notebook/TVAC_ETHERNET_CONNECTION.ipynb` | Runnable commissioning walkthrough |
| `Notebook/HVC3500_REMOTE_INTERFACE.md` | Pointer: the protocol notes live in formsLabCLI `docs/HVC3500.md` |
| `Notebook/FORMSLAB_TVAC_CONTEXT.md` | How this fits the `formsLabCLI` architecture |
| `Notebook/TVAC_ETHERNET_PROGRESS.md` | Dated progress log and commissioning checklist |
| `Notebook/2026-09-24_SESSION_SUMMARY.md` | One-page summary of the 2026-09-24 session: config confirmed, setpoint semantics, first autonomous pump-down |
| `docs/HVC 3500 Manual.pdf` | HVC-3500 controller manual (rev A16) |
| `docs/UNIV. OF ILLINOIS ... Rev A.pdf` | Chamber-specific system manual (FCT3048ELSSSE-1P35531) |
| `bench/tvac_bench.toml` | The bench profile as confirmed in commissioning (operational copy: formsLabCLI `tvac_bench.json`) |
| `tools/pumpdown_test.py` | The first supervised pump-down (2026-09-24); uses formsLabCLI's driver |

## Write safety

| Class | Commands | Client behaviour |
| --- | --- | --- |
| Setpoint (idempotent) | `!VS !VR !VD !VH !TR !Zn !ZRn !RTn` | Written, then read back and compared |
| Action (state-changing) | `!CS !CA !CR !RS !RO !VA !FA !PS !NA !ZSn !ZOn` | `confirm=True` required; never retried |
| Toggle (valve/pump) | `!OR !OV !OF !O4 !OG !OP !OT` | `confirm=True`; read first, at most one toggle, wait, verify |

The PLC stays the authority for interlocks, sequencing, thermal limits and
recovery. Do not expose VNC, FTP or the ASCII port to the public internet, and
do not change the controller's IP settings without recording them and checking
with LACO (remote I/O and the high-vacuum enclosure depend on them).

## Commissioning order

1. Isolate the network (dedicated adapter or VLAN).
2. Record Panel IP, CPU IP, mask, gateway, CPU TCP port, software revision,
   units, zone and sensor mapping, and the *Enable ASCII in Recipe* setting.
3. `probe`, then `lifecycle`, then `snapshot` compared against the HMI.
4. One supervised idempotent write (`set-zone` to the current value).
5. Only inside a supervised ASCII-recipe test: actions and toggles.
