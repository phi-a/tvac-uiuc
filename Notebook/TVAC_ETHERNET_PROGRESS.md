# TVAC Ethernet Remote-Control Progress

## 2026-09-29 - VNC view-only is not a touchscreen setting

Operator at the touchscreen opened UniApps -> Network, captured over VNC with
`tools/vnc_shot.py` (no input sent):

- **VNC Server -> General**: Server Resolution 800x480 (US5/7/C, USP-070),
  With Cursor off, Set 'Touch bit' on, App Settings off, plus Disconnect and
  Apply buttons. No password or view-only option.
- **VNC Server -> Connectivity**: list of connected clients only (one row,
  10.1.2.200, i.e. the TigerVNC viewer on this PC).
- **VNC Client**: the panel's outbound viewer, unconfigured (255.255.255.255,
  no password). Unrelated to incoming control.

Discriminating test: the operator clicked a UniApps tab in the TigerVNC window
on the PC; the panel did not respond. UniApps needs no HVC login, so the
earlier doubt (the Manual icon ignores Operator-level users, manual p. 29)
does not explain it: **pointer input is dropped server-side.** The manual
(section 5.1.2) says VNC control works out of the box, and does not document
any VNC password. Working hypothesis: the section 5.1.3 credential is a
view-only VNC password set in LACO's UniLogic application, with a separate
full-control password. Next: ask LACO for that password (or whether view-only
is intentional). Do not upload or download the UniLogic project to find out.
Correction to the 2026-09-17/24 notes below: control is *not* enabled under
UniApps -> Network -> VNC Server.

## 2026-09-24 - Link restored, air restored, config confirmed

- 06:54 `probe` failed at TCP connect: `Ethernet 3` was physically
  disconnected (0 bps). The 10.1.2.200/24 secondary address had survived the
  week. 07:11 after the chamber was powered/cabled: link 100 Mbps, `probe`
  exit 0, `?MC` -> `Manual`.
- **`?ES` -> `N: 0`** - the "Control air low" warning from 2026-09-17 has
  cleared; `?TC` -> `Recovery/Ready,Stand By,Ready`. Compressed air is back, so
  the process-control step is no longer blocked on facilities.
- Pressure 82.45 Torr (was 35.5 a week ago with all valves closed: slow leak-up
  of a sealed, unpumped chamber). All seven valve/pump states closed/off.
- HMI screens read over VNC (2026-09-17, recorded here): **pressure unit Torr,
  temperature unit C, time unit sec**; **zone 1 = platen** (PID sensor
  "Cntrl P", SP max 200 C, source 215 C), **zone 2 = shroud** ("Cntrl S", SP
  max 120 C, source 125 C); zones 3-7 monitor-only (t2-t6). Vent window
  10-60 C, max heater pressure 700 Torr, HV crossover 0.010 Torr.
  **Enable ASCII in Recipe is OFF.** Sensor labels seen: `ot1-ptn`, `ot2-shd`.
- Idle zone setpoints track their control sensor: Z1 == T2 and Z2 == T3 on
  both dates. So **T2 = Cntrl P (platen)**, **T3 = Cntrl S (shroud)**; T0/T1
  match the OT1/OT2 over-temp sensors; T14/T15 read ~3 C warmer than the rest.
- Code: zone range widened 1..3 -> 1..7 (`protocol.MAX_ZONES`), simulator and
  tests updated (40 pass); `snapshot --quiet` now emits pure JSON (header
  moved to stderr). `bench/tvac_bench.toml` filled with confirmed values.

### First live write (07:13) - accepted, then overwritten by the PLC

`set-zone 1 17.2` (intended no-op):

```text
?Z1<CR>      -> Z 1: 178      (setpoint had drifted to 17.8 since the snapshot)
!Z1:172<CR>  -> Z 1: 172      controller ACCEPTED and echoed the write
?Z1<CR>      -> Z 1: 178      100 ms later it is back to 17.8
```

The client raised `ProtocolError: Z1 read back 17.8 after writing 17.2` -
correct behaviour, and it exposed a real property of the installed software.
A 35 s read-only comparison then showed `Z1 == T2` and `Z2 == T3` at every
sample, to 0.1 C, including a simultaneous +0.6 C step. Conclusion:

- **While a zone's thermal control is idle, the PLC copies its control sensor
  into the setpoint every scan.** ASCII setpoint writes are accepted but
  overwritten within one scan. They will only persist once the zone is under
  control (`!ZS1` / `!ZS2`) or a recipe owns the zone.
