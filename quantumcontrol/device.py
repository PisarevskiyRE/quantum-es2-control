"""Minimal client for the Quantum ES 2 vendor control interface (IF5)."""
import struct
import usb.core
import usb.util

VID, PID = 0x194F, 0x0609
IFACE, ALT = 5, 1
EP_OUT, EP_IN = 0x01, 0x81
POLL_LEN = 752

PARAM_GAIN = 2
PARAM_PHANTOM = 10

STATE_BASE = 376
STATE_STRIDE = 19
OFF_GAIN, OFF_PHANTOM = 0, 9


class QuantumES2:
    def __init__(self):
        self.dev = usb.core.find(idVendor=VID, idProduct=PID)
        if self.dev is None:
            raise RuntimeError("Quantum ES 2 not found")
        self.seq = 1
        usb.util.claim_interface(self.dev, IFACE)
        self.dev.set_interface_altsetting(IFACE, ALT)

    def close(self):
        usb.util.release_interface(self.dev, IFACE)
        usb.util.dispose_resources(self.dev)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _next_seq(self):
        self.seq = (self.seq + 1) & 0xFFFFFFFF
        return self.seq

    def poll(self):
        """Send GetP, return the 752-byte Rply."""
        msg = struct.pack("<HHI8sI4sH", POLL_LEN, 0x0101, self._next_seq(),
                          b"PteGlppA", 0, b"tSUQ", 0x02DC)
        self.dev.write(EP_OUT, msg.ljust(POLL_LEN, b"\0"), timeout=1000)
        return bytes(self.dev.read(EP_IN, 1024, timeout=1000))

    def state(self):
        r = self.poll()
        chans = []
        for ch in range(2):
            base = STATE_BASE + ch * STATE_STRIDE
            chans.append({
                "gain_db": struct.unpack_from("<f", r, base + OFF_GAIN)[0],
                "phantom": bool(r[base + OFF_PHANTOM]),
            })
        return {"channels": chans, "firmware": r[348:360].decode("ascii", "replace")}

    def _set(self, channel, param, packed_value, tag):
        msg = struct.pack("<HHI8sI4sIII4s", 40, 0x0101, self._next_seq(),
                          b"PteSlppA", 1, tag, 20, channel, param, packed_value)
        self.dev.write(EP_OUT, msg, timeout=1000)
        ack = bytes(self.dev.read(EP_IN, 1024, timeout=1000))
        return ack

    def set_gain(self, channel, db):
        return self._set(channel, PARAM_GAIN, struct.pack("<f", db), b"araP")

    def set_phantom(self, channel, on):
        return self._set(channel, PARAM_PHANTOM, struct.pack("<I", int(on)), b"iraP")
