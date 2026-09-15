# `formsLabCLI` TVAC Integration Context

This note captures the current repository architecture and confirmed planning
constraints. It deliberately stops short of choosing the final implementation.

Repository reviewed: `C:/Users/darkn/Desktop/formsLabCLI`

## Existing separation

The repository already has the beginnings of the desired structure:

- `src/formslab/devices/` contains reusable hardware transports and drivers.
- `rScripts/` contains workspace-specific hardware automation routines.
- `FORMSLAB_CONFIG_DIR` selects persistent per-bench configuration.
- CAST provides a local request/status exchange between the console and the
  running sequence host.

This suggests a vendor driver should live with devices, while chamber- or
mission-specific behavior should remain in `rScripts`.

## What is not generic today

The existing TVAC path represents the previous bench rather than a general
thermal-vacuum controller:

- `rScripts/rTVAC.py` directly owns a Rigol PSU, one RTD board, two SMTC08
  thermocouple boards, and a local heater-control loop.
- It hardcodes `PY` and `MY` shroud zones and corresponding CAST fields.
- `rScripts/rTVAC_EQCTRL.py` writes setpoints into the local CAST exchange; it
  does not communicate with a chamber controller.
- `src/formslab/host/modes/tvac.py` hardcodes the scripts loaded for TVAC mode.
- `src/formslab/state.py` hardcodes the current TVAC status schema.

The new LACO chamber instead has an integrated HVC-3500 PLC responsible for
vacuum sequencing, thermal control, interlocks, warnings, and faults. The old
Rigol-based heater controller must not be treated as an implementation of this
chamber.

## Confirmed design constraints

These constraints should carry into the upcoming minimal design:

1. Use ASCII over TCP through the HVC **CPU IP** for automation.
2. Keep VNC as a human setup/diagnostic path and FTP as a log-retrieval path.
3. Keep PLC interlocks authoritative; do not reproduce low-level vacuum
   sequencing in `formsLabCLI`.
4. Start with a read-only connection and snapshot before enabling writes.
5. Model shroud/platen with logical names, and place HVC zone/sensor numbers in
   per-bench configuration.
6. Record pressure and temperature units in that same configuration because
   the ASCII protocol does not expose unit queries.
7. Separate idempotent setpoint writes from non-idempotent start/continue and
   valve/pump toggle commands.
8. Do not automatically retry non-idempotent writes.
9. After any state-changing command, poll and verify controller state.
10. Decode and retain the complete fault bitmask, including unknown bits.
11. Keep raw valve/pump toggles private or explicitly maintenance-only.
12. Put chamber-specific sequences in `rScripts`, not in the transport driver.

## Minimal capability layers to consider

These are planning boundaries, not yet implementation decisions:

- **Transport/framing:** TCP or RS-232 request/reply with timeouts and strict
  parsing.
- **HVC-3500 protocol:** command encoding, response parsing, fault decoding,
  and safe write semantics.
- **Logical TVAC interface:** named zones/sensors and high-level operations
  used by routines.
- **Per-bench profile:** endpoint, units, mappings, timeouts, and enabled
  capabilities.
- **Routine integration:** status publication, recording, and mission-specific
  timelines.

The first usable milestone should require only transport/framing, a small
HVC-3500 read API, the per-bench profile, and a CLI probe. It should not require
rewriting the existing sequence host or generalizing every current TVAC field.

## Planning inputs still missing

The design can be drafted before these are known, but real communication and
write enablement require:

- Actual CPU and Panel IP addresses.
- TCP socket/listening port.
- Installed HVC software revision.
- Confirmed line terminator and connection behavior.
- Pressure and temperature units.
- Shroud/platen zone mapping.
- Physical temperature sensor mapping.
- Confirmation of the ASCII-enabled recipe configuration.

See `HVC3500_REMOTE_INTERFACE.md` for the commissioning checklist and protocol
details.