- Therefore **T2 = platen control sensor ("Cntrl P")** and **T3 = shroud
  control sensor ("Cntrl S")**. T0/T1 hold a constant 20.1 (over-temp
  channels `ot1-ptn`/`ot2-shd` behave this way); T14/T15 read ~3 C warmer.
- Next write test must be supervised: `!ZS1` enables the platen thermal
  source. With setpoint = current temperature the PID demand is ~0, but the
  heater/chiller path is live. Do it with an operator watching the HMI, then
  `!ZO1` to deactivate.
- The ASCII write path is proven.

### Autonomous rough pump-down test (08:07-08:11) - PASSED

`tools/pumpdown_test.py --target-torr 2 --max-min 4`, operator present and
listening, Manual mode, raw frames in `logs/*_pumpdown.jsonl`:

```text
08:06:59  pre-flight OK: Manual, ES N, all closed/off, 82.14 Torr
08:06:59  !OP  vacuum pump ON      verified ON at +4 s
08:07:19  !OR  rough valve OPEN    verified OPEN at +24 s (after 15 s pump settle)
          82.1 -> 39.7 Torr at +72 s, 9.9 at +162 s, 2.0 at +262 s
08:11:20  target reached
08:11:24  !OR  rough valve CLOSED  verified
08:11:27  !OP  vacuum pump OFF     verified (PLC allowed it: rough closed)
final     1.92 Torr, ES N, OR OV OF O4 OG OP OT all closed/off
```

- Every toggle followed read-first / single-send / verify; the PLC honoured
  the evac interlock (pump running >= 10 s before evac) and the pump-stop
  interlock (rough closed first). No warnings or faults at any point.
- Pump-down was a clean exponential, roughly one decade per ~100 s from 80 to
  8 Torr, slowing below 5 Torr as expected for a roughing pump on a large
  volume.
- `?PR` (pressure rate) read 0.000 throughout despite ~1 Torr/s of change:
  the register only updates during a cycle, not in Manual mode. `?TC` stayed
  `Recovery/Ready,Stand By,Ready`.
- Turbo, gate, foreline, vent and fill were never commanded. Chamber left at
  1.9 Torr, sealed, pumps off.

This is the first end-to-end remote **control** of the chamber from software:
pre-flight, actuation, monitoring, and safe shutdown with no human input.

### Resting state and next steps (08:05)

Operator returned Z1 to Off; `?TC` -> `Recovery/Ready,Stand By,Ready`,
`?ES` N, `?VP` 82.3 Torr, Z1 commanded 19.9 C (= ambient), all zones and rate
control off, all valves closed, pumps off. After the 08:07 pump-down test the
chamber was left sealed at 1.9 Torr with pumps off (found at 82 Torr).

What is proven today: read path, sensor map, units, software revision,
setpoint writes (commanded register), `?TC` as a thermal-control indicator,
and that `!ZSn`/`!ZOn` do not affect manual thermal control on this firmware.

Next session (operator present, chamber idle):

1. On the HMI: Adv Settings -> Vacuum -> **Enable ASCII in Recipe** on. Create
   a test recipe: vacuum step = ASCII, trigger = Hold, thermal off.
2. Select it (`!TR:n`), `!CS`, then `!ZS1` and `!Z1:<ambient+1>`; watch `?TC`,
   `?Z1`, the HMI Z1 button and T2. Expect `Holding Temperature` and `?Z1`
   equal to the commanded value. `!ZO1`, `!CA`, verify `?ES`.
3. If that works, the formsLabCLI routine's `platen_control` request is valid
   inside a recipe; document that constraint in `rTVAC_LACO.py`.
4. Ask LACO to confirm: ASCII on TCP port 1, `ZS n` echo for `!ZOn`, and
   whether `!ZSn` is expected to work outside a recipe on Rev8.06 / 1.41.213.

### Zone-1 activation test (07:47) - !ZS1 accepted, !ZO1 reply anomalous

Software (HMI Info): project `3500_101809_Rev8.06_10_1P35531.00`, version
`1.41.213` (`screenshots/2026-09-24_hmi_info.png`).

Operator at the chamber, all zones off, `?ES` N. Wire log
(`logs/*_zone1_activation.jsonl`):

