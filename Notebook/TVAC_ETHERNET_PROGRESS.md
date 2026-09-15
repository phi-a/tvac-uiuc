# TVAC Ethernet Remote-Control Progress

Date: 2026-09-15

## Objective

Connect the LACO thermal-vacuum chamber to a computer over Ethernet so it can be monitored and, after commissioning, controlled remotely.

## Workspace and source review

- `HVC 3500 Manual.pdf` is present at the TVAC folder root.
- `UNIV. OF ILLINOIS, FCT3048ELSSSE-1P35531, FEB 2026, Rev A.pdf` is present at the TVAC folder root.
- `Notebook/` contained the existing TVAC integration notes.
- `tmp/` is empty.

The existing notes summarize the relevant manual sections and are consistent with the following connection model.

## Confirmed connection model

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

## Safe path to a working connection

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

## First discriminating test

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

## Facts still required at the chamber

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

## Safety boundary

The HVC PLC remains the authority for interlocks, vacuum sequencing, thermal limits, recovery, and faults. Remote software should request high-level operations and setpoints; it should not reproduce or bypass PLC safety logic. Do not expose VNC, FTP, or ASCII/TCP directly to the public internet, and do not duplicate credentials from the manual in project notes.

## Next implementation milestone

After the facts above are recorded, implement a small read-only HVC transport and CLI probe in `formsLabCLI` using the CPU IP. Keep endpoint, units, zone mapping, sensor mapping, timeout, and enabled capabilities in a per-bench configuration file. Add writes only after the read-only snapshot matches the HMI under supervision.
