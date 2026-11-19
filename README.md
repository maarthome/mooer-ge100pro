# mooer-ge100pro

Reverse-engineering the USB control protocol of the **Mooer GE100 Pro / GE100 Pro Li** (USB `34db:0011`), with a
Python library and a live decoder that runs on Linux (developed on a Raspberry Pi 5).

Unofficial: not affiliated with or endorsed by Mooer.

## Status

- **Working:** framing and CRC; decoding of the pedal's pushes and replies (state, chain slots, presets with their 10
  slots, preset names, device info); the read requests Mooer Studio sends at start-up (`python3 -m ge100pro.probe`);
  reading and filtering Wireshark/USBPcap captures. The command set belongs to the Prime M2 family.
- **Not yet:** commands that change the pedal (select preset, set a parameter, save). Sending is limited in code to the
  confirmed read requests.

Everything known so far, with what is verified and what is a guess: [PROTOCOL.md](PROTOCOL.md).

## Quick start (Linux)

Connect the pedal's **data** USB-C port. Allow access without root (members of `plugdev`, also over SSH):

```bash
sudo cp udev/70-mooer-ge100pro.rules /etc/udev/rules.d/
```

```bash
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Check that `/dev/hidrawN` now belongs to `plugdev` and that you are a member:

```bash
ls -l /dev/hidraw* && groups
```

If `plugdev` is missing from `groups`, add yourself and open a new login session:

```bash
sudo usermod -aG plugdev "$USER"
```

Run the live decoder from the repo folder (no install needed), then use the pedal:

```bash
PYTHONPATH=src python3 -m ge100pro
```

Read the pedal's state, all 150 preset names and the current preset, using only the read requests Mooer Studio uses
(close Mooer Studio first):

```bash
PYTHONPATH=src python3 -m ge100pro.probe
```

Decode a filtered Wireshark capture, both directions (see [captures/README.md](captures/README.md), raw captures also
contain your keyboard):

```bash
PYTHONPATH=src python3 -m ge100pro tests/fixtures/01_connect_ge100pro.pcapng
```

Decode a saved `xxd -c 64` dump of `/dev/hidrawN`:

```bash
PYTHONPATH=src python3 -m ge100pro tests/fixtures/capture1_xxd.txt
```

Or install it in a virtual environment, which also gives the `ge100pro-decode` command:

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
```

## Tests

The tests check the decoder against real GE100 Pro traffic in `tests/fixtures/`:

```bash
PYTHONPATH=src python3 -m pytest -q
```

## Layout

| Path | Contents |
|---|---|
| `src/ge100pro/crc.py` | CRC-16/GSM (from fingerskier/Mooer_GE150_Pro_Li-IO) |
| `src/ge100pro/framing.py` | `AA 55` frames, 64-byte report splitting, stream reassembly (adapted from the same project) |
| `src/ge100pro/messages.py` | decoders for the pedal's messages |
| `src/ge100pro/transport.py` | Linux hidraw connection; sends only confirmed read requests |
| `src/ge100pro/decode.py` | live / xxd / pcapng decoder (`python3 -m ge100pro`) |
| `src/ge100pro/pcapng.py` | USBPcap capture reader and filter (`python3 -m ge100pro.pcapng filter IN OUT`) |
| `src/ge100pro/probe.py` | read-only state/names/preset query (`python3 -m ge100pro.probe`) |
| `captures/` | raw captures still being analysed |
| `tests/fixtures/` | captures that back a verified fact |
| `udev/` | udev rule |

## Credits

`crc.py` and `framing.py` come from [fingerskier/Mooer_GE150_Pro_Li-IO](https://github.com/fingerskier/Mooer_GE150_Pro_Li-IO)
(MIT, see [NOTICE.md](NOTICE.md)). The protocol work builds on the published findings of the Mooer projects listed in
[PROTOCOL.md §6](PROTOCOL.md#6-related-projects), in particular the Prime M2 research by andymann.

## License

MIT, see [LICENSE](LICENSE).