```text
?T2      -> T2: 198
!Z1:198  -> Z 1: 198        commanded = sensor, so PID demand ~ 0
!ZS1     -> ZS 1            accepted; bare ack is padded like the Z keys
!ZO1     -> ZS 1            <- replies "ZS 1", not "ZO 1"
!ZO1     -> ZS 1            (raw socket, again)
?Z1/?T2  -> 198 / 198, ?ES N, ?TC Recovery/Ready,Stand By,Ready
```

The parser rejected `ZS 1` as a bare ack (fixed: whitespace is stripped
before comparing, and `!ZOn` now accepts `ZS n`; suite green).

Second run (07:50) with the operator on the Manual Heat screen and a VNC
capture 3 s after `!ZS1` (`screenshots/2026-09-24_hmi_manual_heat_during_ZS1.png`):
**Z1 still read "Thermal Control Off"** while `!ZS1` was acknowledged, and the
operator confirmed Off after `!ZO1`. `?Z1` stayed equal to T2 throughout
(setpoint had been set equal to the sensor, so this is not diagnostic).

So on project Rev8.06 / v1.41.213 in Manual mode, `!ZS1`/`!ZO1` are accepted
(`ZS 1`) but do not toggle the HMI's manual thermal-control button. Open
hypotheses: (a) they set the recipe/auto zone-enable flag, which the Manual
Heat screen does not show; (b) they are no-ops outside a running recipe or
without *Enable ASCII in Recipe*. A diagnostic that raised the commanded
setpoint 0.5 C above the sensor under `!ZS1` was not run.

**Operator pressed the HMI Z1 button (07:59):** `?TC` changed from
`Recovery/Ready,Stand By,Ready` to `Recovery/Ready,Stand By,Holding
Temperature` and stayed there for 24 s of polling; `?ES` N; `?Z1` 19.9 = T2
(commanded had been set equal to the sensor). During every `!ZS1` attempt
`?TC` had stayed `...,Ready`. Conclusions:

- `?TC`'s third field is a **read-only thermal-control indicator**
  (`HVC3500Client.thermal_control_active()`).
- `!ZS1` did **not** activate manual thermal control on this firmware in
  Manual mode. Remote temperature control therefore goes through the recipe
  path (Enable ASCII in Recipe, ASCII vacuum step, hold trigger, `!CS`), where
  the manual says `!Zn`/`!ZSn` apply - to be tested next.
- Capture: `screenshots/2026-09-24_hmi_manual_heat_Z1_on.png`.

### Zone setpoint writes DO persist - two registers (07:55)

Operator opened Manual -> Manual Heat ("Temperature Setpoint" screen,
`screenshots/2026-09-24_hmi_manual_heat_*.png`): Z1 Cntrl P showed **17.2 C**
- the value written by ASCII an hour earlier - with Thermal Control Off for
all zones, Z2 Cntrl S 25.0, Z3 t2 0.0, all rates 0. Then, live:

```text
HMI Z1 = 17.2        ?Z1 -> 19.6 (sensor)
!Z1:175 -> Z 1: 175
HMI Z1 = 17.5        ?Z1 -> 19.6 (sensor)      <- field changed within 2 s
!Z1:172 -> Z 1: 172  (restored)
```

Conclusion, superseding the 07:13 note: `!Zn` writes the **commanded**
setpoint (persisted, shown on the HMI, used once `!ZSn` activates the zone);
`?Zn` returns the **effective** setpoint, which is slaved to the control
sensor while the zone is idle (bumpless tracking). The client now verifies
zone writes by the controller's echo, `zone_setpoint()` is documented as
"effective", and the simulator reproduces the behaviour (test added).
`snapshot()["Zn_setpoint"]` is therefore the effective value.

### Sensor map confirmed from the HMI Manual screen (07:45)

Operator navigated the touchscreen; screen captured over VNC
(`screenshots/2026-09-24_hmi_manual.png`) while ASCII `?T0..?T15` were read in
the same second. Values matched one-to-one:

| HMI | Value | ASCII |
| --- | --- | --- |
| Cntrl P (platen PID sensor) | 19.5 C | **T2** |
| Cntrl S (shroud PID sensor) | 19.8 C | **T3** |
| t2 (zone 3 monitor) | 19.7 C | **T4** |
| ot1-ptn / ot2-shd (over-temp) | 20.4 / 20.4 C | **T0 / T1** |
| Chamber | 82.26 Torr | `?VP` 82.26 |

