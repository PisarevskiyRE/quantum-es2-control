"""Offline tests for the wire format in quantumcontrol/device.py (no hardware).

Run: .venv/bin/python -m unittest discover -s tests -v
Expected bytes come from real Universal Control captures (see docs/protocol.md).
"""
import struct
import unittest

from quantumcontrol import device as d


class Stub(d.QuantumES2):
    def __init__(self):
        self.seq = 0
        self.main, self.faders, self.pans = 0.0, [d.FADER_MIN, d.FADER_MIN], [0.0, 0.0]
        self.mutes, self.solos = [False, False], [False, False]
        self._link_seen = None
        self.sent = []

    def _xfer(self, msg):
        self.sent.append(bytes(msg))
        return b""

    def records(self, i=-1):
        b = self.sent[i]
        n = struct.unpack_from("<I", b, 512)[0]
        return [(struct.unpack_from("<I", b, 32 + 8 * k)[0], struct.unpack_from("<f", b, 36 + 8 * k)[0])
                for k in range(n)]


class SetPTests(unittest.TestCase):
    def test_phantom_matches_capture(self):
        s = Stub()
        s.seq = 0xA5
        s.set_phantom(0, True)
        self.assertEqual(s.sent[0].hex(),
                         "28000101a6000000507465536c707041010000006972615014000000000000000a00000001000000")

    def test_gain_float_tag_matches_capture(self):
        s = Stub()
        s.seq = 0xE3
        s.set_gain(0, 0.375)
        self.assertEqual(s.sent[0].hex(),
                         "28000101e4000000507465536c70704101000000617261501400000000000000020000000000c03e")

    def test_output_section_and_dim_mute_mode(self):
        s = Stub()
        s.set_out_mode(2)
        b = s.sent[0]
        self.assertEqual(struct.unpack_from("<I", b, 16)[0], 0)          # section 0 = outputs
        self.assertEqual(b[20:24], b"iraP")
        self.assertEqual(struct.unpack_from("<III", b, 24 + 0, )[0:1], (20,))
        self.assertEqual(struct.unpack_from("<IIII", b, 24), (20, 0, 0, 2))

    def test_gain_is_clamped(self):
        s = Stub()
        s.set_gain(1, 999)
        self.assertAlmostEqual(struct.unpack_from("<f", s.sent[0], 36)[0], 75.0)


