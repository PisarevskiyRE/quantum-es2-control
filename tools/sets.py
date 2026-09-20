#!/usr/bin/env python3
"""List SetP commands in a capture, with reply-state diffs (offsets != meters/seq)."""
import subprocess, sys, struct
f = sys.argv[1]
out = subprocess.run(["tshark","-r",f,"-Y","usb.endpoint_address.number==1 && usb.data_len>0","-T","fields",
    "-e","frame.number","-e","frame.time_relative","-e","usb.endpoint_address.direction","-e","usb.capdata"],
    capture_output=True, text=True).stdout
rows = []
for l in out.splitlines():
    n,t,d,h = l.split("\t"); rows.append((int(n),float(t),d,bytes.fromhex(h.replace(":",""))))
def rep(i, step):
    while 0 <= i < len(rows) and not (rows[i][2]=='1' and rows[i][3][8:12]==b'ylpR'): i += step
    return rows[i][3]
others = {r[3][8:12] for r in rows if r[2]=='0'}
print("OUT commands:", others)
for i,(n,t,d,b) in enumerate(rows):
    if d=='0' and b[8:12]==b'PteS':
        body = b[:b[0]]
        w = struct.unpack_from("<%dI" % ((len(body)-24)//4), body, 24)
        a, c = rep(i,-1), rep(i,1)
        diff = [(o,a[o],c[o]) for o in range(752) if a[o]!=c[o] and not 28<=o<36 and o!=4]
        print(f"#{n} t={t:.2f} len={len(body)} words@24={list(w)} f={[round(struct.unpack('<f',struct.pack('<I',x))[0],3) for x in w]}")
        print("     reply diff:", [(o,hex(x),hex(y)) for o,x,y in diff])
