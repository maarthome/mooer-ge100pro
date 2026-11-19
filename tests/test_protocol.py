"""Tests against the GE100 Pro's own traffic (tests/fixtures/capture1_xxd.txt).

The capture: presets scrolled, a value changed 81 -> 90, blocks navigated,
block 3 toggled off/on and knobs 1-3 turned, all on the pedal itself.
"""

from collections import Counter
from pathlib import Path

from ge100pro.crc import crc16
from ge100pro.decode import frames_from_xxd
from ge100pro.framing import Deframer, build_message, build_reports, parse_message
from ge100pro.messages import Block, Navigation, PresetDump, Status, decode

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
    presets = [m.preset for m in msgs if isinstance(m, Status)]
    assert presets[:3] == [103, 104, 105]
    names = [(m.preset, m.name) for m in msgs if isinstance(m, PresetDump)]
    assert names == [(103, "MDin_1_CLEAR"), (104, "cl_brt_jc120"), (66, "Over My Head")]
    blocks = [m for m in msgs if isinstance(m, Block)]
    assert {b.block for b in blocks} == {3}
    assert blocks[0].params[:4] == [40, 50, 50, 50]
    assert [b.enabled for b in blocks[:3]] == [True, False, True]
    assert max(b.params[0] for b in blocks) == 69  # knob 1 swept 40 -> 69
    navs = [(m.page, m.block) for m in msgs if isinstance(m, Navigation)]
    assert navs[0] == (0x22, 0)
