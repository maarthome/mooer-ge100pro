#!/usr/bin/env python3
"""Convert .nam captures to .gnr files for the GE100 Pro, one file or a whole folder tree.

The conversion itself is done by Mooer's own converter, nam_to_gnr_cli.exe, which comes with
Mooer Studio (resources\\nam). This script only runs it, the same way Mooer Studio does:

    nam_to_gnr_cli.exe --input <file.nam> --output <file.gnr>      (working folder: its own folder)

Output names: the first 18 characters are the capture name as the pedal shows it (the pedal keeps
18 characters). A shorter name is filled up to 18 with PAD. After those 18 come the date and time:

    Mesa_Cln.nam  ->  Mesa_Cln##########_2026-11-19_1552.gnr

Folders: choosing the folder  D:\\NAM  with subfolders writes to  D:\\NAM_GNR  with the same tree,
every folder name with _GNR added:  D:\\NAM\\Fender\\Twin.nam  ->  D:\\NAM_GNR\\Fender_GNR\\Twin....gnr

Usage (Windows, Python 3.9+):
    python nam_to_gnr.py                      asks: one file or a folder, then picks it in a window
    python nam_to_gnr.py <file.nam | folder>  no questions
    python nam_to_gnr.py --cli <path to nam_to_gnr_cli.exe> ...
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

NAME_LEN = 18          # characters the pedal keeps of a capture name
PAD = "#"              # fills a short name up to 18 ('*' is not allowed in Windows file names)
FOLDER_SUFFIX = "_GNR"
DEFAULT_CLI = Path(r"E:\MIDI\Mooer\GE100_PRO_LI\Mooer Studio For GE100 Pro\resources\nam\nam_to_gnr_cli.exe")
BAD_CHARS = '<>:"/\\|?*'   # not allowed in Windows file names


def out_name(src: Path, when: dt.datetime) -> str:
    """18-character capture name (padded with PAD), then _date_time, then .gnr."""
    stem = "".join("_" if c in BAD_CHARS or ord(c) < 32 or ord(c) > 126 else c for c in src.stem)
    return f"{stem[:NAME_LEN].ljust(NAME_LEN, PAD)}_{when:%Y-%m-%d_%H%M}.gnr"


def find_cli(given: str | None) -> Path:
    for p in [given, os.environ.get("NAM_TO_GNR_CLI"), DEFAULT_CLI]:
        if p and Path(p).is_file():
            return Path(p)
    try:                                    # ask for it
        from tkinter import Tk, filedialog
        root = Tk(); root.withdraw()
        p = filedialog.askopenfilename(title="Where is nam_to_gnr_cli.exe? (Mooer Studio\\resources\\nam)",
                                       filetypes=[("nam_to_gnr_cli", "nam_to_gnr_cli*"), ("All files", "*")])
        root.destroy()
        if p:
            return Path(p)
    except Exception:
        pass
    sys.exit("nam_to_gnr_cli.exe not found: give it with --cli <path>")


def convert(cli: Path, src: Path, dst: Path) -> tuple[bool, str]:
    """Run Mooer's converter for one file. Returns (ok, message)."""
    cli, src, dst = cli.resolve(), src.resolve(), dst.resolve()   # the converter runs in its own folder
    dst.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run([str(cli), "--input", str(src), "--output", str(dst)], cwd=str(cli.parent),
                          capture_output=True, text=True, errors="replace")
    status = None
    for line in proc.stdout.splitlines():   # the converter prints JSON lines with status / progress
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if msg.get("status") in ("success", "failure"):
            status = msg
    if status and status.get("status") == "failure":
        return False, f"converter failed (code {status.get('code')})"
    if proc.returncode != 0 and not status:
        return False, f"converter exit code {proc.returncode}: {proc.stderr.strip()[:200]}"
    if not dst.is_file() or dst.stat().st_size == 0:
        return False, "no output file"
    return True, f"{dst.stat().st_size} bytes"


def jobs_for(source: Path, when: dt.datetime) -> list[tuple[Path, Path]]:
    if source.is_file():
        return [(source, source.with_name(out_name(source, when)))]
    root_out = source.with_name(source.name + FOLDER_SUFFIX)
    jobs = []
    for src in sorted(source.rglob("*")):
        if src.is_file() and src.suffix.lower() == ".nam":
            rel_dirs = src.relative_to(source).parent.parts
            dst_dir = root_out.joinpath(*[d + FOLDER_SUFFIX for d in rel_dirs])
            jobs.append((src, dst_dir / out_name(src, when)))
    return jobs


def ask_source() -> Path | None:
    from tkinter import Tk, filedialog, messagebox
    root = Tk(); root.withdraw()
    folder = messagebox.askyesnocancel("NAM to GNR", "Convert a whole folder (with its subfolders)?\n\n"
                                       "Yes: pick a folder\nNo: pick one .nam file")
    if folder is None:
        p = ""
    elif folder:
        p = filedialog.askdirectory(title="Folder with .nam files")
    else:
        p = filedialog.askopenfilename(title=".nam file", filetypes=[("NAM captures", "*.nam")])
    root.destroy()
    return Path(p) if p else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Convert .nam files to .gnr with Mooer's nam_to_gnr_cli.exe")
    ap.add_argument("source", nargs="?", help=".nam file or folder (asked in a window when left out)")
    ap.add_argument("--cli", help="path to nam_to_gnr_cli.exe")
    args = ap.parse_args(argv)

    source = Path(args.source) if args.source else ask_source()
    if not source or not source.exists():
        print("Nothing chosen.")
        return 1
    cli = find_cli(args.cli)
    jobs = jobs_for(source, dt.datetime.now())
    if not jobs:
        print(f"No .nam files in {source}")
        return 1
    failed = 0
    for i, (src, dst) in enumerate(jobs, 1):
        ok, msg = convert(cli, src, dst)
        failed += not ok
        print(f"[{i}/{len(jobs)}] {'OK  ' if ok else 'FAIL'} {src}  ->  {dst.name}  ({msg})")
    print(f"\n{len(jobs) - failed} converted, {failed} failed.")
    if not args.source:
        input("Press Enter to close.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
