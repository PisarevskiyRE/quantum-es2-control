# Handoff / state of the project (written 2026-09-20 for the next session)

Goal: Linux GUI for the PreSonus Quantum ES 2 (USB 194f:0609) that looks like Universal Control. The GUI is
working; see README.md for the feature list and docs/protocol.md for the wire format.

## How to run
- GUI: `cd the project directory && .venv/bin/python -m quantumcontrol` (`--demo` = fake device).
- Tests (offline): `.venv/bin/python -m unittest discover -s tests`
- Only ONE program can hold interface 5: the GUI, `tools/watch.py`, and the Windows VM (USB passthrough) are
  mutually exclusive. Close the GUI before running tools; detach the device from the VM (virt-manager, remove the
  USB host device) before using it on Linux.
- After the VM has held the device, the user ACL is lost. Restore (user must run it with `!`, sudo needs a TTY
  which the assistant does not have): `sudo udevadm trigger --action=add --subsystem-match=usb --attr-match=idVendor=194f`
  (udev rule `udev/99-presonus-quantum.rules` is installed in /etc/udev/rules.d). Check: `getfacl /dev/bus/usb/003/002`.

## Capturing the native app (VM: Windows 10/11 "win11" in libvirt + Universal Control)
- Attach the device to the VM, then on the host: `tools/capture.sh NAME` (dumpcap on usbmon3, uses `sg wireshark`).
- One action per file, log it in `captures/session-log.md`. Analyse: `tools/msgtypes.py` (new message types),
  `tools/cmd_stats.py`, `tools/sets.py` (SetP + reply diffs), `tools/in_diff.py`, `tools/dump_bulk.py`.
- Live probe of state changes (hardware knobs etc.): `PYTHONPATH=. .venv/bin/python tools/watch.py 40` (GUI closed).
- Always filter tshark output (`usb.data_len>0`, specific endpoints): unfiltered dumps flood the context.

## Verified live vs decoded only
- Live: gain write + readback, input meters (28/32), Main L/R meters (172/176, react to music), hardware knobs
  (Main Out 312, Phones 324, gain 376/395, Dim/Mute mode 308, 48V 385) follow into the GUI, overall GUI works.
- Decoded from captures, NOT tested one by one on the device: phantom, low cut, auto gain, stereo link, Dim, Mute,
  monitor/phones writes, main fader, input faders, pan, M/S.

## Open issues
1. **User report: mute on a single input strip seems to mute Main.** Code sends only that input's 2 crosspoints
   (`set_input_mute`, keys `ch | side<<24`), so a device-side or model cause is suspected. Plan: user plays music and
   speaks into in1 with GUI closed, we drive `set_input_mute` from Python and log Main meters (172/176) per phase.
   Compare with the UC mute block from `01-ms.pcapng` (6 records incl. buses 0x0d/0x0e) - try sending those too.
2. The mixer (faders, pan, M/S, main fader) is not readable; the client assumes main 0 dB, faders -96 dB at start.
3. Phones button in the Main strip is shown as a fixed indicator; the manual calls it "Phones Listen" (routes Main
   mix to headphones), probably not clickable on ES 2 because HP Source has one choice. Unverified.
4. Gain dial is 0..75 only; a TRS line input should switch it to a -12..+12 dB trim (not captured).
5. Linked pair: only faders/pan follow in the GUI; the manual says gain/48V/HPF apply to both channels.
6. Unknown Rply words: 276..288 (four tiny floats, maybe phones/monitor meters), 316 (-10.0).

## Planned next steps (in order)
1. Capture with the device (re)plugged or the UC service restarted, to find the mixer read-back command
   (`tools/msgtypes.py` will flag unseen commands). Would remove the "assumed mixer state" problem.
2. Capture gain change while inputs are linked (does UC send both channels or does firmware mirror it?).
3. Measure the mute issue (Open issue 1).
4. Captures: line trim (TRS line plugged), mixer power button, Settings panel items (Main Encoder, HP Source, mute
   button behaviour, dim amount, LED brightness), Loopback 1/2 sends, return fader/mute/phones-listen/flip.
   The user said to leave the gear as is: ask before building the settings panel.
5. Local Scenes (JSON files), peak hold / meter decay, channel names, warning about Loopback at 176.4/192 kHz.

## Working agreements with the user
- Everything lives in the project directory (venv `.venv`, git, one commit per step).
- Speak Russian. The user tests on the real card and reports; do not touch the device while they test.
- Never enable +48V or send unverified writes to the device without saying so first (ribbon mics can be damaged).
- Copy button and native gear window are intentionally not replicated; the Phones button is an indicator.
- pip downloads are slow: run installs in the foreground with a long timeout, never `pkill -f` a pattern that
  matches your own command line.
