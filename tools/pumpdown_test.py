"""Supervised rough pump-down test in Manual mode.

    python tools/pumpdown_test.py [--config bench/tvac_bench.toml] [--target-torr 2] [--max-min 4]

Sequence (each step read-first, single toggle, verified via ?Ox):
  1. pre-flight: mode Manual, ?ES N, all valves closed, pumps off
  2. !OP  vacuum (roughing) pump ON, wait 15 s  (PLC evac interlock: pump on >= 10 s)
  3. !OR  rough valve OPEN; log ?VP ?PR ?ES every 5 s
  4. stop when ?VP < target, time limit reached, or ?ES leaves N
  5. !OR  rough valve CLOSED, then !OP pump OFF (PLC forbids stopping with rough open)

Turbo (!OT), gate (!OG), foreline (!O4), vent (!OV) and fill (!OF) are never
commanded. On any exception the finally block closes the rough valve and stops
the pump. Raw frames go to logs/<timestamp>_pumpdown.jsonl.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import tomllib

# The driver's one copy is formsLabCLI's (pip install -e <formsLabCLI checkout>).
from formslab.devices.hvc3500 import HVC3500Client, ProtocolError


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="bench/tvac_bench.toml")
    ap.add_argument("--target-torr", type=float, default=2.0)
    ap.add_argument("--max-min", type=float, default=4.0)
    ap.add_argument("--settle", type=float, default=15.0, help="seconds pump runs before evac")
    a = ap.parse_args()
    with open(a.config, "rb") as f:
        conn = tomllib.load(f)["connection"]

    os.makedirs("logs", exist_ok=True)
    log = open(f"logs/{time.strftime('%Y%m%d_%H%M%S')}_pumpdown.jsonl", "a")
    c = HVC3500Client(conn["host"], int(conn["port"]), timeout=float(conn.get("timeout_s", 3.0)),
                      toggle_settle_s=3.0, on_transaction=lambda t: log.write(t.as_json() + "\n"))
    c.connect()
    t0 = time.time()

    def stamp() -> str:
        return f"{time.strftime('%H:%M:%S')} +{time.time() - t0:5.0f}s"

    def status(tag: str) -> tuple[float, str]:
        vp, pr, es = c.pressure(), c.pressure_rate(), c.error_status()
        print(f"{stamp()}  {tag:<22} VP={vp:9.3f} Torr  PR={pr:+9.3f}  ES={es.severity} {es.names or ''}")
        return vp, es.severity

    # ---- 1. pre-flight --------------------------------------------------
    mode = c.mode()
    devs = {k: c.device_state(k) for k in ("OR", "OV", "OF", "O4", "OG", "OP", "OT")}
    vp, sev = status("pre-flight")
    if mode != "MANUAL" or sev != "N" or any(devs.values()):
        print(f"ABORT pre-flight: mode={mode} ES={sev} devices={devs}")
        c.close()
        return 2
    print(f"{stamp()}  pre-flight OK: Manual, no faults, all closed/off, {vp:.2f} Torr")

    rough_open = False
    pump_on = False
    try:
        # ---- 2. pump on --------------------------------------------------
        print(f"{stamp()}  !OP -> vacuum pump ON")
        pump_on = c.set_device("OP", True, confirm=True)
        print(f"{stamp()}  pump verified {'ON' if pump_on else 'OFF?!'}; settling {a.settle:.0f} s")
        for _ in range(int(a.settle // 5)):
            time.sleep(5)
            status("pump settling")
        time.sleep(a.settle % 5)

        # ---- 3. rough valve open -----------------------------------------
        print(f"{stamp()}  !OR -> rough valve OPEN")
        rough_open = c.set_device("OR", True, confirm=True)
        print(f"{stamp()}  rough valve verified {'OPEN' if rough_open else 'CLOSED?!'}")

        # ---- 4. monitor --------------------------------------------------
        deadline = time.time() + a.max_min * 60
        while True:
            vp, sev = status("pumping")
            if sev != "N":
                print(f"{stamp()}  fault/warning seen -> stopping")
                break
            if vp < a.target_torr:
                print(f"{stamp()}  reached target {a.target_torr} Torr")
                break
            if time.time() > deadline:
                print(f"{stamp()}  time limit {a.max_min} min reached")
                break
            time.sleep(5)
    except (OSError, ProtocolError) as exc:
        print(f"{stamp()}  ERROR during test: {exc}")
    finally:
        # ---- 5. close rough valve, then pump off --------------------------
        for code, want, label in (("OR", False, "rough valve CLOSED"), ("OP", False, "vacuum pump OFF")):
            try:
                state = c.set_device(code, want, confirm=True)
                print(f"{stamp()}  !{code} -> {label}: verified {'open/on' if state else 'closed/off'}")
            except (OSError, ProtocolError) as exc:
                print(f"{stamp()}  !! {label} NOT verified: {exc}  <- check the HMI")
        try:
            status("final")
            devs = {k: c.device_state(k) for k in ("OR", "OV", "OF", "O4", "OG", "OP", "OT")}
            print(f"{stamp()}  final devices: { {k: ('OPEN' if v else 'closed') for k, v in devs.items()} }")
        finally:
            c.close()
            log.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
