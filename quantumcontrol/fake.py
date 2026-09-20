"""In-memory stand-in for QuantumES2, for `--demo` and UI tests."""
import math
import time


class FakeDevice:
    def __init__(self):
        self.ch = [dict(gain_db=24.0, phantom=False, lowcut=False, link=False, autogain=False)
                   for _ in range(2)]
        self.monitor, self.phones = -18.0, -30.0

    def close(self):
        pass

    def state(self):
        t = time.monotonic()
        for i, c in enumerate(self.ch):
            c["level"] = abs(math.sin(t * (1.3 + i))) * 0.35 * 10 ** ((c["gain_db"] - 24) / 20)
        return {"channels": [dict(c) for c in self.ch], "monitor_db": self.monitor,
                "phones_db": self.phones, "firmware": "v3.03.112204 (demo)"}

    def set_gain(self, ch, db): self.ch[ch]["gain_db"] = db
    def set_phantom(self, ch, on): self.ch[ch]["phantom"] = on
    def set_lowcut(self, ch, on): self.ch[ch]["lowcut"] = on
    def start_autogain(self, ch): pass
    def set_monitor_volume(self, db): self.monitor = db
    def set_phones_volume(self, db): self.phones = db
    def set_main_volume(self, db): pass