class MixTests(unittest.TestCase):
    def test_header_and_count(self):
        s = Stub()
        s.set_input_fader(0, -6.0)
        b = s.sent[0]
        self.assertEqual(len(b), 516)
        self.assertEqual(b[:4].hex(), "04020101")
        self.assertEqual(b[8:12], b"PteS")
        self.assertEqual(b[20:24], b"mrpm")
        self.assertEqual(struct.unpack_from("<I", b, 24)[0], 0x1F0)
        self.assertEqual(struct.unpack_from("<I", b, 512)[0], 2)

    def test_input_fader_records_and_range(self):
        s = Stub()
        s.main = 0.48
        s.set_input_fader(0, 10.0)
        (k0, v0), (k1, v1) = s.records()
        self.assertEqual((k0, k1), (0x0, 0x1000000))
        self.assertAlmostEqual(v0, 10.0 + 0.48 - 3.0, delta=0.02)   # 01-fader capture: max +7.48
        self.assertAlmostEqual(v0, v1)

    def test_pan_extremes_use_minus_145(self):
        s = Stub()
        s.main, s.faders[0] = 1.682, 0.0
        s.set_input_pan(0, -1.0)
        self.assertAlmostEqual(s.records()[0][1], 1.68, places=2)
        self.assertEqual(s.records()[1][1], -145.0)
        s.set_input_pan(0, 1.0)
        self.assertEqual(s.records()[0][1], -145.0)

    def test_pan_is_constant_power(self):
        s = Stub()
        s.main, s.faders[0] = 0.0, 0.0
        for p in (-0.7, -0.2, 0.0, 0.4, 0.9):
            s.set_input_pan(0, p)
            l, r = (10 ** (v / 10) for _, v in s.records())
            self.assertAlmostEqual(l + r, 1.0, places=3)

    def test_mute_sends_two_off_records(self):
        s = Stub()
        s.set_input_mute(1, True)
        self.assertEqual(s.records(), [(0x1, -145.0), (0x1000001, -145.0)])

    def test_solo_silences_others_and_daw(self):
        s = Stub()
        s.main = 0.48
        s.set_input_solo(0, True)
        rec = dict(s.records())
        self.assertEqual(len(rec), 12)
        self.assertNotEqual(rec[0x0], -145.0)                  # soloed input stays audible
        for key in (0x1, 0x1000001, 0xA, 0xB, 0xC, 0xD, 0x100000A, 0x100000B, 0x100000C, 0x100000D):
            self.assertEqual(rec[key], -145.0, hex(key))

    def test_main_block_layout_matches_capture(self):
        s = Stub()
        s.set_main_volume(-1.729)
        rec = s.records()
        self.assertEqual([k for k, _ in rec], [0x0, 0x1, 0xA, 0xB, 0xC, 0xD,
                                             0x1000000, 0x1000001, 0x100000A, 0x100000B, 0x100000C, 0x100000D])
        vals = dict(rec)
        # 10-main-out capture: v - 99. UC uses exactly -3.0 dB at pan centre, we use the exact -3.0103: 0.01 dB apart
        self.assertAlmostEqual(vals[0x0], -1.729 - 96 - 3, delta=0.02)
        self.assertAlmostEqual(vals[0xA], -1.729, places=3)
        self.assertAlmostEqual(vals[0xC], -1.729 - 96, places=3)
        self.assertEqual(vals[0x100000A], -145.0)
        self.assertAlmostEqual(vals[0x100000B], -1.729, places=3)

    def test_stereo_link_records(self):
        s = Stub()
        s.main, s.faders[0] = 0.48, 1.2
        s.set_stereo_link(True)
        # SetP param 1 to ch2 then ch1, then the mix block
        self.assertEqual([struct.unpack_from("<IIII", m, 24) for m in s.sent[:2]], [(20, 1, 1, 1), (20, 0, 1, 1)])
        rec = dict(s.records())
        self.assertAlmostEqual(rec[0x0], 1.68, places=2)
        self.assertEqual(rec[0x1000000], -145.0)
        self.assertEqual(rec[0x1], -145.0)
        self.assertAlmostEqual(rec[0x1000001], 1.68, places=2)
        s.set_stereo_link(False)
        for _, v in s.records():
            self.assertAlmostEqual(v, 1.68 - 3.0103, places=2)


class StateTests(unittest.TestCase):
    def test_state_decoding(self):
        r = bytearray(752)
        struct.pack_into("<f", r, 28, 0.5)
        struct.pack_into("<f", r, 172, 0.25)
        struct.pack_into("<f", r, 176, 0.125)
        struct.pack_into("<f", r, 312, -12.0)
        struct.pack_into("<f", r, 324, -30.0)
        r[308] = 1
        struct.pack_into("<f", r, 376, 42.0)
        r[385] = 1
        r[387] = 1
        r[348:360] = b"v3.03.112204"
        s = Stub()
        s.poll = lambda: bytes(r)
        st = s.state()
        c0 = st["channels"][0]
        self.assertEqual((c0["gain_db"], c0["phantom"], c0["lowcut"], c0["level"]), (42.0, True, True, 0.5))
        self.assertEqual(st["out_mode"], 1)
        self.assertEqual((st["monitor_db"], st["phones_db"]), (-12.0, -30.0))
        self.assertEqual(st["main_level"], [0.25, 0.125])
        self.assertEqual(st["firmware"], "v3.03.112204")


if __name__ == "__main__":
    unittest.main()
