# TVAC Ethernet Remote-Control Readme

Last reviewed: 2026-09-15

This folder documents how to connect the University of Illinois LACO thermal
vacuum chamber to a computer for remote monitoring and, after commissioning,
remote control.

## Result of the review

The HVC-3500 controller supports an ASCII command interface over Ethernet/TCP.
The correct physical connection is the controller enclosure RJ45 port labeled
**Ethernet**. That connection exposes two logical controller addresses:

| Service | Address | Purpose |
| --- | --- | --- |
| ASCII over TCP | CPU IP | Programmatic monitoring and control |
| VNC | Panel IP | Human HMI view and operation |
| FTP, port 21 | Panel IP | Controller logs and screenshots |

The CPU IP, Panel IP, and ASCII TCP port shown in a manual or screenshot must
not be assumed to be the values for the installed chamber. The actual values
must be read from the HMI or supplied by the installer.

## Files in this folder

- [HVC3500_REMOTE_INTERFACE.md](HVC3500_REMOTE_INTERFACE.md) records the
  protocol, command surface, safety behavior, and known uncertainties.
- [FORMSLAB_TVAC_CONTEXT.md](FORMSLAB_TVAC_CONTEXT.md) records how the chamber
  should fit into the existing `formsLabCLI` architecture.
- [TVAC_ETHERNET_PROGRESS.md](TVAC_ETHERNET_PROGRESS.md) is the dated progress
  log and commissioning checklist.
- [TVAC_ETHERNET_CONNECTION.ipynb](TVAC_ETHERNET_CONNECTION.ipynb) explains the
  process and contains a read-only Python TCP probe.

## Process used

### 1. Inspect the source material

The review covered both PDFs in the parent `tvac` folder, the existing notes in
`Notebook`, and the empty `tmp` folder. The HVC manual supplies the Ethernet,
VNC, FTP, ASCII framing, command, recipe, and safety information. The
chamber-specific manual identifies the installed system as the LACO thermal
vacuum chamber and describes the shroud/platen functions, but it does not
provide the installed CPU address, TCP port, or complete sensor numbering.

### 2. Isolate the network

Use a dedicated lab Ethernet adapter or isolated VLAN. Do not expose the
controller directly to the public internet. Do not change controller network
settings until the existing values and any device dependencies are recorded.

### 3. Record the installed configuration

At the HMI, record:

- Panel IP, CPU IP, subnet mask, and gateway.
- Unitronics `Network -> Ethernet -> CPU TCP` listening port.
- Installed HVC application/software revision.
- Pressure and temperature units.
- Shroud/platen mapping to HVC zones.
- Physical sensor mapping to `T0` through `T20`.
- Whether `Enable ASCII in Recipe` is enabled.

The HMI values are the source of truth for this installation. Do not use
example addresses from the manual.

### 4. Prove the read-only path

The first test is:

```text
TCP connect to CPU_IP:CPU_TCP_PORT
send: ?MC followed by carriage return
```

Use `\\r` (`0x0D`) as the initial carriage return. The manual notes contain a
conflicting `0x13` notation, so the actual reply framing must be recorded.
The expected result is a mode response such as `AUTO` or `MANUAL`; `ER` proves
the service answered but the command or installed configuration differs.

After `?MC` succeeds, query only read commands such as `?TC`, `?VP`, and `?ES`.
Record raw replies, timestamps, endpoint, connection lifecycle, timeout, and
polling behavior in the progress log.

### 5. Commission control gradually

Before any write, compare read-only values with the HMI and verify units and
zone mapping. Then add only one idempotent setpoint write under operator
supervision, poll it, and verify the resulting controller state.

Do not blindly retry commands that may change state. `!CS` can start or
continue a held recipe step. Valve and pump commands are toggles with delayed
physical effect. Read state first, send at most one toggle, wait, and verify.

The HVC PLC remains authoritative for interlocks, vacuum sequencing, thermal
limits, faults, and recovery. Remote software should request high-level
operations and setpoints rather than reproduce or bypass PLC safety logic.

## Current status

The documented network path is identified, but live communication has not yet
been proven because the installed CPU IP, TCP port, units, and zone/sensor
mapping have not been recorded. The next milestone is a read-only snapshot
from the installed controller. Only after that snapshot matches the HMI should
the `formsLabCLI` transport and controlled writes be implemented.

## Source manuals

- `../HVC 3500 Manual.pdf` - controller manual, revision A16, including remote
  connection information in section 5 and communications commands in appendix
  9.1.
- `../UNIV. OF ILLINOIS, FCT3048ELSSSE-1P35531, FEB 2026, Rev A.pdf` -
  chamber-specific system manual.

Keep confirmed manual facts, observed chamber configuration, tested protocol
behavior, and proposed software design explicitly separated as this work
continues.
