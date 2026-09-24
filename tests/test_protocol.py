import pytest

from hvc3500 import protocol as P


def test_encode_appends_cr():
    assert P.encode("?MC") == b"?MC\r"
    assert P.encode("!Z1:855") == b"!Z1:855\r"
    assert P.encode("!VS:1.5e-05") == b"!VS:1.5e-05\r"


@pytest.mark.parametrize("bad", ["MC", "?", "?mc", "?MC\r", "!Z1:85.5;rm", "?TOOLONG"])
def test_encode_rejects_bad_commands(bad):
    with pytest.raises(ValueError):
        P.encode(bad)


def test_decode_strips_any_terminator():
    assert P.decode_reply(b"AUTO\r") == "AUTO"
    assert P.decode_reply(b"AUTO\r\n") == "AUTO"
    assert P.decode_reply(b"AUTO\x13") == "AUTO"


def test_parse_mode():
    assert P.parse_reply("?MC", "AUTO").raw == "AUTO"
    with pytest.raises(P.ProtocolError):
        P.parse_reply("?MC", "RUNNING")


def test_parse_keyed_reply_and_mismatch():
    r = P.parse_reply("?VP", "VP:7.5000000E-03")
    assert (r.key, r.value) == ("VP", "7.5000000E-03")
    assert P.parse_number(r.value) == 7.5e-3
    with pytest.raises(P.ProtocolError):
        P.parse_reply("?VP", "VS:1.0")


def test_parse_bare_ack():
    assert P.parse_reply("!CS", "CS").raw == "CS"
    with pytest.raises(P.ProtocolError):
        P.parse_reply("!CS", "CA")


def test_er_raises():
    with pytest.raises(P.ProtocolError):
        P.parse_reply("?QQ", "ER")


def test_temperature_tenths():
    assert P.parse_temperature("458") == 45.8
    assert P.parse_temperature("-105") == -10.5
    assert P.format_temperature(85.5) == "855"
    assert P.format_temperature(-10.55) == "-105" or P.format_temperature(-10.55) == "-106"
    with pytest.raises(P.ProtocolError):
        P.parse_temperature("45.8")


def test_error_status_examples_from_manual():
    es = P.parse_error_status("W: 0000065536")
    assert es.severity == "W" and es.active == (16,) and es.names == ["Control air low"]
    # manual example 2 says faults 20 and 22 but prints 4194304, which is bit 22 alone
    es = P.parse_error_status("F: 00004194304")
    assert es.active == (22,)
    es = P.parse_error_status("F: 5242880")
    assert es.active == (20, 22)
    assert P.parse_error_status("N: 0000000000").ok
    unknown = P.parse_error_status("W: 1073741824")
    assert unknown.active == (30,) and unknown.names == ["unknown bit 30"]


def test_error_status_rejects_garbage():
    for bad in ("X: 1", "W:abc", "W", "W: 4294967296"):
        with pytest.raises(P.ProtocolError):
            P.parse_error_status(bad)


def test_device_state():
    assert P.parse_device_state("O") is True
    assert P.parse_device_state(" C") is False
    with pytest.raises(P.ProtocolError):
        P.parse_device_state("ON")


def test_write_classes_are_disjoint():
    assert not set(P.SETPOINT_WRITES) & set(P.ACTION_WRITES)
    assert not set(P.TOGGLE_WRITES) & set(P.ACTION_WRITES)
