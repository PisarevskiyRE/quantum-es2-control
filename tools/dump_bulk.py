#!/usr/bin/env python3
"""Dump IF5 bulk (EP1) payloads from a usbmon pcapng, trailing zeros trimmed."""
import subprocess
import sys
from collections import Counter

pcap = sys.argv[1]
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 40

out = subprocess.run(
    ["tshark", "-r", pcap, "-Y", "usb.endpoint_address.number==1 && usb.data_len>0",
     "-T", "fields", "-e", "frame.number", "-e", "frame.time_relative",
     "-e", "usb.endpoint_address.direction", "-e", "usb.capdata"],
    capture_output=True, text=True, check=True).stdout

rows = []
for line in out.splitlines():
    parts = line.split("\t")
    if len(parts) < 4:
        continue
    n, t, d, hexs = parts
    data = bytes.fromhex(hexs.replace(":", ""))
    rows.append((int(n), float(t), "IN " if d == "1" else "OUT", data))

print(f"{len(rows)} bulk transfers with data")
sizes = Counter(len(r[3]) for r in rows)
print("payload sizes:", dict(sizes))
heads = Counter((r[2], r[3][:4].hex()) for r in rows)
print("direction/first4 bytes:", dict(heads))
print()
for n, t, d, data in rows[:limit]:
    trimmed = data.rstrip(b"\x00")
    print(f"#{n} t={t:.3f} {d} len={len(data)} nz={len(trimmed)}: {trimmed.hex()}")
