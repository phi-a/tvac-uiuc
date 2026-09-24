# TVAC Remote Control - Session Summary, 2026-09-24

Written for: whoever picks this project up next (lab members, or a future
session). It condenses the day's work; the dated, frame-level detail is in
[TVAC_ETHERNET_PROGRESS.md](TVAC_ETHERNET_PROGRESS.md).

## Where things stood at the start

- The `hvc3500` driver, CLI, simulator and 40 tests existed from 2026-09-17,
  and the read path to the controller had been proven once.
- Open: link was down, units/zone/sensor mapping unconfirmed, no write had
  succeeded, and the formsLabCLI integration had not been started.

## What was done today

### 1. Link and facilities
- `Ethernet 3` was physically disconnected; after cabling and power-up,
  `probe` passed (`?MC` -> `Manual`). The 10.1.2.200/24 address had survived.
- The "Control air low" warning (bit 16) from last week had cleared:
  `?ES` -> `N`, `?TC` -> `Recovery/Ready,Stand By,Ready`.

### 2. Configuration confirmed from the HMI
Operator drove the touchscreen; screens captured over VNC (view-only session)
into `screenshots/`.

| Item | Value |
| --- | --- |
| Pressure / temperature / time units | Torr / C / s |
| Zone 1 | Platen (PID sensor "Cntrl P", SP max 200 C) |
| Zone 2 | Shroud (PID sensor "Cntrl S", SP max 120 C) |
| Zones 3-7 | Monitor-only (t2-t6) |
| Software | project `3500_101809_Rev8.06_10_1P35531.00`, version 1.41.213 |
| Enable ASCII in Recipe | off |
| Sensor map | T2 platen ctrl, T3 shroud ctrl, T4 t2, T0/T1 over-temp; T14/T15 run ~3 C warm; T16-T20 unused |

The sensor map was proven by matching the Manual screen values against live
`?T0..?T15` reads taken in the same second.

### 3. Setpoint writes: two registers (corrects the 09-17 conclusion)
- `!Zn:value` writes the **commanded** setpoint. It persists and appears on
  the HMI Manual Heat field within 2 s (`!Z1:175` observed live).
- `?Zn` returns the **effective** setpoint, which is slaved to the control
  sensor while the zone is idle.
- The client now verifies zone writes by the controller's echo, documents
  `zone_setpoint()` as "effective", and the simulator reproduces this.

### 4. Thermal-control activation
- `!ZS1` / `!ZO1` are acknowledged (both reply `ZS 1`) but **do not** switch
  on manual thermal control on this firmware in Manual mode. The HMI button
  does.
- `?TC`'s third field reads `Holding Temperature` while any zone is active -
  the only read-only indicator found (`client.thermal_control_active()`).
- Remote temperature control therefore has to go through the recipe path
  (Enable ASCII in Recipe -> ASCII vacuum step with Hold -> `!CS`), as the
  manual describes. Not yet tested.

### 5. formsLabCLI integration (commit `707a303` in that repo)
- `src/formslab/devices/hvc3500/`: driver copy + `profile.py` seeded from
  `defaults/tvac_bench.json`.
- `rScripts/rTVAC_LACO.py`: polls the chamber, publishes FORMS scalars and
  CAST block `hvc` (including `thermal_control`), accepts `platen`/`shroud`
  setpoints, `*_control`, `vacuum`, `start`/`abort`/`vent`. No raw toggles.
- `run laco` host mode; existing Rigol `tvac` mode untouched.
- `test/test_hvc3500.py`: 21 hardware-free tests. Suite green.
- Not yet run live: the console venv does not have the `forms` extra.

### 6. First autonomous control run - rough pump-down (PASSED)
`tools/pumpdown_test.py --target-torr 2 --max-min 4`, operator listening:

```text
08:06:59  pre-flight OK: Manual, ES N, all closed/off, 82.14 Torr
08:06:59  !OP  pump ON            verified
08:07:19  !OR  rough valve OPEN   verified (after 15 s pump settle)
          82.1 -> 39.7 Torr (+72 s) -> 9.9 (+162 s) -> 1.95 (+262 s)
08:11:20  target reached
08:11:24  !OR  rough valve CLOSED verified
08:11:27  !OP  pump OFF           verified
final     1.92 Torr, ES N, all seven valves/pumps closed/off
```

Every toggle was read-first, single-send, verified; PLC interlocks were
honoured; turbo, gate, foreline, vent and fill were never commanded. Chamber
left sealed at 1.9 Torr, pumps off. Note: `?PR` (pressure rate) reads 0 in
Manual mode; compute rate from `?VP`.

## Repository state
- tvac: commits `397e22a` (driver, CLI, tests, notes), `5bf3bc4` (pump-down
  test and result), `3dfc052` (README/notes). Tree clean.
- formsLabCLI: `707a303` (LACO support only; the operator's other uncommitted
  work was left in place).

## Next
1. Recipe-path thermal test with an operator present: enable ASCII in
   Recipe, ASCII-step recipe with Hold trigger, `!TR:n`, `!CS`, then
   `!ZS1` + `!Z1:<ambient+1>`; expect `?TC` `Holding Temperature` and `?Z1`
   equal to the commanded value; `!ZO1`, `!CA`, check `?ES`.
2. Install the `forms` extra in the console venv and run `run laco` on the
   bench; confirm the `hvc` CAST block updates.
3. Ask LACO: ASCII on TCP port 1, the `ZS n` echo for `!ZOn`, and whether
   `!ZSn` is expected to work outside a recipe on Rev8.06 / 1.41.213.
4. Optional: enable VNC control on the touchscreen (UniApps -> Network ->
   VNC Server) so the HMI can be driven remotely as well as viewed.
