"""Decoders for the GE100 Pro messages seen so far (pedal -> host).

Offsets below are into the payload, i.e. AFTER the command byte.
Everything here comes from captures of the pedal itself; see PROTOCOL.md for
which fields are verified and which are still guesses.
"""

from __future__ import annotations

from dataclasses import dataclass

from .framing import Frame

STATUS = 0x15        # current preset + global state, pushed on change
BLOCK = 0x27         # one effect block changed (knob, on/off)
PRESET_DUMP = 0x32   # full preset, pushed when a preset is selected
NAVIGATION = 0x43    # cursor / page changes on the pedal's screen

BLOCK_PARAM_SLOTS = 11  # u16 LE at payload offsets 9..29


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little")


def _text(data: bytes) -> str:
    return data.split(b"\x00")[0].decode("ascii", "replace").rstrip()


@dataclass
class Status:
    preset: int          # 1..150                        [verified]
    value2: int          # changed 81 -> 90 on preset 61  [meaning unknown]
    raw: bytes


@dataclass
class Block:
    block: int           # block index                    [verified]
    byte1: int           # always 1 so far                [unknown]
    word3: int           # 0 or 7 so far: model/type?     [hypothesis]
    enabled: bool        # on/off                         [verified]
    word7: int           # 0 or 9 so far: param count?    [hypothesis]
    params: list[int]    # 11 x u16 LE, knob N = slot N   [verified for 1-4 and 6]
    text: str            # 20 bytes, "MEMORY" so far      [unknown]
    raw: bytes


@dataclass
class PresetDump:
    preset: int          # 1..150                         [verified]
    name: str            # 16 bytes                       [verified]
    raw: bytes           # 530 bytes, layout not mapped yet


@dataclass
class Navigation:
    page: int            # 0x05 cursor, 0x22 enter?, 0x0a/0x0c/0x0d/0x21/0x06 pages  [partly]
    block: int           # block index                    [verified]
    raw: bytes


def decode(frame: Frame):
    """Return a typed message for a known command, else the Frame itself."""
    p = frame.payload
    if frame.command == STATUS and len(p) >= 3:
        return Status(preset=p[0], value2=p[2], raw=p)
    if frame.command == BLOCK and len(p) >= 51:
        return Block(
            block=p[0],
            byte1=p[1],
            word3=_u16(p, 3),
            enabled=bool(p[5]),
            word7=_u16(p, 7),
            params=[_u16(p, 9 + 2 * i) for i in range(BLOCK_PARAM_SLOTS)],
            text=_text(p[31:51]),
            raw=p,
        )
    if frame.command == PRESET_DUMP and len(p) >= 17:
        return PresetDump(preset=p[0], name=_text(p[1:17]), raw=p)
    if frame.command == NAVIGATION and len(p) >= 2:
        return Navigation(page=p[0], block=p[1], raw=p)
    return frame


def describe(frame: Frame) -> str:
    """One-line human-readable description of a frame."""
    m = decode(frame)
    prefix = "" if frame.crc_ok else "BADCRC "
    if isinstance(m, Status):
        return f"{prefix}STATUS   preset={m.preset:3d}  value2={m.value2:3d}  raw={m.raw.hex()}"
    if isinstance(m, Block):
        return (f"{prefix}BLOCK    block={m.block} word3={m.word3} word7={m.word7} "
                f"on={int(m.enabled)} params={m.params} text='{m.text}'")
    if isinstance(m, PresetDump):
        return f"{prefix}PRESET   #{m.preset:3d} name='{m.name}' ({len(m.raw)} bytes)"
    if isinstance(m, Navigation):
        return f"{prefix}NAV      page=0x{m.page:02x} block={m.block}"
    return (f"{prefix}UNKNOWN  cmd=0x{frame.command:02x} len={len(frame.payload)} "
            f"raw={frame.payload.hex()}")
