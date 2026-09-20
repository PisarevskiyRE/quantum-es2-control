#!/usr/bin/env python3
"""Show which byte offsets of IF5 IN replies vary across a capture, and decode as floats."""
import subprocess, sys, struct
pcap = sys.argv[1]
out = subprocess.run(
    ["tshark", "-r", pcap, "-Y", "usb.endpoint_address.number==1 && usb.endpoint_address.direction==1 && usb.data_len>0",
     "-T", "fields", "-e", "usb.capdata"], capture_output=True, text=True, check=True).stdout
pk = [bytes.fromhex(l.replace(":", "")) for l in out.splitlines()]
print(len(pk), "IN packets")
varying = sorted(i for i in range(752) if len({p[i] for p in pk}) > 1)
# collapse into ranges
rng = []
for i in varying:
    if rng and i == rng[-1][1] + 1: rng[-1][1] = i
    else: rng.append([i, i])
print("varying byte ranges:", [(a, b) for a, b in rng])
nz = [i for i in range(752) if any(p[i] for p in pk)]
print("last nonzero offset:", max(nz))
def f(p, o): return struct.unpack_from("<f", p, o)[0]
last = pk[-1]
print("\nlast packet, u32/float view of nonzero words (offset: hex float):")
for o in range(0, 400, 4):
    w = last[o:o+4]
    if any(w): print(f"  {o:3}: {w.hex()} f={f(last,o):.4g} u32={struct.unpack_from('<I', last, o)[0]}")
