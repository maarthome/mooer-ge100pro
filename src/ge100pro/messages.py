"""Decoders for the GE100 Pro messages, both directions.

Offsets below are into the payload, i.e. AFTER the command byte.
The command set follows the Prime M2 family: a reply's command is the request's + 1.
See PROTOCOL.md for which fields are verified [V] and which are guesses [H].
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .framing import Frame

#: Model lists per slot type, from the GE100 Pro manual (see models.json)
MODELS = json.loads((Path(__file__).with_name("models.json")).read_text(encoding="utf-8"))["types"]

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
CMD_CHAIN = 0x2D          # id, op (1 add, 2 change, 3 delete, 4 move), args -> 0x2e id ok  (from Mooer Studio's code)

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

#: Slot type = position of the category in the manual's model list
SLOT_TYPES = {int(k): v["name"] for k, v in MODELS.items()}


def bank_label(preset: int) -> str:
    """Preset 1..150 as the pedal shows it: 50 banks of 3, 1 = 01A, 2 = 01B, 3 = 01C, 4 = 02A."""
    return f"{(preset + 2) // 3:02d}{'ABC'[(preset - 1) % 3]}"


def knobs_for(slot_type: int, model: int) -> list[dict] | None:
    """Knob definitions (name, kind, range) for a model, in parameter order; see models.json '_knobs'."""
    info = MODELS.get(str(slot_type))
    if not info:
        return None
    if "knobs_all" in info:
        return info["knobs_all"]
    if "knobs" in info and model < len(info["models"]):
        return info["knobs"][model]
    return info.get("knobs_user")


def knob_text(knob: dict, value: int) -> str:
    """A stored parameter value as the pedal shows it."""
    kind = knob["kind"]
    if kind == "db":
        v = value + knob["min"]
        return f"{'+' if v > 0 else ''}{v} dB"
    if kind == "pitch":
        v = knob["min"] + value / 10
        return f"{'+' if v > 0 else ''}{v:.1f}"
    if kind == "time":
        return f"{value} ms"
    if kind == "hz":
        return f"{value} Hz"
    if kind == "range":
        return str(knob["min"] + value)
    if kind == "sub":
        opts = knob["options"]
        return opts[value] if 0 <= value < len(opts) else str(value)
    if kind == "lowcut":
        return "OFF" if value == 0 else f"{20 + value - 1} Hz"
    if kind == "highcut":
        return "OFF" if value == 0 else "20000 Hz" if value == 1 else f"{20000 - (value - 1)} Hz"
    return str(value)


USER_MODEL = 120
USER_BASE = 100
"""User capture / IR slot u is model USER_BASE + u - 1 on the wire (user amp 75 = slot 3 = model 102)."""
"""Model number of a user capture / IR on the wire; the capture's name is in the slot's text field."""


def model_label(slot_type: int, model: int, text: str = "") -> str:
    """Model as the pedal shows it, e.g. '01 | 65 US DX' (the wire model number is 0-based)."""
    info = MODELS.get(str(slot_type), {"models": []})
    names = info["models"]
    if USER_BASE <= model < USER_BASE + info.get("user_slots", 0):
        return f"{len(names) + model - USER_BASE + 1:02d} | User {model - USER_BASE + 1}"
    if model == USER_MODEL and info.get("user_slots"):
        return f"{len(names) + info['user_slots'] + 1:02d} | {text or '?'}"
    if model < len(names):
        return f"{model + 1:02d} | {names[model]}"
    if model - len(names) < info.get("user_slots", 0):
        return f"{model + 1:02d} | User {model - len(names) + 1}"
    return f"{model + 1:02d} | ?"


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
    CMD_CHAIN: "CHAIN_EDIT",
}

#: Pedal acknowledgements (request + 1, payload 01 = ok)
ACK_NAMES = {0x14: "SET_STATE", 0x26: "SET_SLOT", 0x30: "SAVE_PRESET", 0x42: "OPEN_PAGE"}
CHAIN_ACK = 0x2E          # id, ok
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
    text: str            # 20 bytes: "MEMORY", or the capture / IR name when model is 120 [V]

    @property
    def type_name(self) -> str:
        return SLOT_TYPES.get(self.type, f"?{self.type}")

    @property
    def model_name(self) -> str:
        return model_label(self.type, self.model, self.text)

    @property
    def knobs(self) -> list[tuple[str, str]]:
        """[(knob name, value as shown on the pedal)], or [] if the model has no knob table."""
        spec = knobs_for(self.type, self.model) or []
        return [(k["name"], knob_text(k, v)) for k, v in zip(spec, self.params)]


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
    if r.command == CMD_CHAIN and len(a) >= 2:
        op = {1: "add", 2: "change", 3: "delete", 4: "move"}.get(a[1], f"op {a[1]}")
        if a[1] == 4 and len(a) >= 4:
            return f"CHAIN_EDIT       id {a[0]} move slot {a[2]} -> {a[3]}  (CHANGES THE PEDAL)"
        return f"CHAIN_EDIT       id {a[0]} {op} {a[2:].hex(' ')}  (CHANGES THE PEDAL)"
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
    knobs = ", ".join(f"{n} {v}" for n, v in s.knobs) or f"params={s.params}"
    return f"slot {s.index}: {s.type_name} [{s.model_name}] {'on' if s.enabled else 'OFF'}: {knobs}"


def describe(frame: Frame, direction: str = "pedal") -> str:
    """One-line (or multi-line for preset dumps) human-readable description of a frame."""
    m = decode(frame, direction)
    prefix = "" if frame.crc_ok else "BADCRC "
    if isinstance(m, Request):
        return f"{prefix}HOST >   {describe_request(m)}"
    if isinstance(m, State):
        kind = "STATUS  " if m.pushed else "STATE   "
        return f"{prefix}{kind} preset={bank_label(m.preset)} ({m.preset:3d})  value2={m.value2:3d}  raw={m.raw.hex()}"
    if isinstance(m, Slot):
        return f"{prefix}SLOT     {describe_slot(m)}"
    if isinstance(m, PresetDump):
        kind = "PRESET22" if frame.command == STORED_PRESET else "PRESET  "
        lines = [f"{prefix}{kind} {bank_label(m.preset)} (#{m.preset}) name='{m.name}'"]
        lines += [f"           {describe_slot(s)}" for s in m.slots if s.used]
        return "\n".join(lines)
    if isinstance(m, DeviceInfo):
        return f"{prefix}DEVICE   name='{m.name}' firmware='{m.firmware}' extra={m.extra.hex(' ')}"
    if isinstance(m, Names):
        return (f"{prefix}NAMES    {bank_label(m.first)}-{bank_label(m.last)}: "
                + ", ".join(f"{bank_label(m.first + i)} {n}" for i, n in enumerate(m.names)))
    if isinstance(m, Navigation):
        return f"{prefix}NAV      page=0x{m.page:02x} slot={m.slot}"
    if frame.command == CHAIN_ACK and len(frame.payload) >= 2:
        return f"{prefix}ACK      CHAIN_EDIT id {frame.payload[0]} {'ok' if frame.payload[1] == 1 else 'refused'}"
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