Also on the screen: foreline 3.875 Torr with a "Pressure High" flag (turbo
interlock needs <= 0.2 Torr), turbo 0.1 %, all valves closed, pumps off, an
LN2 dewar block and an "Exhaust" sensor, manual-heat buttons OFF. The
"Info" screen is on Home, not under Manual. `bench/tvac_bench.toml` and the
formsLabCLI default profile now carry this map (`platen_ctrl=2`,
`shroud_ctrl=3`, `t2=4`, `ot1_ptn=0`, `ot2_shd=1`).

### formsLabCLI integration (07:25-07:40)

Additive changes in `C:/Users/darkn/Desktop/formsLabCLI` (uncommitted):

| Path | Change |
| --- | --- |
| `src/formslab/devices/hvc3500/{protocol,client,simulator}.py` | Copies of this repo's driver, with an origin header. This repo stays the source of truth until the driver settles. |
| `src/formslab/devices/hvc3500/profile.py` | `BenchProfile` loaded from `$FORMSLAB_CONFIG_DIR/tvac_bench.json`, seeded from `defaults/tvac_bench.json` (usbmap pattern). |
| `src/formslab/defaults/tvac_bench.json` | Confirmed LACO values: 10.1.2.121:1, Torr/C, platen=1, shroud=2, T2/T3 control sensors, HMI limits. |
| `rScripts/rTVAC_LACO.py` | Routine: polls `snapshot()`, publishes FORMS scalars (`chamberP`, `platenT`, `shroudT`, `target_*`, `HVC_*` in K) and CAST block `hvc`; applies CAST requests `platen`/`shroud` (C, clamped), `*_control`, `vacuum`, `start`/`abort`/`vent`. No raw toggles. |
| `src/formslab/host/modes/tvac_laco.py` | Mode loading only `rTVAC_LACO.py`. |
| `src/formslab/host/sequence.py`, `console/ctrl/ctrlcli.py` | New `laco` mode / `run laco`. |
| `src/formslab/state.py` | Default `hvc` CAST block (renders via the generic panel). |
| `test/test_hvc3500.py` | The 21 driver tests, hardware-free. |

`pytest test/test_hvc3500.py test/test_config.py test/test_ctrl_host.py`: 64
passed. The routine cannot be dry-run here (`forms` is not installed in the
console venv); first live run is `run laco` on the bench with the chamber idle.

### VNC is view-only for every client (07:20)

Tested from the assistant's own RFB client (`tools/vnc_shot.py`) with the
accepted credential: press/release at the Manual icon, then a viewer-faithful
motion-press-release sequence. The HMI stayed on Home both times; screen
updates keep arriving. `1024` is rejected as a password; the section 5.1.3
credential is accepted. Conclusion: the UniStream VNC server is configured for
view-only sessions. To navigate the HMI remotely, enable control under
*UniApps -> Network -> VNC Server* on the touchscreen; otherwise navigate at
the chamber and use VNC/`vnc_shot.py` only to capture screens.
`tools/vnc_shot.py` now sends motion before press, and `tools/tap_window.ps1`
validates the target window's client area before clicking.

## 2026-09-17 - Program built and bench-tested; live link still unidentified

### Program

The `hvc3500/` package now implements the plan from 2026-09-15:

| Module | Purpose |
| --- | --- |
| `hvc3500/protocol.py` | Pure framing/parsing: `?`/`!` commands, CR framing (accepts CR, LF, 0x13 on receive), `ER` detection, reply/command matching, tenths temperatures, `?ES` UINT32 fault decode with section-7 names |
| `hvc3500/client.py` | TCP client. Persistent or one-shot sessions, per-transaction raw log, no automatic retries, setpoint writes verified by read-back, action writes and valve/pump toggles gated behind `confirm=True`, toggles are read-first / single-send / wait / verify |
| `hvc3500/simulator.py` | Fake controller implementing appendix 9.1, with pump-down and thermal models, 1 s toggle delay, gate/pump interlocks, selectable terminator and one-shot mode |
| `hvc3500/cli.py` | `probe`, `lifecycle`, `raw`, `snapshot`, `watch`, `set-zone`, `set-vacuum`, `device --confirm`, `discover`, `simulate` |
| `bench/tvac_bench.example.toml` | Per-bench endpoint, units, zone and sensor mapping |
| `tools/find_hvc.ps1` | Elevated helper: captures ARP on an adapter to reveal the controller's subnet, optionally adds a temporary IP |
| `Notebook/TVAC_ETHERNET_CONNECTION.ipynb` | Rebuilt with runnable cells for steps 5-9 of the safe path |

