# TVAC Ethernet Remote Control

Last reviewed: 2026-09-28

Tools and notes for connecting the University of Illinois LACO thermal vacuum
chamber (VC/HVC-3500 controller) to a computer over Ethernet for monitoring
and, after commissioning, control.

## Status

- **Program: done and bench-tested.** The `hvc3500` package implements the
  documented ASCII/TCP interface with a safety model matched to the chamber
  (no retries, verified setpoints, gated actions, read-first toggles). 40
  tests pass against a protocol simulator; every CLI command was exercised.
- **Live chamber: read path proven (2026-09-17).** CPU IP **10.1.2.121**,
  ASCII socket **port 1**, CR-terminated; `?MC` answers, all 49 documented
  reads answer, `probe`/`lifecycle`/`snapshot` pass. Panel IP is 10.1.2.120
  (VNC 5900, FTP 21). The PC reaches it via `Ethernet 3` with a secondary
  address 10.1.2.200/24 (`tools\find_hvc.ps1 -AddAddress`).
- **Config confirmed (2026-09-24):** Torr, degrees C, zone 1 = platen (sensor
  T2), zone 2 = shroud (sensor T3). Setpoint writes persist (`!Zn` sets the
  commanded value shown on the HMI; `?Zn` reads the effective value, which
  tracks the sensor while the zone is idle). `!ZSn` does not start manual
  thermal control on this firmware; the recipe path is next.
- **First autonomous control (2026-09-24):** rough pump-down 82 -> 1.95 Torr
  in 4 min 22 s with `tools/pumpdown_test.py`, no faults.
- **formsLabCLI:** `run laco` loads `rScripts/rTVAC_LACO.py`, which publishes
  the chamber to the CAST block `hvc` and accepts setpoint/control requests
  (see that repo's `rScripts/README.md`). Not yet run on the bench.
- See `Notebook/TVAC_ETHERNET_PROGRESS.md` for the dated log and raw frames.

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

```powershell
# from the repo root, with any Python 3.11+ (the formsLabCLI venv works)
python -m pytest tests                         # protocol + simulator tests
python -m hvc3500 simulate --port 20256        # fake controller (separate window)
python -m hvc3500 probe --host 127.0.0.1 --port 20256

# on the real chamber (PC needs 10.1.2.x on Ethernet 3; see tools\find_hvc.ps1)
python -m hvc3500 probe     --host 10.1.2.121 --port 1
python -m hvc3500 lifecycle --host 10.1.2.121 --port 1
python -m hvc3500 snapshot  --config bench\tvac_bench.toml
python -m hvc3500 watch     --config bench\tvac_bench.toml --interval 5
python -m hvc3500 set-zone  --config bench\tvac_bench.toml 1 19.3   # verified setpoint write
python tools\vnc_shot.py 10.1.2.120 --password <HMI VNC password> --out hmi.png
python tools\pumpdown_test.py --target-torr 2 --max-min 4     # supervised rough pump-down (passed 2026-09-24)
```

To watch the touchscreen from a PC, use a VNC viewer against the Panel IP
(`vncviewer64.exe 10.1.2.120:5900`, portable TigerVNC works). As installed,
the session is **view-only**. UniApps -> Network -> VNC Server has no setting
for this (checked 2026-09-29); it is most likely a separate full-control VNC
password in LACO's controller application - ask LACO. VNC is for humans;
software control goes over the ASCII/TCP link.

`probe` is the first discriminating test from the notes: connect, `?MC<CR>`,
then `?TC`, `?VP`, `?ES`, then an unknown command that must return `ER`. Its
exit code and messages tell you which layer failed. All commands append a
JSONL log of raw frames to `logs/`.

## Layout

| Path | Contents |
| --- | --- |
| `hvc3500/protocol.py` | Framing, parsing, fault decoding (pure, unit-tested) |
| `hvc3500/client.py` | TCP client, typed reads, guarded writes, transaction log |
| `hvc3500/simulator.py` | Fake HVC-3500 for bench-less testing |
| `hvc3500/cli.py` | `probe`, `lifecycle`, `raw`, `snapshot`, `watch`, `set-zone`, `set-vacuum`, `device`, `discover`, `simulate` |
| `bench/tvac_bench.example.toml` | Endpoint, units, zone and sensor mapping template |
| `tests/` | pytest suite |
| `tools/find_hvc.ps1` | Elevated helper to find the controller's subnet from ARP traffic |
| `Notebook/TVAC_ETHERNET_CONNECTION.ipynb` | Runnable commissioning walkthrough |
| `Notebook/HVC3500_REMOTE_INTERFACE.md` | Protocol, command surface, safety behaviour, open questions |
| `Notebook/FORMSLAB_TVAC_CONTEXT.md` | How this fits the `formsLabCLI` architecture |
| `Notebook/TVAC_ETHERNET_PROGRESS.md` | Dated progress log and commissioning checklist |
| `Notebook/2026-09-24_SESSION_SUMMARY.md` | One-page summary of the 2026-09-24 session: config confirmed, setpoint semantics, first autonomous pump-down |
| `docs/HVC 3500 Manual.pdf` | HVC-3500 controller manual (rev A16) |
| `docs/UNIV. OF ILLINOIS ... Rev A.pdf` | Chamber-specific system manual (FCT3048ELSSSE-1P35531) |
| `bench/tvac_bench.toml` | Confirmed live bench profile for this chamber |

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
