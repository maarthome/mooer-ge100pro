# Mooer GE100 Pro USB protocol notes

Unofficial, reverse-engineered from the pedal's own traffic and from Mooer Studio talking to it. Not affiliated with or
endorsed by Mooer.

Status markers: **[V]** = verified on a real GE100 Pro (captures in `tests/fixtures/`, checked by the tests);
**[H]** = hypothesis, consistent with what was seen but not proven; **[?]** = unknown.

Captures so far:

| Fixture | What | Firmware |
|---|---|---|
| `capture1_xxd.txt` | pedal pushes on Linux (`cat /dev/hidraw0`): presets scrolled, a block toggled, knobs turned | V1.3.3 |
| `01_connect_ge100pro.pcapng` | Mooer Studio (Windows) starting up and reading the pedal | V1.3.3 |
| `02_select_preset.pcapng` | Mooer Studio: select presets 1, 4, 7 | V1.3.3 |
| `03_knob.pcapng` | Mooer Studio: one knob (amp, knob 2) swept 39 → 0 → 100 | V1.3.3 |
| `04_toggle_block.pcapng` | Mooer Studio: two slots switched off and on | V1.3.3 |
| `05_change_model.pcapng` | Mooer Studio: delay model changed four times | V1.3.3 |
| `06_pedal_side.pcapng` | Mooer Studio **saves preset 6** and selects preset 10; then a knob turned on the pedal | V1.3.3 |

All `.pcapng` fixtures are filtered to the pedal only (see §6).

## 1. USB device [V]

| | |
|---|---|
| VID:PID | `34db:0011`, manufacturer string "NXP SEMICONDUCTORS", product "GE100Pro" |
| Interfaces | 0 = Audio Control, 1 = Audio Streaming IN (pedal → host), 2 = Audio Streaming OUT, **3 = HID (control)** |
| HID endpoints | `0x85` IN / `0x05` OUT, interrupt, 64 bytes, 125 µs |
| HID report descriptor | Generic Desktop, 64 × 8-bit Input + 64 × 8-bit Output, **no report ID** |
| Audio | 44.1 kHz, 24-bit stereo (IN endpoint `0x83`, 270 bytes = 45 frames), async feedback on `0x82` |

Use the **data** USB-C port; the other one is power only. On Linux the HID interface binds to `usbhid` and appears as
`/dev/hidrawN` (`udev/70-mooer-ge100pro.rules` gives non-root access).

On Linux, reads from `/dev/hidrawN` return the 64-byte report. Writes must be 65 bytes: `0x00` (no report ID) + the
64-byte report.

## 2. Framing [V]

```
HID report (64 B):  [n] [n bytes of the message stream] [stale bytes, ignore]      n <= 63
Message:            AA 55 | len (u16 LE) | cmd | payload | CRC16 (u16 BE)          len = 1 + payload length
CRC16:              CRC-16/GSM: poly 0x1021, init 0x0000, not reflected, xorout 0xFFFF,
                    over the len field + cmd + payload (not over AA 55)
```

Both directions use the same framing [V: Mooer Studio's requests use it too]. Long messages (preset dumps, name
lists) continue over several reports. The padding after `n` is not zeroed: it holds leftovers of earlier reports.
All captured frames pass the CRC.

## 3. Command set: Prime M2 family [V]

**A reply's command is the request's command + 1** (`01`→`02`, `11`→`12`, `29`→`2a`, `2b`→`2c`, `31`→`32`). The
request numbers match the Mooer Prime M2 (`01` device info, `11` state, `29` names, `2b` availability), so the GE100 Pro
belongs to the same command family as the M2 (see §8), although its records differ.

### Requests seen from Mooer Studio (host → pedal), all read-only [V]

| Request | Payload | Reply | Meaning |
|---|---|---|---|
| `01` | `00` | `02` | device info |
| `11` | — | `12`, then `49` | global state |
| `21` | preset (u16) | `22` | a preset, same layout as `32`. Sent 1 ms after a `13` it returns the new number and name but the **previous** preset's slots: wait for the pedal's own `32` push (≈300 ms) instead [V] |
| `29` | first, last (1…150) | `2a` | preset names; Mooer Studio asks 30 at a time: 1–30, 31–60, … 121–150 |
| `2b` | — | `2c` | 299 bytes, all `01` on this pedal [?] (on the M2: per-category availability / DSP budget) |
| `31` | — | `32`, then `43 05 00` | the current preset (edit buffer?) |
| `65` | type, first (u16), last (u16) | `66` | user capture list; Mooer Studio asks `02 0001 0014`: the 20 amp capture slots |

