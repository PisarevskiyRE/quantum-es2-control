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
| 0   | 2    | total message length: `f0 02` = 0x02f0 = 752 for polls, 0x28 = 40 for SetP, 8 for a bare ack (first `f0 02` is a length, not a magic) |
| 2   | 2    | `01 01` = host->device, `01 81` = device->host (bit 7 = reply) |
| 4   | 4    | sequence counter; host increments per request, the reply echoes it (hypothesis: echo; the IN packet in frame #3 had 0x59 == the OUT in #1) |
| 8   | 8    | command as two fourcc's stored byte-reversed: OUT `PteG lppA` = "GetP" "Appl"; IN `ylpR lppA` = "Rply" "Appl" |
| 16  | 4    | zeros |
| 20  | 4    | `tSUQ` = "QUSt" (constant, meaning unknown) |
| 24  | 4    | `0x2dc` = 732 = 752 - 20 (payload length after a 20-byte prefix? hypothesis) |

OUT request `GetP Appl` ends at offset 26 (rest zero). It is the only command
seen so far: **no writes at all** in this capture.

## SetP command (measured, `02-phantom-in1.pcapng`)

Phantom +48V on input 1 toggled on, off, on, off (4 SetP). Request, 40 bytes:

| off | size | value | meaning |
|-----|------|-------|---------|
| 0   | 2    | `28 00` | length 40 |
| 2   | 2    | `01 01` | request |
| 4   | 4    | seq | counter |
| 8   | 8    | `PteS lppA` | "SetP" "Appl" |
| 16  | 4    | 1 | unknown |
| 20  | 4    | `iraP` = "Pari" for int params (phantom), `araP` = "Para" for float params (gain) | value type tag; **verified**: wrong tag = ack but no effect |
| 24  | 4    | 0x14 (20) | hypothesis: parameter/group id |
| 28  | 4    | 0 | **channel index** (measured: input 1 -> 0, input 2 -> 1) |
| 32  | 4    | 0x0a (10) | hypothesis: parameter id (phantom?) |
| 36  | 4    | 1 = on, 0 = off | value (u32 LE, off = zeros) |

Device answers with an 8-byte ack: `08 00 01 81` + echoed seq (no data).
Right after, the normal `Rply` poll shows the new state at **offset 385**
(u8, 0 -> 1 for phantom on; reply grows from 360 to 386 significant bytes).
Input 2 (`02-phantom-in2.pcapng`) is identical except field 28 = 1, and its
state byte is at reply offset **404** = 385 + 19: per-input state blocks are
19 bytes apart (hypothesis: block 0 starts at 385 - k, phantom is byte k of it).
Still to separate: field 24 (=20) vs field 32 (=10) — group vs parameter id;
needs pad and gain captures.

## Parameters (measured, `03-panGain-in11.pcapng`)

SetP body from offset 24 is `[20, channel, param, value]`, u32 each. The value
is a u32 for switches and a float32 for gain.

| param | meaning | value | state in Rply (channel 0, +19 per channel) |
|-------|---------|-------|--------------------------------------------|
| 2  | input gain | float32 dB, 0..75, step 0.375 | float32 at 376 (ch1: 395) |
| 10 | +48V phantom | 0/1 | byte 385 (ch1: 404) |
| 4  | unknown switch (0/1) | 0/1 | byte 387 |
| 6  | unknown switch (0/1) | 0/1 | bytes 390 and 394 |
| 1  | unknown, sent to both channels at once (stereo link?) | 0/1 | bytes 389 and 408 (+ float at 395..398 changed) |

The per-channel state block is 19 bytes starting at offset 376: gain f32 at +0,
phantom at +9, param 4 at +11, param 1 at +13, param 6 at +14 and +18.
(Which UI buttons correspond to params 1, 4 and 6 is still to be confirmed.)

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

## Verified from Linux

`quantumcontrol/device.py` polls state and sets gain on the live device (host claims IF5 directly, VM must not hold the device). Gain 0 -> 1.5 -> 0 dB read back correctly on input 1. Phantom write not yet tested live (left off deliberately: phantom can damage some mics).
