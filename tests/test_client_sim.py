"""Client against the in-process simulator: framing variants, lifecycle, guarded writes."""
import socket
import time

import pytest

from hvc3500 import HVC3500Client, ProtocolError, WriteRefused
from hvc3500.simulator import Simulator


@pytest.fixture(params=[b"\r", b"\r\n", b"\x13"], ids=["CR", "CRLF", "x13"])
def sim(request):
    with Simulator(terminator=request.param) as s:
        yield s


def client(sim, **kw):
    return HVC3500Client(sim.host, sim.port, timeout=2.0, inter_command_delay=0.0,
                         toggle_settle_s=1.3, **kw)


def test_discriminating_probe(sim):
    with client(sim) as c:
        assert c.mode() == "AUTO"
        assert c.test_status() == "IDLE,Stand By,Ready"
        assert c.thermal_control_active() is False
        assert c.pressure() == pytest.approx(760.0)
        assert c.error_status().ok
        with pytest.raises(ProtocolError):
            c.transact("?QQ")          # ER


def test_snapshot_reads_everything(sim):
    with client(sim) as c:
        snap = c.snapshot(temperatures=[0, 3], zones=[1, 2])
    assert "errors" not in snap
    assert snap["T0"] == pytest.approx(22.0) and snap["T3"] == pytest.approx(22.3)
    # zone idle -> effective setpoint tracks the zone's sensor, not the commanded 20.0
    assert snap["Z1_setpoint"] == pytest.approx(22.0) and snap["OR"] is False
    assert snap["error_status"]["severity"] == "N"


def test_one_shot_lifecycle():
    with Simulator(one_shot=True) as s:
        c = client(s, persistent=False)
        for _ in range(3):
            assert c.mode() == "AUTO"
        assert all(t.reconnected for t in c.transactions)
        # persistent mode against a one-shot server fails on the 2nd command, without retry
        p = client(s, persistent=True)
        p.mode()
        with pytest.raises(OSError):
            p.mode()
        assert len(p.transactions) == 2


def test_timeout_is_not_retried():
    with Simulator(reply_delay_s=0.5) as s:
        c = client(s)
        c.timeout = 0.1
        with pytest.raises(socket.timeout):
            c.mode()
        assert len(c.transactions) == 1 and not c.transactions[0].ok


def test_setpoint_writes_read_back(sim):
    with client(sim) as c:
        assert c.set_zone_setpoint(1, 85.5) == 85.5
        assert c.set_zone_rate(2, 0.4) == 0.4
        assert c.set_zone_range(1, 1.5) == 1.5
        assert c.set_vacuum_setpoint(2.5e-4) == pytest.approx(2.5e-4)
        assert c.set_hold_time(120) == 120
        assert c.select_recipe(3) == 3
        assert c.set_zone_setpoint(7, -150.0) == -150.0      # firmware exposes 7 zones
        with pytest.raises(ValueError):
            c.set_zone_setpoint(8, 10)
        with pytest.raises(ValueError):
            c.select_recipe(21)


def test_zone_setpoint_commanded_vs_effective(sim):
    """As observed on the chamber: !Zn persists (HMI shows it) while ?Zn keeps
    tracking the sensor until the zone is activated."""
    with client(sim) as c:
        assert c.set_zone_setpoint(1, 40.0) == 40.0          # verified by echo
        assert c.zone_setpoint(1) == pytest.approx(22.0)     # still tracking T0
        c.activate_zone(1, confirm=True)
        assert c.zone_setpoint(1) == 40.0                    # now the commanded value
        assert c.thermal_control_active() is True            # ?TC third field
        c.deactivate_zone(1, confirm=True)
        assert c.thermal_control_active() is False


def test_actions_require_confirm(sim):
    with client(sim) as c:
        with pytest.raises(WriteRefused):
            c.action("CS")
        with pytest.raises(WriteRefused):
            c.activate_zone(1)
        with pytest.raises(ValueError):
            c.action("OR", confirm=True)    # toggles are not actions
        assert c.action("CS", confirm=True).raw == "CS"
        assert c.test_status().startswith("RUNNING")
        assert c.activate_zone(1, confirm=True).raw == "ZS1"
        assert c.action("CA", confirm=True).raw == "CA"
        es = c.error_status()
        assert es.severity == "F" and es.active == (0,) and es.names == ["Abort"]
        c.action("CR", confirm=True)
        assert c.error_status().ok


def test_device_toggle_is_read_first_single_send_verify(sim):
    with client(sim) as c:
        with pytest.raises(WriteRefused):
            c.set_device("OP", True)
        n = len(c.transactions)
        assert c.set_device("OP", True, confirm=True) is True
        sent = [t.tx for t in c.transactions[n:]]
        assert sent == ["?OP<CR>", "!OP<CR>", "?OP<CR>"]
        # already on: no toggle sent
        n = len(c.transactions)
        assert c.set_device("OP", True, confirm=True) is True
        assert [t.tx for t in c.transactions[n:]] == ["?OP<CR>"]


def test_interlocked_toggle_reports_no_change(sim):
    with client(sim) as c:
        # gate valve interlock: turbo off -> the toggle is accepted but nothing moves
        with pytest.raises(ProtocolError, match="interlock"):
            c.set_device("OG", True, confirm=True)
        assert [t.tx for t in c.transactions].count("!OG<CR>") == 1   # exactly one toggle


def test_pumpdown_model(sim):
    with client(sim) as c:
        c.set_vacuum_setpoint(1e-3)
        c.set_device("OP", True, confirm=True)
        c.set_device("OR", True, confirm=True)
        time.sleep(1.5)
        assert c.pressure() < 760.0
        assert c.pressure_rate() < 0
