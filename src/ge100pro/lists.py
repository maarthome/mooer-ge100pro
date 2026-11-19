"""EXPERIMENT: ask the pedal which name lists it can send (request 0x65, reply 0x66).

  python -m ge100pro.lists --yes

Mooer Studio only ever sends `65 02 0001 0014`: the 20 user amp capture slots. This tries the same request with
the other slot types 0..8 (still entries 1..20) to see whether the pedal also has lists for user cab IRs, or even
the factory model names. 0x65 is a read request, and only the type byte differs from what Mooer Studio sends, but
these arguments are untested on this pedal: that is why it only runs with --yes. Close Mooer Studio first.
"""

from __future__ import annotations

import sys

from .messages import LIST, MODELS, parse_list
from .transport import GE100Pro


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if "--yes" not in args:
        print(__doc__)
        return 2
    try:
        with GE100Pro() as pedal:
            pedal.read_frames(0.2)
            for t in range(9):
                pedal.send(0x65, bytes([t, 0x01, 0x00, 0x14, 0x00]))
                frames = [f for f in pedal.read_frames(0.6) if f.command == LIST]
                name = MODELS[str(t)]["name"]
                if not frames:
                    print(f"type {t} ({name}): no list")
                    continue
                for f in frames:
                    entries = parse_list(f.payload)
                    used = [f"{e.index}:{e.name}" for e in entries if e.used]
                    print(f"type {t} ({name}): {len(entries)} entries, used: {', '.join(used) or 'none'}")
                    print(f"    raw: {f.payload[:58].hex(' ')} ...")
    except (FileNotFoundError, PermissionError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
