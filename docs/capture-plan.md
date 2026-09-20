# Capture plan: real Universal Control ↔ Quantum ES 2 traffic

Goal: get ground-truth USB traffic for interface 5 (the vendor bulk
interface, EP 0x81 IN / 0x01 OUT — see `docs/findings.md`) so the protocol
can be read off real bytes instead of guessed. Blind guessing against a
device that just silently stalls on a wrong request is not a productive use
of time; this is the step that unblocks everything else.

## 1. Set up the VM (on this host, Fedora/KDE)

Virtualization stack isn't installed yet. To get `virt-manager` + KVM:

```
sudo dnf install @virtualization virt-manager
sudo systemctl enable --now libvirtd
sudo usermod -aG libvirt $USER   # then log out/in
```

Create a Windows (or macOS) VM as usual with `virt-manager`. You supply the
installer ISO/license — not something I can source. Windows 10/11 is fine;
Universal Control is a small Qt-ish app plus a background service
(`ucdaemon`/similarly named), nothing exotic.

**Passthrough, not just a shared USB redirect**: in the VM's hardware
settings, *Add Hardware → USB Host Device* and pick "PreSonus Audio
Electronics, Inc. Quantum ES 2 (194f:0609)". This matters because plain USB
redirection (e.g. spice-vdagent's USB redir) still goes through the host's
usbfs and shows up in `usbmon` the same way host-device passthrough does —
either works, but host-device passthrough is more reliable for a
multi-interface device like this one. Once passed through, the device
disappears from the Linux host's `lsusb`/`aplay -l` while the VM has it —
that's expected and reversible (detach the device in virt-manager to get it
back).

## 2. Capture on the Linux host with usbmon + Wireshark

The physical device is still only reachable through the *host* kernel even
when passed through to the VM (QEMU relays real URBs via the host's
usbfs/libusb) — so `usbmon` on this machine sees everything, no capture
tooling needed inside the Windows guest.

```
sudo dnf install wireshark
sudo usermod -aG wireshark $USER   # then log out/in, or use pkexec dumpcap
sudo modprobe usbmon
```

Start Wireshark **before** starting the VM (or at least before opening
Universal Control), capture on interface `usbmon3` (bus 3, matching
`Bus 003 Device 002` from `lsusb` — re-check the bus number, it can shift).
Capture filter isn't very expressive for USB; just capture everything on
that bus and filter in the display:

```
usb.device_address == <addr from lsusb once passed through>
```

then narrow to the vendor interface once you see it:

```
usb.endpoint_address == 0x81 || usb.endpoint_address == 0x01
```

(Keep an unfiltered view open too — the isochronous audio streams and the
UAC2 interrupt endpoint 0x84 will be noisy but harmless; IF5's bulk
transfers are what matter.)

## 3. Method: one variable at a time

This is the part that actually determines whether the capture is usable.
The `quantum-hd8` project's notes are explicit about this after getting
burned by it (`docs/protocol.md` in that repo, "Lição de método"): measure
one variable at a time, let it settle, don't trust a reading taken while
something else is also changing.

For each step below: **stop capturing, save that slice as its own file in
`captures/` named for the action, note the exact action and timestamp in
`captures/session-log.md`, then start a fresh capture for the next one.**
Small isolated captures are far easier to read than one giant session.

1. **Cold start**: capture from before Universal Control is launched
   through the app fully showing the device's current state. This is where
   any handshake/subscribe/"give me everything" exchange will show up.
2. **Idle, ~10s**: nothing touched. Establishes keepalive traffic (if any)
   and baseline noise (e.g. meter polling).
3. **+48V phantom power**, input 1 only: toggle on, wait 2s, toggle off.
   Two separate captures (on, off) if it's easy to split.
4. **Pad**, input 1 only: same, on then off.
5. **Input 1 gain**: nudge one detent up, wait, one detent down. If the UI
   allows typing an exact dB value, do that once too (gives you a precise
   value to correlate against the raw bytes).
6. **Phones/monitor mix fader**: move one channel fader a noticeable,
   specific amount (note the before/after dB shown in the UI).
7. **Headphone output volume**: same idea, one specific move.
8. **Direct monitor toggle** (if UC exposes one distinct from the ALSA
   "Extension Unit Switch" we already have): on, then off — worth comparing
   against toggling the ALSA control directly to see if it's the same
   thing.
9. **Mute** on any one channel: on, then off.
10. **Close Universal Control** cleanly: capture the shutdown, in case
    there's an explicit unsubscribe/goodbye.

Every other control (more inputs, more mix sends, scenes if the ES 2 has
them) is very likely the same message shape with a different path/id, so
this set should be enough to derive the framing without capturing every
single control by hand — we can extrapolate once the pattern's clear and
verify against a couple of the untouched ones later.

## 4. Handing it back

Once you have the captures, save the `.pcapng` files into `captures/`
(already gitignored — they're binary and may embed the device's serial
number) along with the session log, and let me know. I'll load them and
start decoding the framing against the `quantum-hd8` UCNet notes as a
starting hypothesis.
