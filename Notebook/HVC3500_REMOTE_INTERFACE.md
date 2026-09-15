# HVC-3500 Remote Interface

This note records what the supplied manuals establish about remote operation of
the LACO VC/HVC-3500. It is a design input, not yet a record of successful
communication with the installed chamber.

## Ethernet answer

Yes, the HVC-3500 is intended to communicate over Ethernet. If the cable seen
leaving the chamber is attached to the controller enclosure's RJ45 connector
labeled **Ethernet**, it can provide:

| Service | Address | Documented purpose |
| --- | --- | --- |
| ASCII over TCP | CPU IP | Programmatic monitoring and control |
| VNC | Panel IP | Remote view and operation of the HMI |
| FTP | Panel IP, port 21 | SD-card data logs and screenshots |

The single RJ45 connection can reach both the Panel and CPU. The addresses in
the manual screenshots are examples and must not be assumed to be this
chamber's addresses.

The controller manual does not document the ASCII TCP port. It may be visible
in the Unitronics **Network -> Ethernet -> CPU TCP** settings or supplied by
LACO in the installation configuration.

## Network safety

The manual suggests direct-computer and facility-network connections. For this
installation, prefer a dedicated lab interface or isolated VLAN. The documented
FTP service is plaintext and uses a static credential printed in the manual;
the manual does not describe authentication for ASCII/TCP or VNC. Do not expose
the controller directly to the public internet.

Do not change Panel or CPU IP settings without first recording the existing
values and confirming that the controller is not using them for remote I/O,
the high-vacuum enclosure, or other devices. LACO explicitly warns that an IP
change can break those connections.

## ASCII transports and framing

Documented transports:

- Ethernet/TCP using the **CPU IP**.
- RS-232 at 9600 baud, 8 data bits, no parity, 1 stop bit.

Documented framing:

- Reads begin with `?`.
- Writes begin with `!`.
- Unrecognized commands return `ER` followed by the line terminator.
- Commands and replies end in carriage return.

The manual writes the carriage return as `0x13`. That is inconsistent with
ASCII: carriage return is decimal 13 and hexadecimal `0x0D`. Treat `\r`
(`0x0D`) as the likely framing byte, but verify this with a read-only query on
the installed controller before relying on it.

## Documented command surface

Every command is terminated by carriage return. `#` characters in the manual
represent numeric fields, not literal characters.

### Cycle and recipe

| Command | Meaning | Important behavior |
| --- | --- | --- |
| `!CS` | Start cycle | Also acts like Start/Continue at a held recipe step |
| `!CA` | Abort cycle | Ends the cycle and begins PLC recovery |
| `?TC` | Test status | Possible response values are not documented |
| `?MC` | System mode | Returns `AUTO` or `MANUAL` |
| `!TR:n` / `?TR` | Select/read recipe | Recipe numbering and bounds need confirmation |
| `?RS` | Current recipe step | Returns a step number |
| `!RS` / `!RO` | Recipe start/stop | Exact relationship to `!CS` needs testing |
| `!CR` | Reset system | Starts the controller recovery/home sequence |

`!CS` is contextual and must not be automatically retried after an uncertain
response: a retry could advance a held step rather than merely confirm start.

### Vacuum process

| Command | Meaning |
| --- | --- |
| `?VP` | Chamber pressure |
| `?PR` | Pressure rate |
| `!VS:value` / `?VS` | Set/read vacuum setpoint |
| `!VR:value` / `?VR` | Set/read vacuum control range |
| `!VD:value` / `?VD` | Set/read vacuum rate control |
| `!VH:value` / `?VH` | Set/read hold time |
| `?TT` | Test time |
| `!VA` | Vent to atmosphere |
| `!FA` | Fill to atmosphere |
| `!PS` | Purge system |
| `!NA` | Close all valves / no vacuum operation |

Pressure values use whichever unit is selected in Advanced Settings. No ASCII
command is documented for querying that unit. The driver configuration must
record the unit and commissioning must confirm that it agrees with the HMI.
The maintenance screen example shows scientific notation in a pressure reply,
so parsing should accept both decimal and scientific notation.

### Temperature and thermal control

| Command | Meaning |
| --- | --- |
| `?Tn` | Read temperature input `n`; storage exists for 21 inputs |
| `!Zn:value` / `?Zn` | Set/read temperature setpoint for zone `n` |
| `!ZRn:value` / `?ZRn` | Set/read zone temperature-rate setpoint |
| `!RTn:value` / `?RTn` | Set/read zone temperature control range |
| `!ZSn` | Activate thermal control for zone `n` |
| `!ZOn` | Deactivate thermal control for zone `n` |
| `!FN:value` | Fan RPM command; detailed semantics are not documented |

The standard software supports up to three zones and 21 temperature inputs.
Temperature and thermal-range values are encoded in tenths with no decimal
point: `855` represents `85.5` in the configured temperature unit. The HMI can
be configured for Celsius or Fahrenheit, and no ASCII unit query is documented.

The chamber-specific system manual describes two thermal functions, shroud and
platen, but does not state which is HVC zone 1 or zone 2. It also does not map
physical sensors to `T0` through `T20`.

### Faults and warnings

`?ES` returns a severity and a decimal UINT32 bitmask:

```text
ES: N|W|F: decimal-mask
```

- `N` - no warning or fault.
- `W` - warning active.
- `F` - fault active.
- Bit position `n` corresponds to fault/warning number `n` in section 7.

The manual's combined example for faults 20 and 22 is internally inconsistent.
By its stated bit-position rule the value should be `2^20 + 2^22 = 5242880`,
but the example reports `4194304`, which represents bit 22 alone. Implement the
documented bit rule, retain unknown bits, and verify it against controlled or
observed chamber faults.

