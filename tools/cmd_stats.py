#!/usr/bin/env python3
"""Group IF5 bulk packets by (direction, command header) and show first occurrences."""
import subprocess, sys
from collections import OrderedDict

pcap = sys.argv[1]
out = subprocess.run(
    ["tshark", "-r", pcap, "-Y", "usb.endpoint_address.number==1 && usb.data_len>0",
     "-T", "fields", "-e", "frame.number", "-e", "frame.time_relative",
     "-e", "usb.endpoint_address.direction", "-e", "usb.capdata"],
    capture_output=True, text=True, check=True).stdout

groups = OrderedDict()
for line in out.splitlines():
    n, t, d, hx = line.split("\t")
    data = bytes.fromhex(hx.replace(":", ""))
    key = ("IN" if d == "1" else "OUT", data[0:4].hex(), data[8:16], data[20:22], len(data.rstrip(b"\0")))
    g = groups.setdefault(key, [0, int(n), float(t)])
    g[0] += 1
for (d, h4, cmd, mag, nz), (cnt, first, t) in groups.items():
    print(f"{d:3} hdr={h4} cmd={cmd!r} {mag!r} nz={nz:4} count={cnt:5} first=#{first} t={t:.2f}")
