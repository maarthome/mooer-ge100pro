"""Decoders for the GE100 Pro messages, both directions.

Offsets below are into the payload, i.e. AFTER the command byte.
The command set follows the Prime M2 family: a reply's command is the request's + 1.
See PROTOCOL.md for which fields are verified [V] and which are guesses [H].
"""

from __future__ import annotations

from dataclasses import dataclass

from .framing import Frame

# --- host -> pedal, read requests (seen from Mooer Studio) ---------------------------------
REQ_DEVICE_INFO = 0x01    # payload 00                  -> 0x02
REQ_STATE = 0x11          # no payload                  -> 0x12 (+ 0x49)
REQ_PRESET = 0x21         # preset u16                  -> 0x22 stored preset
REQ_NAMES = 0x29          # first, last preset (1..150) -> 0x2a
REQ_AVAILABILITY = 0x2B   # no payload                  -> 0x2c
REQ_CURRENT_PRESET = 0x31 # no payload                  -> 0x32 (+ 0x43)
REQ_LIST = 0x65           # type, first u16, last u16   -> 0x66 user capture list

# --- host -> pedal, commands that CHANGE the pedal (seen from Mooer Studio, never sent by this code)
CMD_SET_STATE = 0x13      # 44-byte state, byte 0 = preset -> 0x14 01: selects a preset
CMD_SET_SLOT = 0x25       # slot + 50-byte record          -> 0x26 01: live edit of one slot
CMD_SAVE = 0x2F           # preset + 16-byte name          -> 0x30 01: STORES the edit buffer
CMD_OPEN_PAGE = 0x41      # page, slot                     -> 0x42 01: pedal shows that edit page

# --- pedal -> host --------------------------------------------------------------------------
DEVICE_INFO = 0x02
STATE = 0x12              # reply to 0x11
STATUS = 0x15             # same layout as 0x12, pushed when it changes on the pedal
SLOT = 0x27               # one chain slot changed (knob, on/off), pushed
NAMES = 0x2A
AVAILABILITY = 0x2C
PRESET_DUMP = 0x32        # reply to 0x31, also pushed when a preset is selected on the pedal
NAVIGATION = 0x43         # cursor / page changes on the pedal's screen, pushed
UNKNOWN_49 = 0x49         # 6 bytes, follows every 0x12

SLOT_PARAMS = 11          # u16 LE parameters per slot
SLOT_RECORD_SIZE = 50     # one chain slot: 4 words + 11 params + 20-byte text
PRESET_SLOTS = 10         # slot records in a preset dump

#: Slot type numbers seen so far; names follow the Prime M2 numbering where the parameters match. [H]
SLOT_TYPES = {0: "?0", 1: "DRIVE", 2: "AMP", 3: "CAB", 4: "DYNA", 5: "?5 (EQ-like)", 7: "DELAY", 8: "REVERB"}

REQUEST_NAMES = {
    REQ_DEVICE_INFO: "GET_DEVICE_INFO",
    REQ_STATE: "GET_STATE",
    REQ_PRESET: "GET_PRESET",
    REQ_NAMES: "GET_NAMES",
    REQ_AVAILABILITY: "GET_AVAILABILITY",
    REQ_CURRENT_PRESET: "GET_CURRENT_PRESET",
    REQ_LIST: "GET_LIST",
    CMD_SET_STATE: "SET_STATE",
    CMD_SET_SLOT: "SET_SLOT",
    CMD_SAVE: "SAVE_PRESET",
    CMD_OPEN_PAGE: "OPEN_PAGE",
}

#: Pedal acknowledgements (request + 1, payload 01 = ok)
ACK_NAMES = {0x14: "SET_STATE", 0x26: "SET_SLOT", 0x30: "SAVE_PRESET", 0x42: "OPEN_PAGE"}
STORED_PRESET = 0x22      # reply to 0x21, same layout as 0x32 (right after a select: old slots!)
LIST = 0x66               # reply to 0x65


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little")


def _text(data: bytes) -> str:
    return data.split(b"\x00")[0].decode("latin-1").rstrip()


