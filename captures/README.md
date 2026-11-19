# Captures

**Raw Wireshark/USBPcap captures record every USB device on the same root hub, including your keyboard and mouse.
Typed keys can be read back from them. Never commit or share a raw capture: filter it first.**

1. Put raw captures in `captures/raw/` (git-ignored).
2. Filter, which keeps only the GE100 Pro's packets and drops host/OS strings:

   ```bash
   PYTHONPATH=src python3 -m ge100pro.pcapng filter captures/raw/02_select_preset.pcapng captures/02_select_preset.pcapng
   ```

3. Decode the filtered file (both directions, with timestamps):

   ```bash
   PYTHONPATH=src python3 -m ge100pro captures/02_select_preset.pcapng
   ```

Pedal pushes on Linux can be saved directly, they contain only the pedal:

```bash
cat /dev/hidraw0 | xxd -c 64 > captures/NAME.txt
```

Keep a short note with each capture of what was done while recording. Once a capture has confirmed something, copy it
to `tests/fixtures/` and add a test for it.