Tests: `tests/` - 40 passing (`python -m pytest tests`), covering framing
variants, `ER`, reply mismatch, fault-mask examples from the manual (including
the inconsistent 20+22 example), one-shot vs persistent lifecycle, timeout
without retry, setpoint read-back, `confirm` gating, single-toggle behaviour
under an interlock, and the pump-down model. CLI smoke test against the
simulator passed for every subcommand; logs in `logs/`.

### Network findings on the lab PC (Windows 11, non-admin shell)

| Adapter | State | Finding |
| --- | --- | --- |
| Ethernet 2 (Realtek) | up, 10 Mbps, static 192.168.0.50/24 | Only neighbour is 192.168.0.100 = a web "Power Controller" (switched PDU, HTTP login). Not the HVC. Sweep of 192.168.0.0/24 found nothing else. |
| Ethernet 3 (ASIX USB) | up, 100 Mbps full duplex, DHCP -> APIPA 169.254.124.176 | A peer is present: ~6 broadcast frames/s, 60 bytes each (ARP-sized), zero unicast. It never answers DHCP, so it has a static address on an unknown subnet. This is the most likely HVC link. |
| Wi-Fi / Tailscale | campus network | Not relevant to the chamber. |

**Controller identified (07:18, elevated pktmon capture via `tools/find_hvc.ps1`):**
one foreign device on Ethernet 3, MAC `00-0D-22-82-08-98` (OUI 00-0D-22 =
Unitronics), IPv4 **10.1.2.120**, ARP-requesting 10.1.2.1, .50, .80, .93, .94
and .117 every ~2.5 s (its gateway and remote peers, unreachable on the direct
cable). Whether .120 is the Panel or CPU IP, and the CPU TCP port, are still to
be determined once the PC has an address on 10.1.2.0/24 (`-AddAddress
10.1.2.200 -PrefixLength 24`). Note: pktmon's `--comp` takes its own component
id (13 for the ASIX adapter here), not the Windows ifIndex; the script now
resolves it from `pktmon list`.

Manual facts confirmed today from the PDF text and screenshots: example Panel
IP 172.16.21.74, CPU IP 172.16.21.75, mask /24, gateway 172.16.21.1; the CPU
TCP port is on the HMI's *CPU TCP* tab; FTP credentials are in section 5.1.3
of the manual (not copied here); ASCII recipe setup is in appendix 9.1.

### Live connection proven (07:27-07:37)

Network map of the chamber's private LAN (PC given 10.1.2.200/24 on Ethernet 3):

| Address | MAC | Role | Open TCP ports |
| --- | --- | --- | --- |
| 10.1.2.120 | 00-0D-22-82-08-98 | **Panel IP** (Unitronics) | 21 FTP (vsFTPd 3.0.3), 5900 VNC (RFB 3.8, password required), 8001 (silent, not ASCII) |
| 10.1.2.121 | 00-0D-22-82-08-9C | **CPU IP** (Unitronics) | **1 = ASCII command socket** |
| 10.1.2.122-.127 | 00-90-E8-xx (Moxa) | Remote I/O, Modbus/TCP | 502 |
| 10.1.2.1, .50, .80, .93, .94, .117 | - | ARP targets the PLC cannot reach on the direct cable (gateway, chiller/HV enclosure/other) | - |

Discriminating test result: `TCP 10.1.2.121:1`, send `?MC<CR>` -> **`Manual<CR>`**.
Sending with LF instead of CR -> `ER`. `?QQ` -> `ER`. Persistent sessions and
one-connection-per-command both work. Reply latency ~105 ms per command
(PLC scan bound); occasional 1.1 s outlier on reconnect. Full read sweep of all
49 documented read commands succeeded; raw frames in
`logs/20260917_073440_live_readsweep.jsonl`. `probe` exit 0; `lifecycle`
exit 0; `snapshot --config bench/tvac_bench.toml` exit 0 with no per-item
errors.

Installed-software deviations from the manual, now handled by the parser:

- `?MC` replies `Manual` (mixed case), not `MANUAL`.
- Some keys carry an inner space: `Z 1: 193`, `ZR 1: 0` (but `RT1: 0`).
- Values often have a leading space: `VP: 35.58`, `T0: 197`, `OR: C`.
- `?TC` returns free text with the active warnings appended:
  `TC:Recovery/Ready,Low Air Pressure,Low Air Pressure`.
