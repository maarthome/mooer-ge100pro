"""Connection to the GE100 Pro (34db:0011, HID interface 3) on Linux (hidraw) and Windows (hid.dll).

The pedal pushes its changes without any handshake. Sending is limited to the read requests
Mooer Studio itself sends to this pedal (captured on the wire, see PROTOCOL.md); everything
else is refused, because other Mooer models have commands that erase memory and the same
opcode can mean something else on this pedal.

Only one program can use the control channel at a time: close Mooer Studio first.
"""

from __future__ import annotations

import glob
import os
import select
import sys

from .framing import HID_REPORT_SIZE, Deframer, Frame, build_reports

VENDOR_ID = 0x34DB
PRODUCT_ID = 0x0011

#: Host -> pedal commands confirmed on the GE100 Pro: only read requests seen from Mooer Studio.
#: Commands that change the pedal (13 select, 25 set slot, 2f save, 41 open page) are NOT listed.
CONFIRMED_HOST_COMMANDS: set[int] = {0x01, 0x11, 0x21, 0x29, 0x2B, 0x31, 0x65}


def find_hidraw(vendor_id: int = VENDOR_ID, product_id: int = PRODUCT_ID) -> str | None:
    """Linux: return the /dev/hidrawN node of the pedal, or None."""
    wanted = f"HID_ID=0003:{vendor_id:08X}:{product_id:08X}"
    for uevent in sorted(glob.glob("/sys/class/hidraw/hidraw*/device/uevent")):
        with open(uevent) as f:
            if wanted in f.read():
                return "/dev/" + uevent.split("/")[4]
    return None


class _HidrawBackend:
    """Linux /dev/hidrawN: reads return the 64-byte report; writes need a leading 0x00."""

    def __init__(self, path: str | None) -> None:
        self.path = path or find_hidraw()
        if not self.path:
            raise FileNotFoundError("GE100 Pro (34db:0011) not found; is it plugged into the data port?")
        try:
            self._fd = os.open(self.path, os.O_RDWR)
        except PermissionError as e:
            raise PermissionError(
                f"no access to {self.path}: install udev/70-mooer-ge100pro.rules and make sure "
                "you are in the plugdev group (see README, Quick start)"
            ) from e

    def read_report(self, timeout_ms: int | None) -> bytes | None:
        if timeout_ms is not None and not select.select([self._fd], [], [], timeout_ms / 1000)[0]:
            return None
        return os.read(self._fd, HID_REPORT_SIZE)

    def write_report(self, report: bytes) -> None:
        os.write(self._fd, b"\x00" + report)

    def close(self) -> None:
        os.close(self._fd)


class _WindowsBackend:
    """Windows hid.dll via ctypes (see hid_win.py)."""

    def __init__(self, path: str | None) -> None:
        from .hid_win import HidDevice

        self._dev = HidDevice(path)
        self.path = self._dev.path

    def read_report(self, timeout_ms: int | None) -> bytes | None:
        if timeout_ms is not None:
            return self._dev.read_report(timeout_ms)
        while True:  # short waits so Ctrl+C keeps working
            report = self._dev.read_report(200)
            if report is not None:
                return report

    def write_report(self, report: bytes) -> None:
        self._dev.write_report(report)

    def close(self) -> None:
        self._dev.close()


class GE100Pro:
    """Iterate over the pedal's frames and send confirmed read requests."""

    def __init__(self, path: str | None = None) -> None:
        self._io = _WindowsBackend(path) if sys.platform == "win32" else _HidrawBackend(path)
        self.path = self._io.path
        self._deframer = Deframer()

    def close(self) -> None:
        self._io.close()

    def __enter__(self) -> "GE100Pro":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def frames(self):
        """Yield frames forever."""
        while True:
            report = self._io.read_report(None)
            if report:
                yield from self._deframer.feed(report)

    def read_frames(self, timeout: float = 0.5) -> list[Frame]:
        """Read whatever arrives until `timeout` seconds pass without a new report."""
        frames: list[Frame] = []
        while (report := self._io.read_report(int(timeout * 1000))) is not None:
            frames.extend(self._deframer.feed(report))
        return frames

    def send(self, command: int, payload: bytes = b"") -> None:
        """Send one command. Refuses anything not confirmed as a read request for this pedal."""
        if command not in CONFIRMED_HOST_COMMANDS:
            raise PermissionError(
                f"command 0x{command:02X} is not a confirmed read request for the GE100 Pro "
                "(see PROTOCOL.md)"
            )
        for report in build_reports(command, payload):
            self._io.write_report(report)

    # --- read requests, exactly as Mooer Studio sends them --------------------------------
    def request_device_info(self) -> None:
        """-> 0x02: name, firmware version."""
        self.send(0x01, b"\x00")

    def request_state(self) -> None:
        """-> 0x12 (current preset, global state), followed by 0x49."""
        self.send(0x11)

    def request_names(self, first: int, last: int) -> None:
        """-> 0x2a: preset names first..last (1..150; Mooer Studio asks 30 at a time)."""
        if not (1 <= first <= last <= 150 and last - first < 30):
            raise ValueError("first..last must lie within 1..150 and span at most 30 presets")
        self.send(0x29, bytes([first, last]))

    def request_stored_preset(self, preset: int) -> None:
        """-> 0x22: stored preset 1..150 (same layout as 0x32), without selecting it."""
        if not 1 <= preset <= 150:
            raise ValueError("preset must be 1..150")
        self.send(0x21, preset.to_bytes(2, "little"))

    def request_availability(self) -> None:
        """-> 0x2c (299 bytes, meaning unknown)."""
        self.send(0x2B)

    def request_current_preset(self) -> None:
        """-> 0x32: the current preset with its 10 chain slots, followed by 0x43."""
        self.send(0x31)

    def request_amp_captures(self) -> None:
        """-> 0x66: the 20 user amp capture slots (type 2), exactly as Mooer Studio asks."""
        self.send(0x65, bytes([0x02, 0x01, 0x00, 0x14, 0x00]))
