"""Tests against the GE100 Pro's own traffic (tests/fixtures/capture1_xxd.txt).

The capture: presets scrolled, a value changed 81 -> 90, blocks navigated,
block 3 toggled off/on and knobs 1-3 turned, all on the pedal itself.
"""

from collections import Counter
from pathlib import Path

from ge100pro.crc import crc16
from ge100pro.decode import frames_from_xxd
from ge100pro.framing import Deframer, build_message, build_reports, parse_message
from ge100pro.messages import DeviceInfo, Names, Navigation, PresetDump, Request, Slot, State, decode

CAPTURE1 = Path(__file__).parent / "fixtures" / "capture1_xxd.txt"


def test_crc_known_frame():
    # 09 | AA 55 03 00 43 22 00 | 35 54  (a navigation frame from capture 1)
    assert crc16(bytes.fromhex("0300432200")) == 0x3554


def test_build_message_matches_pedal_frame():
    assert build_message(0x43, bytes([0x22, 0x00])) == bytes.fromhex("aa5503004322003554")


def test_reports_roundtrip_long_message():
    payload = bytes(range(256)) * 2  # forces a multi-report message
    d = Deframer()
    frames = [f for r in build_reports(0x32, payload) for f in d.feed(r)]
    assert len(frames) == 1
    assert frames[0].command == 0x32 and frames[0].payload == payload and frames[0].crc_ok


def test_bad_crc_is_flagged():
    msg = bytearray(build_message(0x15, b"\x01\x00"))
    msg[-1] ^= 0xFF
    assert parse_message(bytes(msg)).crc_ok is False


def test_capture1_all_frames_valid():
    frames = list(frames_from_xxd(CAPTURE1))
    assert len(frames) == 191
    assert all(f.crc_ok for f in frames)
    counts = Counter((f.command, len(f.payload)) for f in frames)
    assert counts == {(0x27, 51): 162, (0x15, 44): 18, (0x43, 2): 8, (0x32, 529): 3}


def test_capture1_decoded_content():
    msgs = [decode(f) for f in frames_from_xxd(CAPTURE1)]
    presets = [m.preset for m in msgs if isinstance(m, State) and m.pushed]
    assert presets[:3] == [103, 104, 105]
    names = [(m.preset, m.name) for m in msgs if isinstance(m, PresetDump)]
    assert names == [(103, "MDin_1_CLEAR"), (104, "cl_brt_jc120"), (66, "Over My Head")]
    blocks = [m for m in msgs if isinstance(m, Slot)]
    assert {b.index for b in blocks} == {3}
    assert blocks[0].params[:4] == [40, 50, 50, 50]
    assert [b.enabled for b in blocks[:3]] == [True, False, True]
    assert max(b.params[0] for b in blocks) == 69  # knob 1 swept 40 -> 69
    navs = [(m.page, m.slot) for m in msgs if isinstance(m, Navigation)]
    assert navs[0] == (0x22, 0)


# --- Mooer Studio connect sequence (Wireshark/USBPcap, filtered to the pedal only) --------

from ge100pro.decode import frames_from_pcapng
from ge100pro.pcapng import read_packets

CONNECT = Path(__file__).parent / "fixtures" / "01_connect_ge100pro.pcapng"


def test_connect_capture_holds_only_the_pedal():
    devices = {(p.bus, p.device) for p in read_packets(str(CONNECT))}
    assert devices == {(1, 14)}


def test_connect_sequence_requests():
    frames = list(frames_from_pcapng(str(CONNECT)))
    assert all(f.crc_ok for _, _, f in frames)
    host = [(f.command, f.payload) for _, d, f in frames if d == "host"]
    assert host[:3] == [(0x11, b""), (0x11, b""), (0x2B, b"")]
    assert (0x01, b"\x00") in host
    name_ranges = [p for c, p in host if c == 0x29]
    assert name_ranges[:5] == [bytes([a, a + 29]) for a in range(1, 151, 30)]
    assert {c for c, _ in host} == {0x01, 0x11, 0x29, 0x2B, 0x31}


def test_replies_are_request_plus_one():
    frames = list(frames_from_pcapng(str(CONNECT)))
    requests = {f.command for _, d, f in frames if d == "host"}
    replies = {f.command for _, d, f in frames if d == "pedal"}
    assert {r + 1 for r in requests} <= replies


def test_connect_decoded_content():
    msgs = [decode(f, d) for _, d, f in frames_from_pcapng(str(CONNECT))]
    info = next(m for m in msgs if isinstance(m, DeviceInfo))
    assert (info.name, info.firmware) == ("GE100PRO", "V1.3.3")
    state = next(m for m in msgs if isinstance(m, State))
    assert state.preset == 82 and not state.pushed
    names = {}
    for m in msgs:
        if isinstance(m, Names):
            names.update(zip(range(m.first, m.last + 1), m.names))
    assert len(names) == 150
    assert names[1] == "Atlas Clean" and names[61] == "Over My Head" and names[82] == "JP Lead"
    dump = next(m for m in msgs if isinstance(m, PresetDump))
    assert (dump.preset, dump.name) == (82, "JP Lead")
    used = [(s.index, s.type, s.model) for s in dump.slots if s.used]
    assert used == [(0, 4, 1), (1, 1, 21), (2, 2, 27), (3, 5, 2), (4, 7, 8), (5, 8, 1), (9, 3, 42)]
    assert dump.slots[2].params[:6] == [70, 57, 48, 26, 25, 75]
    assert all(isinstance(m, Request) for m, (_, d, _f) in zip(msgs, frames_from_pcapng(str(CONNECT))) if d == "host")
