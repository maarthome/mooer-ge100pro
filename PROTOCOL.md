# Mooer GE100 Pro USB protocol notes

Unofficial, reverse-engineered from the pedal's own traffic. Not affiliated with or endorsed by Mooer.

Status markers: **[V]** = verified on a real GE100 Pro (captures in `tests/fixtures/`, checked by the tests);
**[H]** = hypothesis, consistent with what was seen but not proven; **[?]** = unknown.

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

Long messages (the 530-byte preset dump) continue over several reports. The padding after `n` is not zeroed: it holds
leftovers of earlier reports. 191 of 191 captured frames pass the CRC.

This framing is shared with other Mooer pedals (GE200, GE150 Pro, GE150 Max, Prime M2); see "Related projects".

## 3. Pedal → host messages

The pedal pushes these **without any handshake** as soon as something changes on it. [V]
Offsets are into the payload, **after** the command byte.

### `0x15` status (44-byte payload)

| Offset | Meaning | |
|---|---|---|
| 0 | current preset, 1…150 (wraps 150 → 1) | [V] |
| 2 | changed 81 → 90 while a control was turned on preset 61 (master/preset volume?) | [?] |
| rest | constant so far: `09 00 00 00 00 00 0c 00 15 00 01 00 01 00 … 20 00 00 00 20 00 00 00 20 … 32 00` | [?] |

Sent on every preset change.

### `0x32` preset dump (529-byte payload)

| Offset | Meaning | |
|---|---|---|
| 0 | preset number | [V] |
| 1–16 | preset name, ASCII, space/NUL padded ("Over My Head", "cl_brt_jc120") | [V] |
| 17… | block data, contains model names such as "1971 Fender Twin R" and "MEMORY" | [?] layout not mapped |

Sent when the pedal settles on a preset (not for every preset scrolled past).

### `0x27` block changed (51-byte payload)

| Offset | Meaning | |
|---|---|---|
| 0 | block index | [V] |
| 1 | always 1 so far | [?] |
| 3–4 | u16: 0 on one block, 7 on a delay | [H] model/effect type |
| 5 | on/off | [V] |
| 7–8 | u16: 0 on one block, 9 on a delay | [H] number of parameters |
| 9–30 | **11 parameter slots, u16 LE; knob N = slot N** | [V] for knobs 1–4 and 6 |
| 31–50 | 20-byte text, "MEMORY" so far | [?] capture/sample name |

The number of parameters depends on the model; unused slots read 0, but 0 is also a valid value.

Delay observed (preset 1, block 3) [V]: slot 3 = time in ms, slot 4 = subdivision, the pedal recalculates slot 3 from a
494 ms beat:

| slot 4 | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| slot 3 (ms) | 494 (free) | 494 (1/4) | 329 (1/4T) | 742 (1/4D) | 247 (1/8) | 165 (1/8T) |

Other delay slots: 14, 22, 51, **1201–1208 (knob 6)**, 494, 50 [?]. 1201–1208 might be a tempo in 0.1 BPM [H].

### `0x43` navigation (2-byte payload)

| Byte 0 | Seen when | |
|---|---|---|
| `05` | cursor moved to block `byte 1` | [V] |
| `22` | block opened / entered | [H] |
| `0a`, `0c`, `0d`, `21`, `06` | an edit page was shown; a full `0x27` for that block follows | [H] page or effect-type id |

Byte 1 = block index 0…3 [V].

## 4. Host → pedal commands

**None confirmed yet.** `transport.GE100Pro.send()` refuses every command until it is added to
`CONFIRMED_HOST_COMMANDS`.

Do not try opcodes from other Mooer models: on the GE150, `8B` and `BA` erase the pedal's memory and `B4 15` opens the
reset prompt; on the GE200, `E4` erases IR flash and `E5` overwrites a preset slot; on the Prime M2, `81` may zero a
preset. The same opcode can mean something different here.

The way forward is a Wireshark/USBPcap capture of Mooer Studio (`MS_For_GE100_Pro`) on Windows, filter:

```
usb.idVendor == 0x34db && (usb.endpoint_address == 0x05 || usb.endpoint_address == 0x85)
```

Capture, one step at a time: editor start-up (connect sequence), selecting a few presets, turning one knob, toggling one
block, changing one model, renaming a preset (without saving over anything important). Store captures in `captures/`.

## 5. Open questions

1. Host → pedal: connect sequence, select preset, set parameter, change model, save.
2. `0x15` offset 2 and the constant fields.
3. `0x27` offsets 1, 3–4 (model?), 7–8 (parameter count?) and the text field; why the first block showed 0 in both.
4. `0x32` layout after the name.
5. `0x43` page ids.
6. Is there a "reply = request + 1" convention as on the Prime M2?

## 6. Related projects

| Project | Model | Relation |
|---|---|---|
| [fingerskier/Mooer_GE150_Pro_Li-IO](https://github.com/fingerskier/Mooer_GE150_Pro_Li-IO) | GE150 Max, `34db:000f` | same transport (64-byte HID, `0x85`/`0x05`, `[n]` prefix); `crc.py` and `framing.py` here come from it |
| [andymann/mooer-prime-m2-app](https://github.com/andymann/mooer-prime-m2-app) | Prime M2, `34db:000d` | same framing, and the only documented model that also pushes `15` and `43` |
| [lucanenni/mooer-prime-m2-web](https://github.com/lucanenni/mooer-prime-m2-web) | Prime M2 | WebHID/BLE editor, protocol notes |
| [klaushofrichter/ge150pro-editor](https://github.com/klaushofrichter/ge150pro-editor) | GE150 Pro, `0483:5703` | same framing, different command set |
| [atahan26/ge200-editor](https://github.com/atahan26/ge200-editor) | GE200, `0483:5703` | same framing, different command set |
| [ThijsWithaar/MooerManager](https://github.com/ThijsWithaar/MooerManager) | GE200 | earliest public decoding (Wireshark dissector) |
