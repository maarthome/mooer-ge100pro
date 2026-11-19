"""Decode GE100 Pro traffic, live from hidraw or from a saved xxd dump.

  ge100pro-decode                       # live, auto-detects /dev/hidrawN
  ge100pro-decode /dev/hidraw0          # live, given node
  ge100pro-decode capture.txt           # an `xxd -c 64` dump of /dev/hidraw0
"""

from __future__ import annotations

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


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    src = args[0] if args else None
    try:
        if src and not src.startswith("/dev/"):
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
