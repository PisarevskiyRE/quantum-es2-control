"""Client for the Quantum ES 2 vendor control interface (IF5). See docs/protocol.md."""
import math
import struct

import usb.core
import usb.util

VID, PID = 0x194F, 0x0609
IFACE, ALT = 5, 1
EP_OUT, EP_IN = 0x01, 0x81
POLL_LEN = 752

SECTION_OUT, SECTION_IN = 0, 1
P_IN_STEREO_LINK, P_IN_GAIN, P_IN_LOWCUT, P_IN_AUTOGAIN, P_IN_PHANTOM = 1, 2, 4, 6, 10
P_OUT_MONITOR, P_OUT_PHONES = 2, 7

STATE_BASE, STATE_STRIDE = 376, 19
OFF_MONITOR, OFF_PHONES = 312, 324
OFF_METER = 28  # float32 linear peak per input, 4 bytes apart

GAIN_MIN, GAIN_MAX = 0.0, 75.0
VOL_MIN, VOL_MAX = -96.0, 0.0
MAIN_MIN, MAIN_MAX = -96.0, 10.0

FADER_MIN, FADER_MAX = -96.0, 10.0
OFF_DB = -145.0  # what the mixer uses for a silent crosspoint


class QuantumES2:
    def __init__(self):
        self.dev = usb.core.find(idVendor=VID, idProduct=PID)
        if self.dev is None:
            raise RuntimeError("Quantum ES 2 not found")
        self.seq = 1
        # The mixer matrix cannot be read back; these are what we assume until the user moves a control.
        self.main, self.faders, self.pans = 0.0, [FADER_MIN, FADER_MIN], [0.0, 0.0]
        usb.util.claim_interface(self.dev, IFACE)
        self.dev.set_interface_altsetting(IFACE, ALT)

    def close(self):
        try:
            usb.util.release_interface(self.dev, IFACE)
        finally:
            usb.util.dispose_resources(self.dev)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _next_seq(self):
        self.seq = (self.seq + 1) & 0xFFFFFFFF
        return self.seq

    def _xfer(self, msg):
        self.dev.write(EP_OUT, msg, timeout=1000)
        return bytes(self.dev.read(EP_IN, 1024, timeout=1000))

    def poll(self):
        msg = struct.pack("<HHI8sI4sH", POLL_LEN, 0x0101, self._next_seq(),
                          b"PteGlppA", 0, b"tSUQ", 0x02DC)
        return self._xfer(msg.ljust(POLL_LEN, b"\0"))

    def state(self):
        r = self.poll()
        chans = []
        for ch in range(2):
            b = STATE_BASE + ch * STATE_STRIDE
            chans.append({
                "gain_db": struct.unpack_from("<f", r, b)[0],
                "phantom": bool(r[b + 9]),
                "lowcut": bool(r[b + 11]),
                "link": bool(r[b + 13]),
                "autogain": bool(r[b + 14]),
                "level": struct.unpack_from("<f", r, OFF_METER + 4 * ch)[0],
            })
        return {
            "channels": chans,
            "monitor_db": struct.unpack_from("<f", r, OFF_MONITOR)[0],
            "phones_db": struct.unpack_from("<f", r, OFF_PHONES)[0],
            "firmware": r[348:360].decode("ascii", "replace"),
        }

    def _set(self, section, channel, param, packed, tag):
        msg = struct.pack("<HHI8sI4sIII4s", 40, 0x0101, self._next_seq(),
                          b"PteSlppA", section, tag, 20, channel, param, packed)
        return self._xfer(msg)

    def _set_float(self, section, channel, param, value):
        return self._set(section, channel, param, struct.pack("<f", value), b"araP")

    def _set_int(self, section, channel, param, value):
        return self._set(section, channel, param, struct.pack("<I", int(value)), b"iraP")

    def set_gain(self, channel, db):
        db = min(max(db, GAIN_MIN), GAIN_MAX)
        return self._set_float(SECTION_IN, channel, P_IN_GAIN, db)

    def set_phantom(self, channel, on):
        return self._set_int(SECTION_IN, channel, P_IN_PHANTOM, on)

    def set_lowcut(self, channel, on):
        return self._set_int(SECTION_IN, channel, P_IN_LOWCUT, on)

    def start_autogain(self, channel):
        return self._set_int(SECTION_IN, channel, P_IN_AUTOGAIN, 1)

    def set_monitor_volume(self, db):
        db = min(max(db, VOL_MIN), VOL_MAX)
        return self._set_float(SECTION_OUT, 0, P_OUT_MONITOR, db)

    def set_phones_volume(self, db):
        db = min(max(db, VOL_MIN), VOL_MAX)
        return self._set_float(SECTION_OUT, 0, P_OUT_PHONES, db)

    def _send_mix(self, records):
        """Send a 516-byte mixer block: 32-byte header, (u32 key, f32 dB) records, count at 512.
        Key = index | side << 24; index 0/1 = input 1/2, 0x0a..0x0d = DAW returns; side 0/1 = L/R."""
        b = bytearray(516)
        b[0:32] = struct.pack("<HHI4sII4sII", 516, 0x0101, self._next_seq(), b"PteS", 0, 0,
                              b"mrpm", 0x1F0, 0)
        for i, (key, value) in enumerate(records):
            struct.pack_into("<If", b, 32 + 8 * i, key, value)
        struct.pack_into("<I", b, 512, len(records))
        return self._xfer(bytes(b))

    def _input_level(self, ch, side):
        """Crosspoint of input `ch` into Main L/R: fader + main + constant-power pan gain."""
        theta = (self.pans[ch] + 1) * math.pi / 4
        g = math.cos(theta) if side == 0 else math.sin(theta)
        if g < 1e-7:
            return OFF_DB
        return max(self.faders[ch] + self.main + 20 * math.log10(g), OFF_DB)

    def set_main_volume(self, db):
        """Main L/R fader. UC resends every crosspoint, since they all include the main level."""
        v = self.main = min(max(db, MAIN_MIN), MAIN_MAX)
        records = []
        for side in (0, 1):
            c = side << 24
            records += [(c | 0, self._input_level(0, side)), (c | 1, self._input_level(1, side)),
                        (c | 0x0A, v if side == 0 else -145.0),
                        (c | 0x0B, -145.0 if side == 0 else v),
                        (c | 0x0C, v - 96 if side == 0 else -145.0),
                        (c | 0x0D, -145.0 if side == 0 else v - 96)]
        return self._send_mix(records)

    def _send_input(self, channel):
        return self._send_mix([(channel | side << 24, self._input_level(channel, side))
                               for side in (0, 1)])

    def set_input_fader(self, channel, db):
        """Mixer fader of input 1/2: updates its left and right Main crosspoints only."""
        self.faders[channel] = min(max(db, FADER_MIN), FADER_MAX)
        return self._send_input(channel)

    def set_input_pan(self, channel, pan):
        """Pan of input 1/2, -1 (left) .. +1 (right). UC also rewrites two send pairs that sit at -96 dB; skipped."""
        self.pans[channel] = min(max(pan, -1.0), 1.0)
        return self._send_input(channel)