Connect sequence of Mooer Studio V1.3.3: `11`, `11`, `2b`, (0.5 s) `11`, (0.5 s) `01 00`, `11`, `29 01 1e`, `29 1f 3c`,
`29 3d 5a`, `29 5b 78`, `29 79 96`, `31`, `31`, then the same again from `11`/`2b`. It does not wait for a reply
before the next request. No request in this sequence changes the pedal.

### Pushed by the pedal on its own [V]

No handshake is needed: the pedal sends these as soon as something changes on it.

| Command | When |
|---|---|
| `15` | preset changed or a global value changed (same layout as `12`) |
| `27` | a chain slot changed: knob turned, slot switched on/off |
| `32` | a preset was selected on the pedal (same layout as the reply to `31`) |
| `43` | cursor or page change on the pedal's screen |

## 4. Messages

Offsets are into the payload, **after** the command byte. Multi-byte values are little-endian.

### `02` device info (45 bytes) [V]

| Offset | Meaning | |
|---|---|---|
| 0–31 | name, NUL padded: `GE100PRO` | [V] |
| 32–38 | firmware: `V1.3.3`, NUL terminated | [V] |
| 39–44 | `41 00 96 14 14 0a`: 0x96 = 150 = number of presets? 0x14 = 20, 0x14 = 20, 0x0a = 10 = capture slots (20 amp, 10 drive per the specs)? | [H] |

### `12` / `15` state (44 bytes)

| Offset | Meaning | |
|---|---|---|
| 0 | current preset, 1…150 (wraps 150 → 1) | [V] |
| 2 | 81…90 and 94 seen; changed while a control was turned (master or preset volume?) | [?] |
| rest | constant so far: `09 00 00 00 00 00 0c 00 15 00 01 00 01 00 … 20 00 00 00 20 00 00 00 20 … 32 00` | [?] |

### `2a` preset names [V]

`first, last, then (last − first + 1) × 16-byte names` (NUL or space padded). Unused slots are named `EMPTY`.
150 presets.

### `32` preset (529 bytes) [V layout]

| Offset | Size | Meaning | |
|---|---|---|---|
| 0 | 1 | preset number | [V] |
| 1 | 16 | name | [V] |
| 17 | 10 × 50 | **10 chain slots**, record layout below | [V] |
| 517 | 12 | `00 00 00 00 00 00 01 00 00 00 64 00` (preset level 100?) | [?] |

The chain has 10 positions. In preset 82 slots 0–5 and 9 are used, 6–8 empty (all zeros) [V]; the cab sat in slot 9
[V], whether the cab is always last is [?].

### Chain slot record (50 bytes), also the body of `27`

| Offset | Meaning | |
|---|---|---|
| 0 | u16: 1 = slot in use, 0 = empty | [H] |
| 2 | u16: **effect type** (category), table below | [H] (7 = delay [V]) |
| 4 | u16: on/off | [V] |
| 6 | u16: **model** within the type | [H] |
| 8 | 11 × u16: **parameters**, knob N = parameter N | [V] for knobs 1–4 and 6 |
| 30 | 20 bytes text, `MEMORY` in every used slot so far | [?] capture/IR name? |

`27` = `slot index (1 byte)` + this 50-byte record [V].

**Effect types and models.** The type number is the category, the model number the 0-based position in that
category's list: model 0 is shown on the pedal as `01`. All names and knobs are in `src/ge100pro/models.json`:

- **Model names** as the pedal shows them: the `NN:NAME` strings in the GE100 Pro firmware (`GE100PRO.mr`, which ships
  with Mooer Studio), e.g. `01:65 US DX`, `09:DUAL DELAY`, `15:INTER REDUCER` (sic). [V]
- **Knob names, ranges and value encodings**: Mooer Studio for GE100 Pro V1.3.3 has them built in (its effect tables);
  the pedal does not send them. Every slot record of the captures decodes sensibly with them. [V]

| Type | Category | Models | Knobs (examples) |
|---|---|---|---|
| 0 | Pre FX (wah, compressors, limiter, reducer) | 15 | CRY WAH: Q, Position, Peak, Level |
| 1 | Drive | 35 + 10 user captures (36–45) | Volume, Tone, Gain |
| 2 | Amp | 72 + 20 user captures (73–92) | GAIN, BASS, MID, TREBLE, PRES, MST |
| 3 | Cab | 67 + 20 user IRs (68–87) | LOW CUT, HIGH CUT, ROOM |
| 4 | Noise reduction | 3 | NOISE KILLER: THRES; INTEL REDUCER: SENS; NOISE GATE: ATTACK, RELEASE, THRES |
| 5 | EQ | 6 | MOOER HM: 80Hz, 240Hz, 750Hz, 2.2KHz, 6.6KHz; CUSTOM EQ: Gain/Freq × 3 |
| 6 | Modulation | 27 | PHASER: Rate, Level, Depth; PITCH SHIFT: Pitch, Mix, Tone |
| 7 | Delay | 12 | DIGITAL: Level, Feedback, Time, Sub-D; DUAL DELAY: Time A/B, Sub A/B |
| 8 | Reverb | 9 | Pre Delay, Level, Decay, Tone (SHIMMER: + Shimmer) |

