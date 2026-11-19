# Adapted from fingerskier/Mooer_GE150_Pro_Li-IO
#   https://github.com/fingerskier/Mooer_GE150_Pro_Li-IO
#   file:   src/mooer_ge150_mcp/protocol/framing.py
#   commit: b1756d5459fe392ca4c6a2972601ae2dfbfa6fde
#   Copyright (c) Matt Currier (fingerskier), MIT License -- see NOTICE.md
# Changes for the GE100 Pro: frame building and parsing kept (Frame,
# frame_checksum, parse_message, build_reports = build_chunked_frames);
# added the Deframer stream reassembler; removed the single-report helpers.
"""Frame builder and parser for the GE100 Pro's 64-byte HID reports.

HID report (64 bytes, no report ID)::

    [n] [n bytes of the message stream] [stale padding, ignore]     n <= 63

Message stream (a message may span several reports)::

    AA 55 | len (u16 LE) | cmd | payload | CRC16 (u16 BE)
            `-- len = 1 + len(payload)
    CRC-16/GSM over: len field + cmd + payload   (see crc.py)

Verified on the GE100 Pro: 191/191 frames in tests/fixtures/capture1_xxd.txt.
"""

from __future__ import annotations

from dataclasses import dataclass

from .crc import crc16

PREAMBLE = b"\xAA\x55"
HID_REPORT_SIZE = 64
CHUNK_SIZE = HID_REPORT_SIZE - 1  # first byte of each report is the chunk length


def frame_checksum(size_and_body: bytes) -> int:
    """Checksum over the size field + command + payload; serialise big-endian."""
    return crc16(size_and_body)


@dataclass
class Frame:
    """A parsed protocol frame."""

    command: int
    payload: bytes
    crc_ok: bool = True

    def __repr__(self) -> str:
        return (
            f"Frame(command=0x{self.command:02X}, "
            f"payload={self.payload.hex(' ') if self.payload else '(empty)'})"
        )


def build_message(command: int, payload: bytes = b"") -> bytes:
    """Build one framed message: AA 55 | len | cmd | payload | CRC."""
    body = bytes([command]) + payload
    size = len(body).to_bytes(2, "little")
    checksum = frame_checksum(size + body).to_bytes(2, "big")
    return PREAMBLE + size + body + checksum


def build_reports(command: int, payload: bytes = b"") -> list[bytes]:
    """Split one message into 64-byte HID reports ([n] + chunk + zero padding).

    Host -> pedal direction: the framing matches what the pedal sends and what
    the GE150 projects send, but no GE100 Pro host command is confirmed yet.
    """
    message = build_message(command, payload)
    reports = []
    for offset in range(0, len(message), CHUNK_SIZE):
        chunk = message[offset : offset + CHUNK_SIZE]
        reports.append(bytes([len(chunk)]) + chunk + b"\x00" * (CHUNK_SIZE - len(chunk)))
    return reports


def parse_message(assembled: bytes) -> Frame | None:
    """Parse one fully assembled message (preamble onward).

    Returns a Frame (with crc_ok set) or None if the header is invalid or the
    message is incomplete.
    """
    if len(assembled) < 7 or assembled[0:2] != PREAMBLE:
        return None
    body_size = int.from_bytes(assembled[2:4], "little")
    if body_size < 1 or len(assembled) < 4 + body_size + 2:
        return None
    command = assembled[4]
    payload = assembled[5 : 4 + body_size]
    expected = int.from_bytes(assembled[4 + body_size : 6 + body_size], "big")
    ok = frame_checksum(assembled[2 : 4 + body_size]) == expected
    return Frame(command=command, payload=payload, crc_ok=ok)


class Deframer:
    """Reassemble frames from a sequence of 64-byte HID reports."""

    def __init__(self) -> None:
        self._buf = b""

    def feed(self, report: bytes) -> list[Frame]:
        """Add one report; return every frame completed by it."""
        if not report:
            return []
        n = min(report[0], CHUNK_SIZE)
        self._buf += report[1 : 1 + n]
        frames: list[Frame] = []
        while True:
            start = self._buf.find(PREAMBLE)
            if start < 0:
                # keep a trailing 0xAA in case the preamble is split
                self._buf = self._buf[-1:] if self._buf.endswith(b"\xAA") else b""
                return frames
            self._buf = self._buf[start:]
            if len(self._buf) < 4:
                return frames
            total = 4 + int.from_bytes(self._buf[2:4], "little") + 2
            if len(self._buf) < total:
                return frames
            frame = parse_message(self._buf[:total])
            if frame is None:  # bad header: skip this preamble and resync
                self._buf = self._buf[2:]
                continue
            frames.append(frame)
            self._buf = self._buf[total:]
