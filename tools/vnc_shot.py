"""Minimal read-only VNC (RFB 3.3/3.8) screenshot grabber for the HVC-3500 HMI.

Usage:
    python tools/vnc_shot.py HOST [PORT] [--password PW] [--out file.png]
    python tools/vnc_shot.py HOST --tap X Y        # one touch at pixel (X, Y), then screenshot
    python tools/vnc_shot.py HOST --hold X Y 2.5   # press-and-hold (e.g. UniApps corner), then screenshot

Only Raw encoding is requested, so it works against any server. Standard
library only; writes an 8-bit RGB PNG.
"""
from __future__ import annotations

import argparse
import socket
import struct
import sys
import time
import zlib


def _recv_exact(s: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("server closed connection")
        buf += chunk
    return buf


# --- VNC "auth" (DES with reversed-bit key) -----------------------------------
def _des_encrypt_block(key: bytes, block: bytes) -> bytes:
    """Tiny pure-Python single-block DES, used only for the RFB challenge."""
    PC1 = [57,49,41,33,25,17,9,1,58,50,42,34,26,18,10,2,59,51,43,35,27,19,11,3,60,52,44,36,
           63,55,47,39,31,23,15,7,62,54,46,38,30,22,14,6,61,53,45,37,29,21,13,5,28,20,12,4]
    PC2 = [14,17,11,24,1,5,3,28,15,6,21,10,23,19,12,4,26,8,16,7,27,20,13,2,
           41,52,31,37,47,55,30,40,51,45,33,48,44,49,39,56,34,53,46,42,50,36,29,32]
    IP = [58,50,42,34,26,18,10,2,60,52,44,36,28,20,12,4,62,54,46,38,30,22,14,6,64,56,48,40,32,24,16,8,
          57,49,41,33,25,17,9,1,59,51,43,35,27,19,11,3,61,53,45,37,29,21,13,5,63,55,47,39,31,23,15,7]
    FP = [40,8,48,16,56,24,64,32,39,7,47,15,55,23,63,31,38,6,46,14,54,22,62,30,37,5,45,13,53,21,61,29,
          36,4,44,12,52,20,60,28,35,3,43,11,51,19,59,27,34,2,42,10,50,18,58,26,33,1,41,9,49,17,57,25]
    E = [32,1,2,3,4,5,4,5,6,7,8,9,8,9,10,11,12,13,12,13,14,15,16,17,16,17,18,19,20,21,20,21,22,23,24,25,
         24,25,26,27,28,29,28,29,30,31,32,1]
    P = [16,7,20,21,29,12,28,17,1,15,23,26,5,18,31,10,2,8,24,14,32,27,3,9,19,13,30,6,22,11,4,25]
    S = [
        [14,4,13,1,2,15,11,8,3,10,6,12,5,9,0,7,0,15,7,4,14,2,13,1,10,6,12,11,9,5,3,8,4,1,14,8,13,6,2,11,15,12,9,7,3,10,5,0,15,12,8,2,4,9,1,7,5,11,3,14,10,0,6,13],
        [15,1,8,14,6,11,3,4,9,7,2,13,12,0,5,10,3,13,4,7,15,2,8,14,12,0,1,10,6,9,11,5,0,14,7,11,10,4,13,1,5,8,12,6,9,3,2,15,13,8,10,1,3,15,4,2,11,6,7,12,0,5,14,9],
        [10,0,9,14,6,3,15,5,1,13,12,7,11,4,2,8,13,7,0,9,3,4,6,10,2,8,5,14,12,11,15,1,13,6,4,9,8,15,3,0,11,1,2,12,5,10,14,7,1,10,13,0,6,9,8,7,4,15,14,3,11,5,2,12],
        [7,13,14,3,0,6,9,10,1,2,8,5,11,12,4,15,13,8,11,5,6,15,0,3,4,7,2,12,1,10,14,9,10,6,9,0,12,11,7,13,15,1,3,14,5,2,8,4,3,15,0,6,10,1,13,8,9,4,5,11,12,7,2,14],
        [2,12,4,1,7,10,11,6,8,5,3,15,13,0,14,9,14,11,2,12,4,7,13,1,5,0,15,10,3,9,8,6,4,2,1,11,10,13,7,8,15,9,12,5,6,3,0,14,11,8,12,7,1,14,2,13,6,15,0,9,10,4,5,3],
        [12,1,10,15,9,2,6,8,0,13,3,4,14,7,5,11,10,15,4,2,7,12,9,5,6,1,13,14,0,11,3,8,9,14,15,5,2,8,12,3,7,0,4,10,1,13,11,6,4,3,2,12,9,5,15,10,11,14,1,7,6,0,8,13],
        [4,11,2,14,15,0,8,13,3,12,9,7,5,10,6,1,13,0,11,7,4,9,1,10,14,3,5,12,2,15,8,6,1,4,11,13,12,3,7,14,10,15,6,8,0,5,9,2,6,11,13,8,1,4,10,7,9,5,0,15,14,2,3,12],
        [13,2,8,4,6,15,11,1,10,9,3,14,5,0,12,7,1,15,13,8,10,3,7,4,12,5,6,11,0,14,9,2,7,11,4,1,9,12,14,2,0,6,10,13,15,3,5,8,2,1,14,7,4,10,8,13,15,12,9,0,3,5,6,11],
    ]
    SHIFTS = [1,1,2,2,2,2,2,2,1,2,2,2,2,2,2,1]

    def bits(data: bytes) -> list[int]:
        return [(b >> (7 - i)) & 1 for b in data for i in range(8)]

    def perm(src, table):
        return [src[i - 1] for i in table]

    def to_bytes(bl):
        return bytes(int("".join(map(str, bl[i:i + 8])), 2) for i in range(0, len(bl), 8))

    k = perm(bits(key), PC1)
    c, d = k[:28], k[28:]
    subkeys = []
    for sh in SHIFTS:
        c, d = c[sh:] + c[:sh], d[sh:] + d[:sh]
        subkeys.append(perm(c + d, PC2))
    b = perm(bits(block), IP)
    l, r = b[:32], b[32:]
    for sk in subkeys:
        e = [x ^ y for x, y in zip(perm(r, E), sk)]
        out = []
        for i in range(8):
            six = e[i * 6:(i + 1) * 6]
            row = six[0] * 2 + six[5]
            col = six[1] * 8 + six[2] * 4 + six[3] * 2 + six[4]
            v = S[i][row * 16 + col]
            out += [(v >> 3) & 1, (v >> 2) & 1, (v >> 1) & 1, v & 1]
        f = perm(out, P)
        l, r = r, [x ^ y for x, y in zip(l, f)]
    return to_bytes(perm(r + l, FP))


def vnc_auth_response(password: str, challenge: bytes) -> bytes:
    pw = (password.encode("latin1") + b"\0" * 8)[:8]
    key = bytes(int(f"{b:08b}"[::-1], 2) for b in pw)     # RFB reverses the bits of each key byte
    return b"".join(_des_encrypt_block(key, challenge[i:i + 8]) for i in (0, 8))


# --- PNG ---------------------------------------------------------------------
def write_png(path: str, width: int, height: int, rgb_rows: list[bytes]) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + row for row in rgb_rows)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