**Value encodings** (stored u16 → shown value), from Mooer Studio's conversion code:

| Kind | Shown as | Example |
|---|---|---|
| plain (most knobs) | the stored value, 0–100 | GAIN 70 |
| dB | stored + min | EQ −16…+16 dB: stored 16 = 0 dB, 14 = −2 dB |
| pitch | min + stored / 10 | PITCH SHIFT −12…+12: stored 0…240 |
| time | ms as stored | delay Time 40…2500, reverb Pre Delay 0…500 |
| Hz | Hz as stored | CUSTOM EQ Freq 0…18000 |
| range | min + stored | SWEEP Range 300…4000 |
| sub-division | index into `OFF, 1/4, 1/4T, 1/4D, 1/8, 1/8T, 1/8D, 1/16, 1/16T, 1/16D` | matches the measured 494/329/742/247/165 ms |
| cab LOW CUT | 0 = OFF, else 20 + (stored − 1) Hz | |
| cab HIGH CUT | 0 = OFF, 1 = 20000 Hz, else 20000 − (stored − 1) Hz | stored 7941 = 12060 Hz |

Knob N of a model is slot parameter N. Parameters after the model's last knob are not used (the pedal sometimes keeps
old values there).

**Preset numbering on the pedal:** 50 banks of 3: preset 1 = `01A`, 2 = `01B`, 3 = `01C`, 4 = `02A` … 150 = `50C`.

Delay, observed on the pedal (preset 1, slot 3, model 9) [V]: parameter 3 = time in ms, parameter 4 = subdivision; the
pedal recalculates the time from a 494 ms beat:

| parameter 4 | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| parameter 3 (ms) | 494 (free) | 494 (1/4) | 329 (1/4T) | 742 (1/4D) | 247 (1/8) | 165 (1/8T) |

Other delay parameters: 14, 22, 51, **1201–1208 (knob 6)**, 494, 50 [?]. 1201–1208 might be a tempo in 0.1 BPM [H].
Note: the Prime M2 encodes a synced delay time as `0x8000 | index` instead; the GE100 Pro uses a separate parameter.

### `43` navigation (2 bytes)

| Byte 0 | Seen when | |
|---|---|---|
| `05` | cursor on slot `byte 1`; also sent after every `32` reply | [V] |
| `22` | slot opened / entered | [H] |
| `06` + type (`06`, `08`, `0a`, `0c`, `0d`) | that slot's edit page is shown (also the echo of the host's `41`) | [V] |
| `21` | another page | [?] |

### `49` (6 bytes)

`00 00 0f 05 56 00` after every `12` [V]. Meaning [?] (0x0f05 = 3845? 0x56 = 86?).

### `66` user capture list [V for type 2]

Entries of 29 bytes: `type, index (u16), used (1/0), flag (2 if used), name (24 bytes)`. Type 2 = the 20 user amp
slots, which are amp models 73–92; in this pedal 1–4 hold NAM/MNRS captures ("ReverPlex CLN 1_z2", "Clean_9b5eltcb",
…). The same request with another type byte (`python -m ge100pro.lists --yes`, 2026-11-19) [V]:

| Type | Reply |
|---|---|
| 1 drive | 20 entries: user drive captures, here "1971 Fender Twin R", "Bogie412CB65_CG_16" (drive models 36–45; the specs and the device info say 10 slots) |
| 2 amp | 20 entries: user amp captures (amp models 73–92) |
| 3 cab | 20 entries: user IR slots (cab models 68–87), all empty here |
| 0, 4–8 | `66` with an empty payload |

**The pedal does not send factory model names**: those come from the manual (`models.json`). The 20-byte text field
of a slot record holds the name of the capture in use ("1971 Fender Twin R" appeared there) or `MEMORY`.

## 5. Commands that change the pedal

Seen from Mooer Studio on the wire [V]. **This code never sends them**: `transport.GE100Pro.send()` only allows the
read requests of §3. Each is acknowledged with `request + 1` and payload `01`.

