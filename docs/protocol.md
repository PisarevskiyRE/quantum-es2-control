# IF5 protocol notes (Quantum ES 2, vendor bulk EP 0x01 OUT / 0x81 IN)

Source: `captures/01-cold-start.pcapng` (usbmon on host, Windows 10 VM with
Universal Control, ~26 s). **Measured** = seen in bytes. **Hypothesis** = guess.

**Not UCNet.** The `"UC" 00 01 | size | code` framing from `quantum-hd8`
(daemon<->app over TCP) does not appear on the wire to the device.

## Transport (measured)

- Strict request/response polling: one 752-byte bulk OUT, then one 752-byte
  bulk IN, repeated every ~6 ms (~166 Hz). Every transfer is exactly 752 bytes,
  zero-padded; the meaningful part is much shorter.
- Only EP 1 is used during the whole capture (plus a few EP0 control transfers).

## Packet header (measured)

Offsets in bytes, all little-endian:

| off | size | meaning |
|-----|------|---------|
| 0   | 2    | `f0 02` magic (constant) |
| 2   | 2    | `01 01` = host->device, `01 81` = device->host (bit 7 = reply) |
| 4   | 4    | sequence counter; host increments per request, the reply echoes it (hypothesis: echo; the IN packet in frame #3 had 0x59 == the OUT in #1) |
| 8   | 8    | command as two fourcc's stored byte-reversed: OUT `PteG lppA` = "GetP" "Appl"; IN `ylpR lppA` = "Rply" "Appl" |
| 16  | 4    | zeros |
| 20  | 4    | `tSUQ` = "QUSt" (constant, meaning unknown) |
| 24  | 4    | `0x2dc` = 732 = 752 - 20 (payload length after a 20-byte prefix? hypothesis) |

OUT request `GetP Appl` ends at offset 26 (rest zero). It is the only command
seen so far: **no writes at all** in this capture.

## Reply body (IN, offsets from packet start)

- `28..35`: two float32, ~9e-6 — the only bytes that vary over time. Hypothesis:
  input peak meters (linear, silence ~ -100 dBFS). Needs a signal test.
- `312`: float -96.0, `316`: float -10.0, `324`: float -37.26 (unchanged all
  capture) — hypothesis: current parameter values / ranges (dB). Unknown which.
- `332`: u32 5, `344`: u32 75 (75 matches the ALSA MIDI/gain max of 75 dB).
- `348..359`: ASCII `v3.03.112204` — firmware version (bcdDevice is 3.03).
- Everything else up to offset 751 is zero in this capture.

## Next

The cold-start capture shows only the polling service; UC's real writes are
still missing. Need per-action captures (phantom, pad, gain, ...) per
`docs/capture-plan.md`, diffing the constant region of the IN reply and
looking for non-`GetP` commands on OUT. Tools: `tools/dump_bulk.py`,
`tools/cmd_stats.py`, `tools/in_diff.py`.