# --- RFB session ---------------------------------------------------------------
class VNC:
    def __init__(self, host: str, port: int = 5900, password: str | None = None, timeout: float = 10.0):
        self.s = socket.create_connection((host, port), timeout=timeout)
        ver = _recv_exact(self.s, 12)
        print("server version:", ver.strip().decode())
        self.s.sendall(b"RFB 003.008\n")
        n = _recv_exact(self.s, 1)[0]
        if n == 0:
            reason_len = struct.unpack(">I", _recv_exact(self.s, 4))[0]
            raise ConnectionError("server refused: " + _recv_exact(self.s, reason_len).decode(errors="replace"))
        types = list(_recv_exact(self.s, n))
        print("security types offered:", types, "(1=None, 2=VNC password)")
        if 1 in types:
            self.s.sendall(b"\x01")
        elif 2 in types:
            if password is None:
                raise SystemExit("server requires a VNC password; pass --password")
            self.s.sendall(b"\x02")
            challenge = _recv_exact(self.s, 16)
            self.s.sendall(vnc_auth_response(password, challenge))
        else:
            raise SystemExit(f"unsupported security types {types}")
        result = struct.unpack(">I", _recv_exact(self.s, 4))[0]
        if result != 0:
            raise SystemExit("VNC authentication failed")
        self.s.sendall(b"\x01")                                    # ClientInit, shared
        w, h = struct.unpack(">HH", _recv_exact(self.s, 4))
        pf = _recv_exact(self.s, 16)
        name_len = struct.unpack(">I", _recv_exact(self.s, 4))[0]
        self.name = _recv_exact(self.s, name_len).decode(errors="replace")
        self.w, self.h = w, h
        (self.bpp, self.depth, self.big_endian, self.true_colour, self.rmax, self.gmax, self.bmax,
         self.rshift, self.gshift, self.bshift) = struct.unpack(">BBBBHHHBBB", pf[:13])
        print(f"desktop '{self.name}' {w}x{h}, {self.bpp} bpp, depth {self.depth}, true colour {self.true_colour}")
        # SetEncodings: Raw only
        self.s.sendall(struct.pack(">BxHi", 2, 1, 0))
        self.fb = bytearray(w * h * (self.bpp // 8))

    def pointer(self, x: int, y: int, pressed: bool) -> None:
        self.s.sendall(struct.pack(">BBHH", 5, 1 if pressed else 0, x, y))

    def tap(self, x: int, y: int, hold_s: float = 0.15) -> None:
        # Real viewers send motion events before a press; some HMIs ignore a
        # press that arrives without a preceding move to the same point.
        for dx in (-40, -20, -5, 0):
            self.pointer(x + dx, y, False)
            time.sleep(0.05)
        self.pointer(x, y, True)
        time.sleep(hold_s)
        self.pointer(x, y, False)
        time.sleep(0.05)
        self.pointer(x + 1, y + 1, False)

    def refresh(self) -> None:
        self.s.sendall(struct.pack(">BBHHHH", 3, 0, 0, 0, self.w, self.h))   # full, non-incremental
        bypp = self.bpp // 8
        while True:
            mtype = _recv_exact(self.s, 1)[0]
            if mtype == 0:
                nrect = struct.unpack(">xH", _recv_exact(self.s, 3))[0]
                for _ in range(nrect):
                    x, y, w, h, enc = struct.unpack(">HHHHi", _recv_exact(self.s, 12))
                    if enc != 0:
                        raise SystemExit(f"unexpected encoding {enc}")
                    data = _recv_exact(self.s, w * h * bypp)
                    for row in range(h):
                        off = ((y + row) * self.w + x) * bypp
                        self.fb[off:off + w * bypp] = data[row * w * bypp:(row + 1) * w * bypp]
                return
            elif mtype == 1:      # SetColourMapEntries
                _, first, n = struct.unpack(">xHH", _recv_exact(self.s, 5))
                _recv_exact(self.s, n * 6)
            elif mtype == 2:      # Bell
                pass
            elif mtype == 3:      # ServerCutText
                ln = struct.unpack(">xxxI", _recv_exact(self.s, 7))[0]
                _recv_exact(self.s, ln)
            else:
                raise SystemExit(f"unknown server message {mtype}")

    def to_png(self, path: str) -> None:
        bypp = self.bpp // 8
        fmt = (">" if self.big_endian else "<") + {1: "B", 2: "H", 4: "I"}[bypp]
        rows = []
        for y in range(self.h):
            row = bytearray()
            for x in range(self.w):
                px = struct.unpack_from(fmt, self.fb, (y * self.w + x) * bypp)[0]
                r = (px >> self.rshift) & self.rmax
                g = (px >> self.gshift) & self.gmax
                b = (px >> self.bshift) & self.bmax
                row += bytes((r * 255 // self.rmax, g * 255 // self.gmax, b * 255 // self.bmax))
            rows.append(bytes(row))
        write_png(path, self.w, self.h, rows)

    def close(self) -> None:
        self.s.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("host")
    ap.add_argument("port", nargs="?", type=int, default=5900)
    ap.add_argument("--password")
    ap.add_argument("--out", default="hmi.png")
    ap.add_argument("--tap", nargs=2, type=int, metavar=("X", "Y"), action="append", default=[],
                    help="touch a point before the screenshot (repeatable, in order)")
    ap.add_argument("--hold", nargs=3, metavar=("X", "Y", "SECONDS"), help="press-and-hold before the screenshot")
    ap.add_argument("--settle", type=float, default=1.0, help="seconds to wait after input before capturing")
    a = ap.parse_args(argv)
    v = VNC(a.host, a.port, a.password)
    v.refresh()
    if a.hold:
        x, y, secs = int(a.hold[0]), int(a.hold[1]), float(a.hold[2])
        print(f"hold ({x},{y}) for {secs}s")
        v.tap(x, y, secs)
        time.sleep(a.settle)
    for x, y in a.tap:
        print(f"tap ({x},{y})")
        v.tap(x, y)
        time.sleep(a.settle)
    v.refresh()
    v.to_png(a.out)
    print("wrote", a.out)
    v.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
