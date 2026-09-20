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
| 16  | 4    | 1 = input section, **0 = output section** (`08-monitor-volume`) | target section |
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
| 4  | **low cut** (high-pass), confirmed by `04-lowcut-in1` | 0/1 | byte 387 |
| 6  | **auto gain** (one-shot start, `05-autogen-in1`) | 1 to start | bytes 390/394 = 1 while listening (~10 s), then 390 = 3, then both 0 (~3 s later); gain float updates if a signal is present (untested: no signal in capture) |
| 1  | **input stereo link** (inputs 1+2 as a pair, `07-stereolink-in12`); UC sends SetP to ch1 then ch0 | 0/1 | bytes 389 and 408 |

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

## Mixer table block (measured, `07-stereolink-in12.pcapng`, not needed for basic control)

Right after enabling/disabling stereo link, UC sends one 516-byte OUT (0x204)
with header `04 02 01 01`, seq, `PteS`, 8 zero bytes, tag `mrpm`, then a table of
records with float32 levels (-96.0 / -145.0 dB when linked, -99.0 when
unlinked). Presumably rewrites the internal mixer matrix for the new mode.
Not decoded; a GUI that only changes gain/+48V/low cut/auto gain does not need it.
It is unknown whether stereo link works from Linux without also sending it.

## Outputs (measured, `08-monitor-volume.pcapng`, live write from Linux NOT yet tested)

Same SetP layout with field 16 = 0. Monitor (main) volume: `[section 0] araP 20, index 0, param 2, float32 dB`,
swept -96.0 .. -4.7 dB in the capture. State in Rply: float32 at offset **312**
(was -96.0 at capture start). The two other floats that looked constant in the very first
capture (316 = -10.0, 324 = -96.0) are probably further output levels (phones?), unconfirmed.

Headphone volume (`09-phones-volume.pcapng`): section 0, index 0, **param 7**, float32 dB
(swept -96.0 .. -0.8). State: float32 at offset **324**. So 312 = monitor (param 2), 324 = phones
(param 7). Offset 316 (-10.0, never changed) is still unidentified.

## Main out volume (measured, `10-main-out-volume.pcapng`)

Not a 40-byte SetP: UC sends the 516-byte `mrpm` block (see "Mixer table block")
for every fader step (54 blocks in one sweep, each acked with 8 bytes). Header:
`04 02 01 01`, seq, `PteS`, 8 zero bytes, `mrpm`, u32 0x1f0, u32 0. Then records of
(u32 id, float32 value): ch0 ids at offsets 32.., ch1 records the same layout 48 bytes later.

One fader value `v` (dB, seen -27.55 .. +8.3) determines eight floats, verified on all 54 blocks:
`v` at offsets 52 and 108, `v-99` at 36, 44, 84, 92, `v-96` at 68 and 124. Every other byte of the
block was identical across the sweep, so the block can be replayed as a template with only those
eight floats replaced. The Rply poll has no readable state for main volume (only tiny meter-like
values at 172/176/276..288), so a client must remember the value itself.
Live write from Linux not tested; the template also encodes the current mixer setup (stereo link
changes the -96/-99 constants), so it should be captured from the same state it is replayed in.

## Input meters (offset 28 verified live on input 1; input 2 from captures only)

Rply float32 at offset **28** (input 1) and **32** (input 2): linear peak amplitude, dBFS = 20*log10(v).
Evidence: only offset 28 rises in the input-1 captures (0.0185 during phantom toggling, 0.274 during the
gain sweep) and only offset 32 in the input-2 phantom capture (0.0232); silence is ~1e-5 (about -100 dBFS).
Whether 1.0 is exactly full scale and whether the value is peak-since-last-poll is not verified.
The GUI shows them as bars with instant attack, 20 dB/s release and a CLIP flag at >= -0.5 dBFS.

## Naming vs the native app (from a local screenshot of the native app (not in the repo))

- Native "Main Out" knob (H/W Controls) = param 2, section 0, Rply float at 312 (-96 shown as "-oo dB").
- Native "Phones" knob = param 7, section 0, Rply float at 324.
- Native "Main L/R" fader = the 516-byte `mrpm` block (`10-main-out-volume`, ended at +0.48 dB, same as the screenshot).
- Still to capture (one file each): input fader (In 1), pan, M (mute), S (solo), strip link icon, Dim,
  main M (mute), the headphone button next to it, and whatever the gear/copy icons open.

## Mixer block `mrpm` decoded (`01-fader.pcapng` + `10-main-out-volume.pcapng`)

