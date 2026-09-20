# Notes from the PreSonus manuals (docs/OM_*.pdf hardware, docs/UM_*.pdf Universal Control)

The PDFs are gitignored (vendor material). This file keeps what matters so they need not be reread.

## Hardware (Quantum ES 2)
- 2 MAX-HD mic preamps, gain 0..+75 dB; combo jacks. Front TS instrument input defeats back combo jack of ch 1.
- Line signal on the TRS side bypasses the preamp and the gain control becomes a **Line trim -12..+12 dB**.
  Auto Gain works for mic/guitar only, not line.
- 2 line outs (Main 1/2, DC coupled), 1 headphone out, 3.5 mm MIDI in/out, USB-C, aux power USB-C.
- Top panel: 48V button, Auto Gain, channel select buttons, clip LEDs (at -0.5 dBFS), multipurpose endless knob
  (modes: Main / Headphone / channel gain, gain mode times out after 10 s), Main button, Headphone button,
  Mute/Dim button (default mute; can be configured as dim in UC; **does not affect headphones**).
- Stereo link: hold odd channel button, press the next: settings of the left channel copied to the right (except
  pan), gain/48V changes then affect **both**, pan hard L/R; unlink returns pans to centre, gain stays.
- Auto Gain: 10 s listening, LED green x3 on success, red x3 on failure; can be cancelled.
- Recovery mode: hold the knob while powering on. Firmware update/revert only via UC (DFU interface IF6: out of scope).

## Universal Control mixer
- Navigation bar: Scenes panel, Settings panel, **mixer power button** (bypass mixer, e.g. to mix in a DAW).
- Input strip: HPF (80 Hz, 12 dB/oct), 48V, Autogain, Gain (0..75 dB) or Line level, double-click a value to type.
- Sends: per-channel send level to a Return (FlexChannel); Loopback 1/2 virtual outputs; Sends per output pair.
- Mix controls: Pan (also applies to Sends), Mute (also Sends), Solo (mutes all other channels in the Main mix),
  Mono/Stereo link, level value, pre-fader channel meter, fader, name/icon/colour.
- Returns: Return select, copy/paste mix, **Fader Flip** (fader edits per-channel send level), Mute, **Phones Listen**
  (route the selected mix to headphones), mono/stereo toggle, meter, fader.
- Monitor strip: Main Out level (same as knob), Headphone level, **Dim (amount in Settings, default -10 dB)**,
  Speaker Switching (ES 4 only, greyed on ES 2), **Mute Main (not headphones)**, **Phones Listen (Main mix -> HP 1)**,
  Monitor meters (pre monitor level), Main fader (independent of the encoder; fader down = nothing reaches the knob).
- Scenes: snapshot of all channel parameters, fader positions, aux mixes, mutes, solos; stored as files on the PC
  (Save/Load/Store/Delete). A local implementation is possible.
- Settings panel, hardware: Main Encoder (None / 1-2; None mutes Main 1/2), Speaker Switching, **HP Source**,
  **Mute Button Behavior** (mute or dim), **Dim Amount**, **LED Brightness** (default 100 %), **Factory Reset**.
  UI: Colorize Channels, Peak Hold, Show all Loopback, Edit Popup, Meter Decay (slow/medium/fast).
- Persistence (UM 3.2.2): Main-mix settings (channel volume, pan, solo, mute, stereo link) and monitor levels are
  saved to firmware (up to ~10 s after a change) and recalled at power-on. => the device knows the mixer state, so
  a read-back command probably exists (not yet seen on the wire).
- Loopback inputs are disabled at 176.4 and 192 kHz.

## Not applicable to ES 2
Speaker switching, multichannel "All" mode, second headphone, Fender Studio Pro remote control, mobile setup.
