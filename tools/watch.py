#!/usr/bin/env python3
"""Poll the device and print every change in the Rply (except meters), to find hardware-knob state.

Usage: .venv/bin/python tools/watch.py [seconds]   (close the GUI first: only one program can hold IF5)
"""
import struct
import sys
import time

from quantumcontrol.device import QuantumES2

METER = set(range(28, 36)) | set(range(172, 180)) | set(range(276, 292))  # constantly moving (meters)
secs = float(sys.argv[1]) if len(sys.argv) > 1 else 40
with QuantumES2() as d:
    prev = d.poll()
    print("watching", secs, "s - operate the hardware controls now")
    t0 = time.monotonic()
    while time.monotonic() - t0 < secs:
        r = d.poll()
        diff = [i for i in range(8, 752) if r[i] != prev[i] and i not in METER and i != 4]
        if diff:
            words = sorted({i // 4 * 4 for i in diff})
            desc = ", ".join(f"{w}: {prev[w:w + 4].hex()}->{r[w:w + 4].hex()} (f={struct.unpack_from('<f', r, w)[0]:.3g})"
                             for w in words)
            print(f"t={time.monotonic() - t0:6.2f}  {desc}")
        prev = r
        time.sleep(0.02)
