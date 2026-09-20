"""Sample rate / buffer size via PipeWire's global clock settings (pw-metadata)."""
import re
import subprocess

RATES = [44100, 48000, 88200, 96000, 176400, 192000]
QUANTA = [32, 64, 128, 256, 512, 1024, 2048]
BITS = 24  # the interface only supports 24-bit samples (32-bit slot)


def _run(*args):
    return subprocess.run(["pw-metadata", "-n", "settings", *args], capture_output=True,
                          text=True, timeout=3, check=True).stdout


def get_settings():
    """Return {'rate','quantum','force_rate','force_quantum'} (ints)."""
    out = _run()
    def val(key):
        m = re.search(rf"key:'{re.escape(key)}' value:'(\d+)'", out)
        return int(m.group(1)) if m else 0
    return {"rate": val("clock.rate"), "quantum": val("clock.quantum"),
            "force_rate": val("clock.force-rate"), "force_quantum": val("clock.force-quantum")}


def set_rate(hz):
    """hz = 0 returns control to PipeWire (automatic)."""
    _run("0", "clock.force-rate", str(int(hz)))


def set_quantum(frames):
    """frames = 0 returns control to PipeWire (automatic)."""
    _run("0", "clock.force-quantum", str(int(frames)))
