#!/usr/bin/env python3
"""Summarise every distinct IF5 message type in a capture: direction, length field, command fourccs, tag.

Use it on a fresh capture (e.g. replug / service restart) to spot commands we have never seen.
Known: GetP/Rply (752 B poll), SetP 40 B, mrpm 516 B mixer block, 8 B ack.

    python3 tools/msgtypes.py captures/NAME.pcapng [--examples N]
"""
import struct
import subprocess
import sys
from collections import OrderedDict

pcap = sys.argv[1]
n_examples = int(sys.argv[sys.argv.index("--examples") + 1]) if "--examples" in sys.argv else 1
out = subprocess.run(
    ["tshark", "-r", pcap, "-Y", "usb.endpoint_address.number==1 && usb.data_len>0", "-T", "fields",
     "-e", "frame.number", "-e", "frame.time_relative", "-e", "usb.endpoint_address.direction",
     "-e", "usb.capdata"], capture_output=True, text=True, check=True).stdout

KNOWN = {("OUT", 752, b"PteG"), ("IN", 752, b"ylpR"), ("OUT", 40, b"PteS"), ("OUT", 516, b"PteS"),
         ("IN", 8, b"")}
groups = OrderedDict()
for line in out.splitlines():
    num, t, d, hx = line.split("\t")
    b = bytes.fromhex(hx.replace(":", ""))
    direction = "IN" if d == "1" else "OUT"
    length = struct.unpack_from("<H", b, 0)[0] if len(b) >= 2 else 0
    cmd = b[8:12][::-1].decode("ascii", "replace") if len(b) >= 12 else ""
    key = (direction, length, b[8:12] if len(b) > 8 else b"", b[20:24] if len(b) >= 24 else b"")
    g = groups.setdefault(key, {"count": 0, "first": (int(num), float(t)), "ex": []})
    g["count"] += 1
    if len(g["ex"]) < n_examples:
        g["ex"].append(b.rstrip(b"\0"))

print(f"{'dir':3} {'len':>4} {'cmd':6} {'tag':6} {'count':>6} first(frame,t)  known")
for (direction, length, cmd, tag), g in groups.items():
    known = (direction, length, cmd) in KNOWN
    print(f"{direction:3} {length:4} {cmd[::-1].decode('ascii','replace'):6} {tag[::-1].decode('ascii','replace'):6} "
          f"{g['count']:6} {g['first']}  {'' if known else '<-- NEW'}")
    if not known:
        for ex in g["ex"]:
            print("     ", ex[:96].hex(), "..." if len(ex) > 96 else "")