@dataclass
class State:
    """0x12 / 0x15: global state."""
    preset: int          # current preset 1..150                [V]
    value2: int          # 81..90 and 94 seen (master volume?)  [?]
    pushed: bool         # True for 0x15 (changed on the pedal)
    raw: bytes


@dataclass
class Slot:
    """One chain slot: the record in a preset dump, or a 0x27 push (with its slot index)."""
    index: int           # position in the chain 0..9           [V]
    used: int            # word 0: 1 = slot in use, 0 = empty   [H]
    type: int            # word 1: effect category, see SLOT_TYPES [H, 7 = delay V]
    enabled: bool        # word 2                               [V]
    model: int           # word 3: model within the category    [H]
    params: list[int]    # 11 x u16 LE; knob N = params[N-1]    [V]
    text: str            # 20 bytes, "MEMORY" so far            [?]

    @property
    def type_name(self) -> str:
        return SLOT_TYPES.get(self.type, f"?{self.type}")


def parse_slot(index: int, rec: bytes) -> Slot:
    return Slot(
        index=index,
        used=_u16(rec, 0),
        type=_u16(rec, 2),
        enabled=bool(_u16(rec, 4)),
        model=_u16(rec, 6),
        params=[_u16(rec, 8 + 2 * i) for i in range(SLOT_PARAMS)],
        text=_text(rec[30:50]),
    )


@dataclass
class PresetDump:
    preset: int          # 1..150                               [V]
    name: str            # 16 bytes                             [V]
    slots: list[Slot]    # 10 records of 50 bytes               [V layout, H meaning]
    tail: bytes          # last 12 bytes                        [?]
    raw: bytes


@dataclass
class DeviceInfo:
    name: str            # "GE100PRO"                           [V]
    firmware: str        # "V1.3.3"                             [V]
    extra: bytes         # 41 00 96 14 14 0a: 0x96 = 150 presets? 0x14/0x0a = capture slots? [H]
    raw: bytes


@dataclass
class Names:
    first: int
    last: int
    names: list[str]     # 16 bytes each                        [V]


@dataclass
class Navigation:
    page: int            # 0x05 cursor, 0x22 enter?, others = edit pages  [partly V]
    slot: int            # chain slot index                     [V]
    raw: bytes


@dataclass
class Request:
    command: int
    args: bytes

    @property
    def name(self) -> str:
        return REQUEST_NAMES.get(self.command, f"REQ_{self.command:02X}")


def decode(frame: Frame, direction: str = "pedal"):
    """Return a typed message for a known command, else the Frame itself.

    direction: "pedal" for pedal -> host traffic, "host" for host -> pedal.
    """
    p, c = frame.payload, frame.command
    if direction == "host":
        return Request(c, p)
    if c in (STATE, STATUS) and len(p) >= 3:
        return State(preset=p[0], value2=p[2], pushed=c == STATUS, raw=p)
    if c == SLOT and len(p) >= 1 + SLOT_RECORD_SIZE:
        return parse_slot(p[0], p[1 : 1 + SLOT_RECORD_SIZE])
    if c in (PRESET_DUMP, STORED_PRESET) and len(p) >= 17 + PRESET_SLOTS * SLOT_RECORD_SIZE:
        body = p[17:]
        slots = [parse_slot(i, body[i * SLOT_RECORD_SIZE : (i + 1) * SLOT_RECORD_SIZE]) for i in range(PRESET_SLOTS)]
        return PresetDump(preset=p[0], name=_text(p[1:17]), slots=slots,
                          tail=body[PRESET_SLOTS * SLOT_RECORD_SIZE :], raw=p)
    if c == DEVICE_INFO and len(p) >= 39:
        return DeviceInfo(name=_text(p[:32]), firmware=_text(p[32:39]), extra=p[39:], raw=p)
    if c == NAMES and len(p) >= 2:
        n = (len(p) - 2) // 16
        return Names(first=p[0], last=p[1], names=[_text(p[2 + 16 * i : 18 + 16 * i]) for i in range(n)])
    if c == NAVIGATION and len(p) >= 2:
        return Navigation(page=p[0], slot=p[1], raw=p)
    return frame


@dataclass
class ListEntry:
    type: int            # effect type the list belongs to (2 = amp)        [V for 2]
    index: int           # 1..20                                             [V]
    used: bool           # byte 3                                            [H]
    flag: int            # byte 4: 2 on used entries                         [?]
    name: str            # 24 bytes                                          [V]


