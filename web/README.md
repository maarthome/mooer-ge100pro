# GE100 Pro editor (web page)

A single page that talks to the pedal over USB through WebHID. It runs in **Microsoft Edge or Google Chrome** on
Windows 11, and later in Chromium on the Pi 5. Nothing to install.

What it does:

- reads the pedal like Mooer Studio does: firmware, all 150 preset names, the current preset
- select a preset; see its 10-slot signal chain
- switch a block on/off with the light on its card, or in the editor
- move a block: drag its card to another place in the chain
- per slot: pick the model from a drop-down, turn the knobs (drag up/down, mouse wheel, arrow keys,
  double-click or Enter to type a value; hold Shift for fine steps); delay sub-divisions are drop-downs
- Settings (saved in this browser): five text sizes (parameter names in the editor, block names and group names in
  the chain, the editor heading, all other text), colours, and a colour per effect group
- follows the pedal: presets, knobs and the cursor changed on the pedal show up in the page
- **Save** writes the current sound to the preset, only after you confirm; switching presets with unsaved changes
  (knobs, on/off, models, moved blocks) asks: Cancel, Don't save, or Save first
- *Show traffic* shows every message to and from the pedal

Presets are numbered as on the pedal (01A … 50C), models as on the pedal's screen ("01 | 65 US DX"), knobs with their
names and units (GAIN, Time A 222 ms, HIGH CUT 12060 Hz, 750Hz −2 dB, Sub-D 1/8T …), and the user capture/IR slots
with the names of your captures, read from the pedal.

## Run it

1. Plug the pedal's **data** USB-C port into the computer.
2. **Close Mooer Studio**: only one program can use the pedal at a time.
3. Open `web/index.html` in Edge or Chrome (double-click it, or drag it into the browser).
4. Click **Connect pedal** and choose the GE100 Pro.

If the browser refuses to open the file directly, serve the folder and open http://localhost:8000:

```bash
python -m http.server 8000 -d web
```

On Linux (the Pi), Chromium needs the udev rule from `udev/` for access to the pedal, as described in the main README.

## Files

| File | Contents |
|---|---|
| `index.html` | the editor |
| `protocol.js` | framing, CRC and message decoding (port of `src/ge100pro`), tested by `tests/test_web_protocol.py` |
| `models.js` | model names, generated from `src/ge100pro/models.json` by `tools/gen_models_js.py` |