Section 7 documents these identifiers:

| Number | Meaning |
| ---: | --- |
| 0 | Abort |
| 1 | Evac/Rough timeout |
| 2 | Vent-to-atmosphere timeout |
| 3 | Fill-to-atmosphere timeout |
| 4 | High-vacuum warning |
| 5 | Soft overtemperature |
| 6 | Gauge disconnected |
| 16 | Control air low |
| 17 | Hard overtemperature; requires physical Watlow reset |
| 18 | Gate valve not opening |
| 19 | Gate valve not closing |
| 20 | Chiller communications |
| 21 | PLC/HMI-to-I/O communications |
| 22 | High-vacuum enclosure communications |
| 23 | Turbo fault |
| 24 | Door open / massive leak |
| 25 | Foreline pressure |
| 26 | Chiller response |
| 27 | Watlow communications |
| 28 | Thermocouple-card communications |

User-configurable warnings can become faults after a configured delay. A fault
ends the cycle and turns off outputs. Abort/reset sends the system through its
home/recovery sequence. A hard overtemperature does not clear automatically
and requires a physical reset at the Watlow controller.

### Direct valve and pump commands

| Write toggle | Read status | Device |
| --- | --- | --- |
| `!OR` | `?OR` | Rough valve |
| `!OV` | `?OV` | Vent valve |
| `!OF` | `?OF` | Fill valve |
| `!O4` | `?O4` | Foreline valve |
| `!OG` | `?OG` | High-vacuum gate valve |
| `!OP` | `?OP` | Vacuum pump |
| `!OT` | `?OT` | Turbo pump |

Status is `C` for closed/off or `O` for open/on.

These writes are toggles, not desired-state commands. The response describes
the state at command receipt; the actual change occurs about one second later.
Consequences:

- Never blindly retry a toggle after a timeout or lost response.
- Read the current state before deciding whether to toggle.
- Send at most one toggle.
- Wait beyond the documented actuation delay, then read and verify the state.
- Keep this surface out of ordinary automation routines unless a maintenance
  workflow explicitly requires it.

## PLC-owned safety behavior

The controller retains interlocks in manual operation, and ASCII automation
should leave the PLC as the safety authority. Documented examples include:

- Evac requires the vacuum pump to have run for 10 seconds and the vent, fill,
  foreline, and gate valves to be closed.
- Vent and fill require gate and vacuum valves closed.
- Foreline requires the vacuum pump to have run for 10 seconds and the vacuum
  valve closed.
- Turbo start requires the foreline valve open and foreline pressure in its OK
  range: OK at or below 0.2 Torr, lost above 0.5 Torr.
- Gate requires chamber pressure below crossover, turbo running, and foreline
  open.
- The vacuum pump cannot stop while foreline or evac is open.
- Venting is constrained by configured minimum and maximum temperatures. The
  PLC can run a temperature-recovery cycle before venting.

Normal software should request high-level operations and setpoints rather than
reimplement these sequences or attempt to bypass the PLC.

## ASCII-controlled recipe setup

To let external software drive a process:

1. Enable **ASCII in Recipe** in Advanced Settings.
2. Select `ASCII` as the recipe's vacuum operation.
3. Set the recipe trigger to hold.
4. Start the recipe locally or with `!CS`.
5. Issue setpoint and status commands while the PLC maintains interlocks.

The manual says ASCII commands can also be sent during a cycle or manual mode,
but an externally orchestrated full cycle should use the explicit ASCII recipe
configuration.

## Data and operator access

- The controller can log CSV data to its internal microSD card.
- Process logging can run automatically during recipe cycles.
- FTP exposes the `DT` folder containing data logs and the `Media` folder
  containing screenshots.
- The FTP host is the Panel IP and the port is 21. Credentials are printed in
  section 5.1.3 of the controller manual and are intentionally not duplicated
  in this notebook.
- VNC connects to the Panel IP and presents the HMI for human operation.

`formsLabCLI` should use ASCII/TCP for automation. VNC is useful for setup and
observation, while FTP is useful for retrieving controller-native logs.

## Facts to collect at the chamber

Record these before enabling any write command:

- [ ] Confirm the observed cable is connected to the RJ45 port labeled
      **Ethernet**.
- [ ] Panel IP, subnet mask, and gateway.
- [ ] CPU IP, subnet mask, and gateway.
- [ ] ASCII TCP listening port / CPU TCP socket configuration.
- [ ] Installed HVC application software revision.
- [ ] Whether **Enable ASCII in Recipe** is enabled.
- [ ] A dedicated test recipe configured with an ASCII step and hold trigger.
- [ ] Configured pressure unit.
- [ ] Configured temperature unit.
- [ ] Zone mapping: shroud/platen to HVC zone numbers.
- [ ] Sensor mapping: physical names and locations to `T0`-`T20`.
- [ ] Which zones and sensors are actually enabled on this custom system.
- [ ] Read-only response to `?MC`, `?TC`, `?VP`, `?ES`, and mapped temperature
      queries using the verified TCP terminator.
- [ ] Behavior on an unrecognized read command.
- [ ] Whether TCP permits one request per connection or a persistent session.
- [ ] Maximum safe polling cadence and response timeout.

## Source locations

- `HVC 3500 Manual.pdf`: sections 4.3.4-4.3.8, 5, 6.4, 7, and appendix 9.1;
  especially pages 16-22, 29-34, 36-42, and 44-53.
- Chamber-specific system manual: equipment and safety descriptions on pages
  7-9, 16-18, 23-24, and 27-28.
