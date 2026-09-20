# Capture session log

One entry per capture file. Fill in as you go through `docs/capture-plan.md`.

| file | action taken | exact value (if applicable) | timestamp | notes |
|------|--------------|------------------------------|-----------|-------|
| 02-phantom-in1.pcapng | +48V input 1: on, off, on, off | n/a | 2026-09-20 ~14:55 | 4 SetP seen, state byte at reply offset 385 |
| 02-phantom-in2.pcapng | +48V input 2: on, off, on, off | n/a | 2026-09-20 | field 28 = 1, state byte at reply offset 404 |
| 03-panGain-in11.pcapng | sweep gain, then pressed various buttons (unlogged order) | gain 0..~70 dB | 2026-09-20 | params 2, 4, 6, 10, 1 seen; 03-panGain-in1 had no writes |
| 04-lowcut-in1.pcapng | low cut button input 1: on, off, on, off | n/a | 2026-09-20 | param 4 confirmed, state byte 387 |
| 05-autogen-in1.pcapng | auto gain input 1, once, no signal | n/a | 2026-09-20 | param 6; state bytes 390/394 |
| 06-gain-in1-repeat.pcapng | gain sweep input 1 | 0..64.5 dB | 2026-09-20 | only param 2, nothing new |
| 07-stereolink-in12.pcapng | stereo/mono link inputs 1-2: on, off | n/a | 2026-09-20 | param 1 on ch0+ch1, then 516-byte mprm block |
| 08-monitor-volume.pcapng | monitor volume sweep | -96..-4.7 dB | 2026-09-20 | section 0 (outputs), param 2, state float at 312 |
| 09-phones-volume.pcapng | phones volume sweep | -96..-0.8 dB | 2026-09-20 | section 0, param 7, state float at 324 |
| 10-main-out-volume.pcapng | main out fader sweep | -27.55..+8.3 dB | 2026-09-20 | 516-byte mrpm block, 8 floats derived from one fader value |
| 01-fader.pcapng | input 1 fader sweep | -96..+10 dB | 2026-09-20 | 2-record mrpm block, main assumed +0.48 |
| 01-ms.pcapng | in1 mute on/off, then solo on/off | n/a | 2026-09-20 | mrpm blocks: 6 records for mute, 12 for solo |
| 01-link.pcapng | stereo link icon on/off | n/a | 2026-09-20 | param 1 + 12-record mrpm |
