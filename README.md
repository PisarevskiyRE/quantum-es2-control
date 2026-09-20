<img width="876" height="679" alt="image" src="https://github.com/user-attachments/assets/72ac14c2-da80-4937-88cf-32bf77626134" />


# quantum-es2-control

> **Unofficial.** Not affiliated with or endorsed by PreSonus. The protocol was reverse-engineered
> from USB traffic of the vendor's own software for interoperability. Everything is provided
> **as is, at your own risk**: the tool writes settings to the device. In particular, +48V phantom power
> can damage ribbon microphones; many controls are decoded from captures but not yet tested one by one
> (see Status). Tested only on a Quantum ES 2 with firmware v3.03.112204.

Linux GUI for controlling a PreSonus Quantum ES 2 audio interface — input
preamp gain, +48V phantom power, pad, direct monitor mix, headphone/output
levels, etc. PreSonus only ships a control panel (Universal Control) for
Windows/macOS; on Linux the device works as a plain class-compliant USB
Audio 2.0 interface (see `docs/findings.md`), but none of the interesting
controls are reachable through ALSA. This project reverse-engineers the
vendor protocol PreSonus's own software uses and reimplements it natively.

## Status

Working Qt GUI (PySide6) laid out like Universal Control. Inputs 1-2: gain, +48V, low cut, auto gain, stereo
link, pan, mute/solo, mixer fader into Main, level meter. Outputs: Main Out knob, Phones knob, Dim, Mute,
Main L/R fader. Audio settings (sample rate, buffer, latency) are in the "Настройки" dialog and go through
PipeWire. Not implemented on purpose: the native copy button; the headphone button is an indicator only.

Verified live: gain (readback), input 1 meter, and the user's overall check that the GUI works. Everything else
follows decoded captures but was not tested control by control. The mixer matrix (faders, pan, mute/solo, main
fader) cannot be read back, so the GUI keeps its own model and starts from main 0 dB / faders -96 dB.
Protocol details: `docs/protocol.md`.

Run (the device must not be held by the VM or another program, and udev
rule must be installed, see `udev/`):

    .venv/bin/python -m quantumcontrol          # real device
    .venv/bin/python -m quantumcontrol --demo   # fake device, no hardware

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

## Contributing

Issues and pull requests are welcome, especially: testing controls on your own unit, other firmware
versions, other Quantum ES models (ES 4, ES 8, ES 16), and captures of features not decoded yet
(`docs/HANDOFF.md` lists open questions, `docs/capture-plan.md` explains how to capture). Raw captures
may contain your device serial number: check before sharing.

## License

GPL-3.0-or-later, see `LICENSE`. "PreSonus" and "Quantum" are trademarks of their owners.
