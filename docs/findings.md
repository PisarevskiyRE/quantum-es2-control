# Hardware findings

Host: Fedora (KDE), kernel 7.2.5-200.fc44. Device connects over USB (not
Thunderbolt, despite the "Quantum" branding shared with the Thunderbolt-only
2626/HD8 models — the ES 2 is USB).

## ALSA

```
card 2: Q2 [Quantum ES 2], device 0: USB Audio [USB Audio]
  PreSonus Quantum ES 2 at usb-0000:13:00.3-1, high speed
```

`amixer -c 2 controls`:

| numid | iface  | name                     | notes |
|-------|--------|--------------------------|-------|
| 5     | CARD   | Internal Validity        | read-only bool, always `on` |
| 3     | MIXER  | Extension Unit Switch    | rw bool, currently `off` — untested what it does live (candidate: direct monitor enable) |
| 4     | MIXER  | MIDI Capture Volume      | rw int, 0..75 dB, stereo |
| 1     | PCM    | Capture Channel Map      | fixed FL,FR,FC,LFE,RL,RR |
| 2     | PCM    | Playback Channel Map     | fixed FL,FR,FC,LFE |

Nothing else — no per-input gain, no phantom power, no pad, no headphone
volume, no mixer routing. That's expected: UAC2 devices only expose what's
declared in Feature/Extension Units, and PreSonus put the real controls
behind the vendor interface instead (see below), reachable only via their
own software.

## USB topology (`lsusb -v -d 194f:0609`)

7 interfaces under one Interface Association (config 1):

- **IF0** — Audio Control (UAC2). Clock source (unit 7, internal
  programmable), input terminal (unit 1, 6ch line connector), an
  **Extension Unit (unit 3, `wExtensionCode 0xae01`, Enable Control r/w)** —
  this is the ALSA "Extension Unit Switch" — a Feature Unit (unit 4, Volume
  control on channels 1/2 only, *not* currently surfaced by ALSA as a
  control — worth checking why), output terminals to/from USB streaming.
  Has an interrupt IN endpoint (0x84) for standard UAC2 control-change
  notifications.
- **IF1** — Audio Streaming, capture, 6ch, 24-bit, isochronous IN (EP 0x83)
  with implicit feedback.
- **IF2** — Audio Streaming, playback, 4ch, 24-bit, isochronous OUT
  (EP 0x03) + feedback IN (EP 0x85).
- **IF3/IF4** — USB-MIDI (2 in / 2 out jacks each way; bulk EPs 0x02/0x82).
- **IF5** — **Vendor Specific Class (0xFF)**, altsetting 0 = no endpoints,
  altsetting 1 = bulk EP 0x81 IN + bulk EP 0x01 OUT, 512-byte max packet.
  No kernel driver binds to this (it's not audio/HID/anything the kernel
  recognizes) — free for us to claim via libusb. **This is the control
  channel**: gain, phantom power, pad, monitor mix, everything Universal
  Control exposes almost certainly goes through here. Confirmed by its
  string descriptor, only readable once we had rw access (see below):
  `iInterface` = **"Quantum ES 2 Control"**.
- **IF6** — DFU (firmware update), Application Specific / DFU 1.10. Leave
  alone — not in scope, and flashing firmware wrong bricks the interface.

## Access

- `getfacl` on `/dev/bus/usb/003/002` showed only `owner root, group root,
  other r--` — read-only for a normal user, not enough to claim IF5 for
  bulk transfers. `udev/99-presonus-quantum.rules` (in this repo, install to
  `/etc/udev/rules.d/`) tags the device `uaccess` so systemd-logind grants
  the active session user rw access automatically, no group hacks, no sudo
  needed after that.
- `pyusb` (installed in `.venv`) sees and enumerates the device fine
  read-only even without the rule; claiming IF5 for read/write needs the rw
  access above. Verified working (2026-09-20): `user:roy:rw-` present in the
  ACL, `usb.util.claim_interface(dev, 5)` succeeds cleanly.

## Open questions for the capture (see `docs/capture-plan.md`)

- Does IF5 speak the same UCNet framing (`"UC" 00 01 | size | code | cbytes
  | payload`) that `quantum-hd8` documented over TCP, or something else
  entirely?
- Is there a handshake/subscribe step before the device streams state, like
  UCNet's `Subscribe`/`Synchronize`?
- What do preamp gain, phantom power (+48V), pad, and monitor-mix changes
  look like as raw bytes — need one isolated capture per control (change
  exactly one thing at a time, otherwise correlation is guesswork).
