"""Read USBPcap .pcapng captures (Wireshark on Windows) and keep only the GE100 Pro.

USBPcap records every device on the root hub it is attached to, including keyboards and mice. Typed keys can be
recovered from such a capture, so never share or commit an unfiltered capture: filter it first.

  python3 -m ge100pro.pcapng filter IN.pcapng OUT.pcapng   # keep only the GE100 Pro's packets

The reader understands the pcapng blocks Wireshark writes (section header, interface description, enhanced packet)
and the USBPcap pseudo-header (link type 249).
"""

from __future__ import annotations

import struct
import sys
from dataclasses import dataclass

LINKTYPE_USBPCAP = 249
VENDOR_ID = 0x34DB
PRODUCT_ID = 0x0011

_SHB, _IDB, _EPB = 0x0A0D0D0A, 0x00000001, 0x00000006
_TRANSFER_INTERRUPT = 1
_OPT_TSRESOL = 9


@dataclass
class UsbPacket:
    time_us: int        # timestamp in microseconds
    bus: int
    device: int         # USB device address on that bus
    endpoint: int       # bit 7 set = IN
    transfer: int       # 0 iso, 1 interrupt, 2 control, 3 bulk
    to_host: bool       # True = completion of a device -> host transfer
    data: bytes         # transfer data (without the USBPcap header)
    raw_block: bytes    # the original enhanced packet block, for writing filtered files


def _blocks(buf: bytes):
    i = 0
    while i + 12 <= len(buf):
        btype, blen = struct.unpack_from("<II", buf, i)
        if blen < 12 or i + blen > len(buf):
            break
        yield btype, buf[i + 8 : i + blen - 4], buf[i : i + blen]
        i += blen


def _tsresol(idb_body: bytes) -> int:
    """Return ticks per second of an interface (default microseconds)."""
    i = 8
    while i + 4 <= len(idb_body):
        code, length = struct.unpack_from("<HH", idb_body, i)
        if code == 0:
            break
        if code == _OPT_TSRESOL and length >= 1:
            v = idb_body[i + 4]
            return 2 ** (v & 0x7F) if v & 0x80 else 10 ** v
        i += 4 + (length + 3) // 4 * 4
    return 1_000_000


def read_packets(path: str):
    """Yield every USBPcap packet in a pcapng file."""
    with open(path, "rb") as f:
        buf = f.read()
    resol: list[int] = []
    for btype, body, raw in _blocks(buf):
        if btype == _SHB:
            resol = []
        elif btype == _IDB:
            linktype = struct.unpack_from("<H", body, 0)[0]
            if linktype != LINKTYPE_USBPCAP:
                raise ValueError(f"{path}: link type {linktype}, expected USBPcap ({LINKTYPE_USBPCAP})")
            resol.append(_tsresol(body))
        elif btype == _EPB:
            iface, ts_hi, ts_lo, caplen, _ = struct.unpack_from("<IIIII", body, 0)
            pkt = body[20 : 20 + caplen]
            if len(pkt) < 27:
                continue
            hlen, _irp, _status, _func, info, bus, dev, ep, transfer, dlen = struct.unpack_from(
                "<HQIHBHHBBI", pkt, 0
            )
            ticks = (ts_hi << 32) | ts_lo
            per_s = resol[iface] if iface < len(resol) else 1_000_000
            yield UsbPacket(
                time_us=ticks * 1_000_000 // per_s,
                bus=bus,
                device=dev,
                endpoint=ep,
                transfer=transfer,
                to_host=bool(info & 1),
                data=pkt[hlen : hlen + dlen],
                raw_block=raw,
            )


def find_pedal(packets: list[UsbPacket]) -> tuple[int, int]:
    """Return (bus, device address) of the GE100 Pro, found from its device descriptor."""
    for p in packets:
        d = p.data
        if p.transfer == 2 and p.to_host and len(d) >= 12 and d[0] == 18 and d[1] == 1:
            vid, pid = struct.unpack_from("<HH", d, 8)
            if (vid, pid) == (VENDOR_ID, PRODUCT_ID):
                return p.bus, p.device
    # No descriptor in the capture (pedal already enumerated): fall back to the HID endpoints
    for p in packets:
        if p.transfer == _TRANSFER_INTERRUPT and p.endpoint in (0x05, 0x85) and len(p.data) == 64:
            return p.bus, p.device
    raise LookupError("no GE100 Pro (34db:0011) traffic found in this capture")


def pedal_reports(path: str):
    """Yield (time_us, direction, 64-byte report); direction is 'host' (to pedal) or 'pedal'."""
    packets = list(read_packets(path))
    bus, dev = find_pedal(packets)
    for p in packets:
        if (p.bus, p.device) != (bus, dev) or p.transfer != _TRANSFER_INTERRUPT or len(p.data) != 64:
            continue
        if p.endpoint == 0x05 and not p.to_host:
            yield p.time_us, "host", p.data
        elif p.endpoint == 0x85 and p.to_host:
            yield p.time_us, "pedal", p.data


def _block(btype: int, body: bytes) -> bytes:
    body += b"\x00" * (-len(body) % 4)
    n = 12 + len(body)
    return struct.pack("<II", btype, n) + body + struct.pack("<I", n)


def filter_capture(src: str, dst: str) -> int:
    """Write a new pcapng holding only the GE100 Pro's packets. Returns the packet count.

    The section header and interface blocks are rebuilt without options (no host or OS strings); only the
    timestamp resolution is kept.
    """
    with open(src, "rb") as f:
        buf = f.read()
    packets = list(read_packets(src))
    bus, dev = find_pedal(packets)
    resol = None
    for btype, body, _ in _blocks(buf):
        if btype == _IDB:
            resol = _tsresol(body)
            break
    shb = _block(_SHB, struct.pack("<IHHq", 0x1A2B3C4D, 1, 0, -1))
    idb_opts = b""
    if resol and resol != 1_000_000:
        exp = len(str(resol)) - 1
        idb_opts = struct.pack("<HHB", _OPT_TSRESOL, 1, exp) + b"\x00" * 3 + struct.pack("<HH", 0, 0)
    idb = _block(_IDB, struct.pack("<HHI", LINKTYPE_USBPCAP, 0, 0x40000) + idb_opts)
    kept = [p.raw_block for p in packets if (p.bus, p.device) == (bus, dev)]
    with open(dst, "wb") as f:
        f.write(shb + idb + b"".join(kept))
    return len(kept)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) == 3 and args[0] == "filter":
        n = filter_capture(args[1], args[2])
        print(f"wrote {args[2]}: {n} GE100 Pro packets, all other USB devices removed")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
