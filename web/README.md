# GE100 Pro editor (web page)

A single page that talks to the pedal over USB through WebHID. It runs in **Microsoft Edge or Google Chrome** on
Windows 11, and later in Chromium on the Pi 5. Nothing to install.

What it does:

- reads the pedal like Mooer Studio does: firmware, all 150 preset names, the current preset
- select a preset; see its 10-slot signal chain
- per slot: switch on/off, step through models, turn the knobs (drag up/down, mouse wheel, arrow keys,
  double-click or Enter to type a value; hold Shift for fine steps)
- follows the pedal: presets, knobs and the cursor changed on the pedal show up in the page
- **Save** writes the current sound to the preset, only after you confirm; switching presets with unsaved changes asks
  first instead of saving
- *Show traffic* shows every message to and from the pedal

Not known yet, so shown as numbers: model names and knob names/ranges.

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
