"""Decode GE100 Pro traffic, live from hidraw, from an xxd dump or from a filtered Wireshark capture.

  python3 -m ge100pro                         # live, auto-detects /dev/hidrawN
  python3 -m ge100pro /dev/hidraw0            # live, given node (Linux)
  python3 -m ge100pro capture.txt             # an `xxd -c 64` dump of /dev/hidrawN (pedal -> host only)
  python3 -m ge100pro capture.pcapng          # USBPcap capture: both directions, with timestamps
"""

from __future__ import annotations

import os
import re
import sys

from .framing import Deframer
from .messages import describe

_XXD_LINE = re.compile(r"^[0-9a-f]{8}: ((?:[0-9a-f]{4} ){31}[0-9a-f]{4})")


def reports_from_xxd(path: str):
    """Yield 64-byte reports from an `xxd -c 64` dump."""
    with open(path) as f:
        for line in f:
            m = _XXD_LINE.match(line)
            if m:
                yield bytes.fromhex(m.group(1).replace(" ", ""))


def frames_from_xxd(path: str):
    d = Deframer()
    for report in reports_from_xxd(path):
        yield from d.feed(report)


def frames_from_pcapng(path: str):
    """Yield (time_ms, direction, frame) from a USBPcap capture; direction is 'host' or 'pedal'."""
    from .pcapng import pedal_reports

    deframers = {"host": Deframer(), "pedal": Deframer()}
    t0 = None
    for time_us, direction, report in pedal_reports(path):
        t0 = time_us if t0 is None else t0
        for frame in deframers[direction].feed(report):
            yield (time_us - t0) / 1000, direction, frame


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    src = args[0] if args else None
    try:
        if src and src.endswith(".pcapng"):
            for ms, direction, frame in frames_from_pcapng(src):
                print(f"{ms:9.1f}  {describe(frame, direction)}", flush=True)
        elif src and os.path.isfile(src) and not src.startswith("/dev/"):
            for frame in frames_from_xxd(src):
                print(describe(frame), flush=True)
        else:
            from .transport import GE100Pro

            with GE100Pro(src) as pedal:
                for frame in pedal.frames():
                    print(describe(frame), flush=True)
    except KeyboardInterrupt:
        pass
    except BrokenPipeError:
        pass
    except (FileNotFoundError, PermissionError, LookupError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
