"""Ask the pedal for its state, the same way Mooer Studio does when it connects. Read-only.

  python3 -m ge100pro.probe            # device info, state, all 150 preset names, current preset, amp captures

Sends only the read requests Mooer Studio sends to this pedal (see PROTOCOL.md §4). Close Mooer Studio first:
only one program can use the control channel at a time.
"""

from __future__ import annotations

import sys

from .messages import describe
from .transport import GE100Pro


def main() -> int:
    try:
        with GE100Pro() as pedal:
            pedal.read_frames(0.2)  # drop anything already queued
            steps = [
                ("device info", pedal.request_device_info),
                ("state", pedal.request_state),
                *[(f"names {a}-{a + 29}", lambda a=a: pedal.request_names(a, a + 29)) for a in range(1, 151, 30)],
                ("availability", pedal.request_availability),
                ("current preset", pedal.request_current_preset),
                ("user drive captures", lambda: pedal.request_user_list(1)),
                ("user amp captures", lambda: pedal.request_user_list(2)),
                ("user cab IRs", lambda: pedal.request_user_list(3)),
            ]
            for label, request in steps:
                request()
                frames = pedal.read_frames(0.5)
                print(f"--- {label}: {len(frames)} frame(s)")
                for frame in frames:
                    print(describe(frame))
    except (FileNotFoundError, PermissionError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
