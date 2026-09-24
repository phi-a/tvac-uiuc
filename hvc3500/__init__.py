"""LACO VC/HVC-3500 ASCII-over-TCP client.

Layers:
- protocol.py   pure framing/parsing/fault decoding (no I/O)
- client.py     TCP transport, typed read API, guarded writes, transaction log
- simulator.py  fake controller for bench-less testing
- cli.py        probe / snapshot / watch / raw / guarded-write commands
"""
from .protocol import (
    CR,
    FAULT_NAMES,
    ErrorStatus,
    ProtocolError,
    Reply,
    decode_reply,
    encode,
    format_temperature,
    parse_error_status,
    parse_number,
    parse_reply,
    parse_temperature,
)
from .client import HVC3500Client, Transaction, WriteRefused

__all__ = [
    "CR", "FAULT_NAMES", "ErrorStatus", "ProtocolError", "Reply",
    "decode_reply", "encode", "format_temperature", "parse_error_status",
    "parse_number", "parse_reply", "parse_temperature",
    "HVC3500Client", "Transaction", "WriteRefused",
]
