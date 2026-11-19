"""Linux hidraw transport for the GE100 Pro (34db:0011, HID interface 3).

The pedal pushes its changes without any handshake. Sending is limited to the
read requests Mooer Studio itself sends to this pedal (captured on the wire,
tests/fixtures/01_connect_ge100pro.pcapng); everything else is refused, because
other Mooer models have commands that erase memory and the same opcode can mean
something else on this pedal.
"""

from __future__ import annotations

import glob
import os
import select

from .framing import HID_REPORT_SIZE, Deframer, Frame, build_reports

VENDOR_ID = 0x34DB
PRODUCT_ID = 0x0011

#: Host -> pedal commands confirmed on the GE100 Pro: only the read requests Mooer Studio
#: sends during its connect sequence. No command that changes the pedal is listed yet.
CONFIRMED_HOST_COMMANDS: set[int] = {0x01, 0x11, 0x29, 0x2B, 0x31}


def find_hidraw(vendor_id: int = VENDOR_ID, product_id: int = PRODUCT_ID) -> str | None:
    """Return the /dev/hidrawN node of the pedal, or None."""
    wanted = f"HID_ID=0003:{vendor_id:08X}:{product_id:08X}"
    for uevent in sorted(glob.glob("/sys/class/hidraw/hidraw*/device/uevent")):
        with open(uevent) as f:
            if wanted in f.read():
                return "/dev/" + uevent.split("/")[4]
    return None


class GE100Pro:
    """Minimal hidraw connection: iterate over frames, optionally send."""

    def __init__(self, path: str | None = None) -> None:
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
        self._deframer = Deframer()

    def close(self) -> None:
        os.close(self._fd)

    def __enter__(self) -> "GE100Pro":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def frames(self):
        """Yield frames forever (blocking reads)."""
        while True:
            report = os.read(self._fd, HID_REPORT_SIZE)
            yield from self._deframer.feed(report)

    def read_frames(self, timeout: float = 0.5) -> list[Frame]:
        """Read whatever arrives until `timeout` seconds pass without a new report."""
        frames: list[Frame] = []
        while select.select([self._fd], [], [], timeout)[0]:
            frames.extend(self._deframer.feed(os.read(self._fd, HID_REPORT_SIZE)))
        return frames

    def send(self, command: int, payload: bytes = b"") -> None:
        """Send one command. Refuses anything not confirmed for this pedal."""
        if command not in CONFIRMED_HOST_COMMANDS:
            raise PermissionError(
                f"command 0x{command:02X} is not confirmed for the GE100 Pro; "
                "capture it from Mooer Studio first (see PROTOCOL.md)"
            )
        for report in build_reports(command, payload):
            # hidraw, unnumbered reports: leading 0x00 report ID + 64-byte report
            os.write(self._fd, b"\x00" + report)

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

    def request_availability(self) -> None:
        """-> 0x2c (299 bytes, meaning unknown)."""
        self.send(0x2B)

    def request_current_preset(self) -> None:
        """-> 0x32: the current preset with its 10 chain slots, followed by 0x43."""
        self.send(0x31)