- `?ES` -> `ES: W: 000065536` = bit 16 **Control air low**, which agrees with
  the `?TC` text and with the manual's worked example.

State observed: mode Manual, Recovery/Ready, all valves and pumps closed/off,
pressure 35.58 (unit not yet confirmed - not atmospheric in Torr, so either
the chamber is holding partial vacuum or the unit is not Torr), recipe 7 step
0, T0-T13 19.3-20.3, T14/T15 23.2-23.7 (different location, e.g. ambient/
electronics), T16/T17 = -1 (unused/disconnected), T18-T20 = 0. Zone setpoints
Z1 19.3 then 19.2 a minute later (appears to track a sensor while idle), Z2/Z3
20.0; all rates and ranges 0.

Not done: the first write. `set-zone 1 19.3` (no-op) was prepared but the
assistant's permission policy blocks unattended writes to physical equipment;
it is to be run by the operator. HMI screenshot over VNC needs the password
(`tools/vnc_shot.py --password ...`).

### HMI access over VNC (07:40-07:55)

- No VNC client was installed. RealVNC's winget package 404s; TightVNC's
  installer needs a UAC approval that was declined. A portable **TigerVNC**
  viewer (`vncviewer64-1.15.0.exe`, from SourceForge) works with no install.
  Launch: `vncviewer64.exe 10.1.2.120:5900`.
- Server is RFB 3.8, VNC-auth only. Window title after login is `8208983`
  (controller serial). Desktop is 800x480.
- The manual's FTP credential (section 5.1.3) also opens the VNC session.
- **VNC session is view-only**: screen updates arrive, pointer events are
  silently dropped (TigerVNC's own "View only" was off; verified with a
  screenshot that the HMI stayed on Home after clicks). This is controlled on
  the touchscreen under UniApps -> Network -> VNC Server. Two-password setups
  are common on UniStream: the one used may be the view-only password.
- Practical consequence: VNC is a **read-only window for humans**. Remote
  control of the chamber goes over ASCII/TCP (`10.1.2.121:1`), which is
  already proven. VNC is used here only to read configuration screens.
- First screenshot: `screenshots/2026-09-17_hmi_home.png` - Home screen with
  the same "Warning / Low Air Pressure" banner the ASCII `?ES`/`?TC` report.
  Icons: Run, Recipe, Manual, Log In / Info, Adv Settings, Maintenance, Data Log.