| Command | Payload | Ack | Effect |
|---|---|---|---|
| `13` | the 44-byte state from `12`, with byte 0 = new preset | `14 01` | **selects a preset** (exactly the Prime M2 method: read the state, change the preset byte, write it all back). The pedal then pushes `32` with the new preset ≈300 ms later |
| `25` | slot index + the full 50-byte slot record | `26 01` | **live edit of one slot**: knob values, on/off, model. Mooer Studio streams one `25` every ≈20 ms while a knob is dragged. Not stored until saved |
| `41` | page, slot | `42 01` | pedal shows the edit page of that slot; **page = 6 + slot type** (amp 2 → `08`, dyna 4 → `0a`, delay 7 → `0d`; `06` and `0c` seen for types 0 and 6). The pedal echoes it as `43 page slot` |
| `2f` | preset, 16-byte name | `30 01` | **saves the edit buffer to that preset slot, permanently** (Prime M2: `2f pp name[20]`) |
| `2d` | id, operation, args | `2e id ok` | **edits the chain** (edit buffer): 1 = add `pos type model`, 2 = change `pos type model`, 3 = delete `pos`, 4 = move `from to` (take the block out, insert it at `to`; the blocks in between shift). From Mooer Studio for GE100 Pro's code (`dragEffectChain`), same as the Prime M2's `2d`; the editor uses *add*, *delete* and *move*. On the Prime M2 the pedal ignores requests for about 200 ms after an add or delete ([lucanenni/mooer-prime-m2-web](https://github.com/lucanenni/mooer-prime-m2-web)); the editor sends nothing for 300 ms after any `2d`. **Not yet seen in a capture**: unknown whether add/delete shift the other slots on the GE100 Pro |

Details [V]:
- `25` records sent by Mooer Studio carry `1` in parameter 11; the pedal's own records have `0` there [?].
- Model change: Mooer Studio sends `25` with the new model and that model's values; the pedal confirms with a `27`
  push carrying the model and its parameters (delay: parameter 7 = 500 = parameter 3).
- A save happened in capture 06 when the editor left a preset with unsaved edits: Mooer Studio sends `2f` **before**
  selecting the next preset. Preset 6 was stored with its edited delay (model 4, switched off).


Do not try opcodes from other Mooer models: on the GE150, `8B` and `BA` erase the pedal's memory and `B4 15` opens the
reset prompt; on the GE200, `E4` erases IR flash and `E5` overwrites a preset slot; on the Prime M2, `81` may zero a
preset and `a1` is a factory reset. Still to capture: adding, removing and moving slots (Prime M2: `2d`), renaming,
captures/IR upload.

## 6. Capturing Mooer Studio

Wireshark with USBPcap on Windows, Mooer Studio `MS_For_GE100_Pro`.

**USBPcap records every device on the same root hub, including keyboards and mice: typed keys can be read back from a
raw capture.** In the USBPcap interface options, select only the GE100 Pro if possible, don't type anything sensitive
while capturing, and always filter before sharing or committing:

```
python3 -m ge100pro.pcapng filter captures/raw/IN.pcapng captures/OUT.pcapng
```

`captures/raw/` is git-ignored. Decode a filtered capture, both directions with timestamps:

```
python3 -m ge100pro captures/OUT.pcapng
```

**When Mooer Studio asks to save changes while you capture, answer No**: it sends `2f` and stores the edit buffer.

## 7. Open questions

1. Add / remove / move slots, rename, upload; what `2c` (availability) means.
2. `12`/`15` offset 2 and the constant fields; `49`; `2c`.
3. Slot record word 0 and the text field.
4. Preset dump tail (12 bytes).
5. `43` page ids.

## 8. Related projects

| Project | Model | Relation |
|---|---|---|
| [andymann/mooer-prime-m2-app](https://github.com/andymann/mooer-prime-m2-app) | Prime M2, `34db:000d` | **same command family** (`01`, `11`, `29`, `2b`, reply = request + 1), same framing, pushes `15` and `43` |
| [lucanenni/mooer-prime-m2-web](https://github.com/lucanenni/mooer-prime-m2-web) | Prime M2 | WebHID/BLE editor, protocol notes |
| [fingerskier/Mooer_GE150_Pro_Li-IO](https://github.com/fingerskier/Mooer_GE150_Pro_Li-IO) | GE150 Max, `34db:000f` | same transport (64-byte HID, `0x85`/`0x05`, `[n]` prefix); `crc.py` and `framing.py` here come from it |
| [klaushofrichter/ge150pro-editor](https://github.com/klaushofrichter/ge150pro-editor) | GE150 Pro, `0483:5703` | same framing, different command set |
| [atahan26/ge200-editor](https://github.com/atahan26/ge200-editor) | GE200, `0483:5703` | same framing, different command set |
| [ThijsWithaar/MooerManager](https://github.com/ThijsWithaar/MooerManager) | GE200 | earliest public decoding (Wireshark dissector) |