def parse_list(p: bytes) -> list[ListEntry]:
    """0x66: entries of 29 bytes."""
    return [ListEntry(type=p[i], index=_u16(p, i + 1), used=bool(p[i + 3]), flag=p[i + 4], name=_text(p[i + 5 : i + 29]))
            for i in range(0, len(p) - 28, 29)]


def describe_request(r: Request) -> str:
    a = r.args
    if r.command == CMD_SET_STATE and a:
        return f"SET_STATE        select preset {a[0]}  (CHANGES THE PEDAL)"
    if r.command == CMD_SET_SLOT and len(a) >= 1 + SLOT_RECORD_SIZE:
        return "SET_SLOT         " + describe_slot(parse_slot(a[0], a[1 : 1 + SLOT_RECORD_SIZE])) + "  (CHANGES THE PEDAL)"
    if r.command == CMD_SAVE and a:
        return f"SAVE_PRESET      preset {a[0]} name='{_text(a[1:17])}'  (STORES TO THE PEDAL)"
    if r.command == CMD_OPEN_PAGE and len(a) >= 2:
        return f"OPEN_PAGE        page=0x{a[0]:02x} slot={a[1]}"
    if r.command == REQ_PRESET and a:
        return f"GET_PRESET       preset {_u16(a, 0)}"
    if r.command == REQ_LIST and len(a) >= 5:
        return f"GET_LIST         type {a[0]} entries {_u16(a, 1)}-{_u16(a, 3)}"
    return r.name + (f" args={a.hex(' ')}" if a else "")


def describe_slot(s: Slot) -> str:
    if not s.used:
        return f"slot {s.index}: empty"
    return (f"slot {s.index}: {s.type_name}(type={s.type}) model={s.model} on={int(s.enabled)} "
            f"params={s.params} text='{s.text}'")


def describe(frame: Frame, direction: str = "pedal") -> str:
    """One-line (or multi-line for preset dumps) human-readable description of a frame."""
    m = decode(frame, direction)
    prefix = "" if frame.crc_ok else "BADCRC "
    if isinstance(m, Request):
        return f"{prefix}HOST >   {describe_request(m)}"
    if isinstance(m, State):
        kind = "STATUS  " if m.pushed else "STATE   "
        return f"{prefix}{kind} preset={m.preset:3d}  value2={m.value2:3d}  raw={m.raw.hex()}"
    if isinstance(m, Slot):
        return f"{prefix}SLOT     {describe_slot(m)}"
    if isinstance(m, PresetDump):
        kind = "PRESET22" if frame.command == STORED_PRESET else "PRESET  "
        lines = [f"{prefix}{kind} #{m.preset:3d} name='{m.name}'"]
        lines += [f"           {describe_slot(s)}" for s in m.slots if s.used]
        return "\n".join(lines)
    if isinstance(m, DeviceInfo):
        return f"{prefix}DEVICE   name='{m.name}' firmware='{m.firmware}' extra={m.extra.hex(' ')}"
    if isinstance(m, Names):
        return f"{prefix}NAMES    {m.first}-{m.last}: " + ", ".join(m.names)
    if isinstance(m, Navigation):
        return f"{prefix}NAV      page=0x{m.page:02x} slot={m.slot}"
    if frame.command in ACK_NAMES:
        ok = frame.payload == b"\x01"
        return f"{prefix}ACK      {ACK_NAMES[frame.command]} {'ok' if ok else 'payload=' + frame.payload.hex()}"
    if frame.command == LIST:
        entries = parse_list(frame.payload)
        used = [f"{e.index}:{e.name}" for e in entries if e.used]
        return f"{prefix}LIST     type {entries[0].type if entries else '?'}, {len(entries)} entries, used: " + ", ".join(used)
    if frame.command == AVAILABILITY:
        return f"{prefix}AVAIL    {len(frame.payload)} bytes, distinct values {sorted(set(frame.payload))}"
    return (f"{prefix}UNKNOWN  cmd=0x{frame.command:02x} len={len(frame.payload)} "
            f"raw={frame.payload.hex()}")
