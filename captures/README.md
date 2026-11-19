# Captures

Put raw captures here, one action per file where possible, with a short note of what was done on the pedal or in the
editor while recording.

- Pedal pushes on Linux: `sudo cat /dev/hidraw0 | xxd -c 64 > captures/<name>.txt`
- Mooer Studio traffic on Windows: Wireshark + USBPcap, saved as `captures/<name>.pcapng`, filter in PROTOCOL.md §4.

Once a capture has confirmed something, copy it to `tests/fixtures/` and add a test for it.
