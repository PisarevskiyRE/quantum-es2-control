# QuantumControl

Linux GUI for controlling a PreSonus Quantum ES 2 audio interface — input
preamp gain, +48V phantom power, pad, direct monitor mix, headphone/output
levels, etc. PreSonus only ships a control panel (Universal Control) for
Windows/macOS; on Linux the device works as a plain class-compliant USB
Audio 2.0 interface (see `docs/findings.md`), but none of the interesting
controls are reachable through ALSA. This project reverse-engineers the
vendor protocol PreSonus's own software uses and reimplements it natively.

## Status

Pre-protocol. See `docs/findings.md` for what's been established about the
hardware and `docs/capture-plan.md` for the next concrete step: capturing
real Universal Control ↔ device traffic from a Windows VM with USB
passthrough, via `usbmon` on this host.

## Layout

- `docs/` — findings, protocol notes as they're established, capture plan.
- `udev/99-presonus-quantum.rules` — grants the logged-in user access to the
  device's vendor USB interface without root (install into
  `/etc/udev/rules.d/`, the only file this project needs outside the repo).
- `captures/` — raw `usbmon`/Wireshark captures (gitignored; binary, and may
  contain serial numbers).
- `tools/` — probing/analysis scripts used during reverse engineering.
- `quantumcontrol/` — the protocol client library and, later, the GUI.
- `.venv/` — local Python environment (pyusb for now; PySide6 once the GUI
  starts).

## Hardware facts established so far

- USB Audio Class 2.0 device, `194f:0609`, 7 USB interfaces: audio control
  (IF0), two audio streaming pairs (IF1 capture, IF2 playback), a USB-MIDI
  pair (IF3/IF4), a **vendor-specific class interface (IF5, altsetting 1,
  bulk EP 0x81 IN / 0x01 OUT)**, and a DFU interface (IF6, firmware update).
- ALSA only exposes what UAC2 already standardizes: an "Extension Unit
  Switch", MIDI capture volume, and clock source/validity. No preamp gain,
  phantom power, pad, or monitor mix controls — those live behind IF5.
- IF5 is almost certainly how PreSonus's own control app (and its
  `ucdaemon` background service) talks to the hardware. A sibling project
  (`jpfaria/quantum-hd8`) reverse-engineered that same family's protocol
  (PreSonus calls it UCNet) by sniffing `ucdaemon`'s localhost TCP socket on
  macOS — useful as a Rosetta Stone, but it's the daemon↔app protocol, not
  necessarily byte-identical to what crosses IF5 to the hardware itself.
  Worth checking once we have real IF5 traffic.