516 bytes: 32-byte header (`len 0x204`, `01 01`, seq, `PteS`, 0, 0, `mrpm`, 0x1f0, 0), then records of
(u32 key, float32 dB) from offset 32, zero padded, and the **record count as u32 at offset 512**.
Key = index | side << 24, side 0/1 = left/right, index 0/1 = input 1/2, 0x0a..0x0d = DAW returns.

- Input fader (In 1/2): UC sends only two records, (i, side 0) and (i, side 1), value =
  `fader + main + pan law`, fader -96..+10 dB, pan law -3 dB at centre (so pan is per-side, next capture).
- Main fader: UC resends all 12 records (both inputs' crosspoints plus DAW returns: L gets `v` on 0x0a and `v-96`
  on 0x0c, R gets `v` on 0x0b and `v-96` on 0x0d, the rest -145).
- Verified by regenerating all 54 main blocks and 66 fader blocks from this model: keys and floats identical.
  The mixer matrix is not readable, so the client keeps a local model (main = 0 dB, faders = -96 dB at start)
  and the real device state may differ until a control is moved. In the fader capture the main level was
  +0.48 dB (as on the native screenshot), which reproduces the -96.00 dB / +10.00 dB fader range exactly.

Confirmed by the user in the native app: Gain = preamp gain; the channel fader = send level of the input into the Main mix.

## Pan (measured, `01-pan.pcapng`)

Pan uses the same `mrpm` block. Constant-power law, `theta = (p+1)*pi/4` for p in -1 (left) .. +1 (right):
input's Main crosspoints `L = fader + main + 20*log10(cos theta)`, `R = fader + main + 20*log10(sin theta)`,
the opposite side is exactly -145 dB at the extremes (p = +-1.000 in the capture; centre = -3 dB each).
Over 71 blocks the model reproduces the captured values within 0.09 dB (assuming fader+main = +1.68 dB there).
UC also rewrites two send pairs (keys 0x000d0000/0x010d0000 and 0x000e0000/0x010e0000 for input 1) with value
`-96 + pan gain` (send fader at -96 = off); the client skips them and sends only the two Main crosspoints
(6 records vs 2). Input 2's send-pair keys are not captured.

## Mute / Solo (measured, `01-ms.pcapng`: mute on/off, then solo on/off, input 1)

Same `mrpm` block, no separate parameter.
- Mute in1: its six records (Main L/R + the two send pairs) all -145 dB; unmute writes the normal values back.
- Solo in1: 12 records; in1's Main crosspoints unchanged, input 2's crosspoints and all DAW returns (0x0a..0x0d)
  set to -145. Solo off resends the full block with the normal values (in2 = fader + main + pan, DAW = main /
  main-96 as in the main-fader block). From the restored values, main was +0.48 dB, in1 fader ~+1.2 dB.
- Client: mute sends only the input's two Main records; solo sends all 12 (`_send_full_mix`). Neither state is
  readable from the device.

## Stereo link (measured, `01-link.pcapng` + `07-stereolink-in12.pcapng`)

The strip's link icon is SetP param 1 (`[20, ch, 1, 0/1]`, channel 1 first, then channel 0), followed by a
12-record `mrpm` block. Link on: in1 -> Main L only and in2 -> Main R only (`f+main` = +1.68 dB, opposite
sides -145 dB), i.e. hard pan L/R, and input 2's fader takes input 1's value. Link off: both inputs centred
(`f+main-3` = -1.32 dB on every crosspoint). The block also carries the send pairs with keys
`input | bus << 16 | side << 24` (bus 0x0d / 0x0e; input 2 is `0x000d0001`), values `-96 + pan gain`
(-96/-145 linked, -99 unlinked); the client omits them and sends the four Main crosspoints. The link flag is
readable from Rply (bytes 389 / 408), so the GUI mirrors it.

## Dim and Mute of Main Out (measured, `01-dim.pcapng`, `01-M.pcapng`)

One enum parameter in the output section: `[section 0, tag iraP, 20, 0, param 0, mode]` with mode 0 = normal,
1 = Dim, 2 = Mute (mutually exclusive). State: byte at Rply offset **308** carries the same mode value. The amount
of attenuation is applied by the device (not visible on the wire).

## Main L/R meters (offsets 172 / 176, confirmed live)

Rply float32 at **172** (Main L) and **176** (Main R): linear level, dBFS = 20*log10(v), same scale as the input
meters at 28/32. Confirmed by the user: the bars react to music played from the computer. Offsets 276..288 (four
values, ~1e-9 at silence) are still unidentified (possibly headphone/monitor meters).
