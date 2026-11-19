# Mooer GE100 Pro USB protocol notes

Unofficial, reverse-engineered from the pedal's own traffic and from Mooer Studio talking to it. Not affiliated with or
endorsed by Mooer.

Status markers: **[V]** = verified on a real GE100 Pro (captures in `tests/fixtures/`, checked by the tests);
**[H]** = hypothesis, consistent with what was seen but not proven; **[?]** = unknown.

Captures so far:

| Fixture | What | Firmware |
|---|---|---|
| `capture1_xxd.txt` | pedal pushes on Linux (`cat /dev/hidraw0`): presets scrolled, a block toggled, knobs turned | V1.3.3 |
| `01_connect_ge100pro.pcapng` | Mooer Studio (Windows) starting up and reading the pedal; filtered to the pedal only | V1.3.3 |

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
| `29` | first, last (1…150) | `2a` | preset names; Mooer Studio asks 30 at a time: 1–30, 31–60, … 121–150 |
| `2b` | — | `2c` | 299 bytes, all `01` on this pedal [?] (on the M2: per-category availability / DSP budget) |
| `31` | — | `32`, then `43 05 00` | the current preset (edit buffer?) |

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

Effect types seen (names where the parameter count and values fit the Prime M2's types) [H]:

| Type | Seen as | Parameters seen |
|---|---|---|
| 0 | slot 3 in preset 61 | 4 × ~50 |
| 1 | DRIVE (model 21) | 100, 10 (Gain, Tone? …) |
| 2 | AMP (model 27) | 6: 70, 57, 48, 26, 25, 75 (Gain, Bass, Mid, Treble, Presence, Master) |
| 3 | CAB (model 42), slot 9 | 0, 7941, 23 |
| 4 | DYNA (model 1) | 4: 30, 85, 30, 50 (Attack, Ratio, Threshold, Level?) |
| 5 | EQ-like (model 2) | 5 × ~16 (band gains around a centre of 16?) |
| 7 | DELAY (models 8, 9) | see below |
| 8 | REVERB (model 1) | 4: 0, 21, 50, 35 (Pre Delay, Level, Decay, Tone, as on the M2) |

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
| `0a`, `0c`, `0d`, `21`, `06` | an edit page was shown; a full `27` for that slot follows | [H] page or effect-type id |

### `49` (6 bytes)

`00 00 0f 05 56 00` after every `12` [V]. Meaning [?] (0x0f05 = 3845? 0x56 = 86?).

## 5. Commands that change the pedal

**None confirmed yet.** `transport.GE100Pro.send()` only allows the read requests of §3.

Do not try opcodes from other Mooer models: on the GE150, `8B` and `BA` erase the pedal's memory and `B4 15` opens the
reset prompt; on the GE200, `E4` erases IR flash and `E5` overwrites a preset slot; on the Prime M2, `81` may zero a
preset and `a1` is a factory reset. The Prime M2's write commands (`13` select preset by writing the state, `25` set a
slot, `2d` add/change/delete a slot, `2f` save) are the obvious candidates here, but they must be confirmed from a
capture of Mooer Studio before anything sends them.

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

Next captures, one action each: select presets 1, 2, 3 in the editor; turn one knob; switch one slot off/on; change a
model; then the same actions on the pedal with the editor open. No saving, renaming, uploads or resets yet.

## 7. Open questions

1. The write commands: select preset, set a parameter, slot on/off, change a model, save (§5).
2. `12`/`15` offset 2 and the constant fields; `49`; `2c`.
3. Slot record word 0 and the text field; the full effect type and model tables.
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