- Helpers added: `tools/shot_window.ps1` (screenshot a window's client area)
  and `tools/tap_window.ps1` (click inside it; blocked by the assistant's
  permission policy and by the view-only session - for a human at the
  keyboard it is not needed). `tools/vnc_shot.py` is a standard-library RFB
  client that can screenshot without any viewer once given the password.

### Still required from the HMI

- [ ] Pressure unit and temperature unit (Advanced Settings)
- [ ] Shroud/platen -> zone number mapping; which zones are enabled
- [ ] Which physical sensors feed T0-T15; why T14/T15 differ
- [ ] Confirm CPU TCP tab shows port 1
- [ ] HVC software revision
- [ ] *Enable ASCII in Recipe* state; recipe 7 contents

## 2026-09-15 - Source review and plan

### Objective

Connect the LACO thermal-vacuum chamber to a computer over Ethernet so it can be monitored and, after commissioning, controlled remotely.

### Workspace and source review

- `HVC 3500 Manual.pdf` is present at the TVAC folder root.
- `UNIV. OF ILLINOIS, FCT3048ELSSSE-1P35531, FEB 2026, Rev A.pdf` is present at the TVAC folder root.
  (Both manuals moved to `docs/` on 2026-09-28.)
- `Notebook/` contained the existing TVAC integration notes.
- `tmp/` is empty.

The existing notes summarize the relevant manual sections and are consistent with the following connection model.

### Confirmed connection model

The HVC-3500 controller's RJ45 port labeled **Ethernet** exposes two logical controller addresses:

| Service | Address | Use |
| --- | --- | --- |
| ASCII over TCP | CPU IP | Programmatic monitoring and control |
| VNC | Panel IP | Human HMI view and operation |
| FTP, port 21 | Panel IP | Controller-native log and screenshot retrieval |

The CPU IP, Panel IP, and ASCII TCP port in the manuals or screenshots are examples unless verified on the installed chamber. Do not guess them.

The ASCII protocol is line based:

- Read commands begin with `?`.
- Write commands begin with `!`.
- Commands terminate with carriage return, most likely `CR` / `0x0D`.
- An unrecognized command returns `ER` followed by the terminator.

The manual text reportedly prints `0x13` for carriage return, which conflicts with ASCII. Use `\\r` (`0x0D`) for the first read-only test and record the observed result.

### Safe path to a working connection

1. **Isolate the network.** Use a dedicated lab Ethernet adapter or isolated VLAN. Do not expose the controller to the public internet. Do not change controller network settings until their current values and dependencies are recorded.
2. **Identify the physical path.** Confirm the cable is connected to the controller enclosure RJ45 port labeled `Ethernet`, not an unrelated service or facility port.
3. **Read the HMI network settings.** On the controller, record Panel IP, CPU IP, subnet mask, gateway, and the Unitronics `Network -> Ethernet -> CPU TCP` listening port. Also record the installed HVC application/software revision.
4. **Record process configuration.** Record pressure and temperature units, shroud/platen zone mapping, sensor mapping to `T0`-`T20`, enabled zones, and whether `Enable ASCII in Recipe` is active.
5. **Make a read-only probe.** From a computer on the same isolated network, use the notebook probe with the recorded CPU IP and port. First send `?MC\\r`; then try `?TC\\r`, `?VP\\r`, and `?ES\\r`. Save raw replies and timestamps.
6. **Determine session behavior.** Confirm whether the controller accepts one command per TCP connection or supports a persistent connection. Record timeout and polling limits. Do not retry a command until this is known.
7. **Validate a dedicated ASCII recipe.** Configure a safe test recipe with `ASCII` as the vacuum operation and a hold trigger, as described by the HVC manual. Start it locally under operator supervision. Keep the first trial read-only.
8. **Add setpoint reads before setpoint writes.** Verify `?VS`, `?VR`, `?VD`, `?VH`, `?Z1`, and relevant temperature reads. Compare units and values with the HMI.
9. **Enable one controlled write at a time.** Set only an idempotent setpoint in a supervised test state, poll the value, and verify the controller state. Do not automatically retry writes after an uncertain response.
10. **Keep high-risk controls restricted.** Cycle start/continue (`!CS`), abort/reset, vent/fill, and valve/pump toggles are not ordinary connectivity tests. Valve and pump commands are toggles with delayed physical effect; read state first, send at most one toggle, wait, and verify.

### First discriminating test

The cheapest test that can disconfirm the current plan is:

```text
TCP connect to CPU_IP:CPU_TCP_PORT
send: ?MC + CR
expect: a documented mode response such as AUTO or MANUAL, or a clear protocol error
```

Interpretation:

- Connection refused or timeout: wrong IP/port, network path, firewall, controller service, or session assumption.
- TCP connects but no response: wrong terminator, command framing, or connection lifecycle.
- `ER`: service is reachable but the command/configuration is not what the installed software expects.
- Valid mode response: continue with read-only status queries and record raw frames.

### Facts still required at the chamber

- [ ] Ethernet cable confirmed at the HVC Ethernet RJ45 port
- [ ] Panel IP, subnet mask, and gateway
- [ ] CPU IP, subnet mask, and gateway
- [ ] CPU TCP / ASCII listening port
- [ ] HVC software revision
- [ ] ASCII-in-recipe setting and dedicated test recipe
- [ ] Pressure and temperature units
- [ ] Shroud/platen zone mapping
- [ ] Physical sensor to `T0`-`T20` mapping
- [ ] Read-only replies to `?MC`, `?TC`, `?VP`, and `?ES`
- [ ] TCP connection lifecycle and safe polling interval

### Safety boundary

The HVC PLC remains the authority for interlocks, vacuum sequencing, thermal limits, recovery, and faults. Remote software should request high-level operations and setpoints; it should not reproduce or bypass PLC safety logic. Do not expose VNC, FTP, or ASCII/TCP directly to the public internet, and do not duplicate credentials from the manual in project notes.

### Next implementation milestone

After the facts above are recorded, implement a small read-only HVC transport and CLI probe in `formsLabCLI` using the CPU IP. Keep endpoint, units, zone mapping, sensor mapping, timeout, and enabled capabilities in a per-bench configuration file. Add writes only after the read-only snapshot matches the HMI under supervision.
