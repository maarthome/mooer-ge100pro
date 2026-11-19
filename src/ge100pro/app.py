"""The editor as a desktop app: a small local web server that shows web/index.html in a window and
passes the pedal's USB reports to and from the page, so no WebHID (and no particular browser) is needed.

    python -m ge100pro.app            (or GE100Pro_Editor.exe, built by tools/build_editor_exe.ps1)

The page talks to these addresses on 127.0.0.1 (web/bridge.js stands in for navigator.hid there):

    GET  /bridge/devices    {"count": n}            how many GE100 Pro pedals are plugged in
    POST /bridge/open       {"ok": true, "name"}    open the pedal
    POST /bridge/send       64 bytes                one output report
    GET  /bridge/events     text/event-stream       "report" events (64 bytes as hex), "disconnect"
    POST /bridge/settings   text                    write settings.js next to the app

Everything stays on this computer: the server only listens on 127.0.0.1. It stops a few seconds after the
editor window is closed.
"""
from __future__ import annotations

import json
import mimetypes
import os
import queue
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .transport import GE100Pro, find_hidraw

IDLE_EXIT_S = 8          # quit this long after the last editor window went away


def app_dir() -> Path:
    """Folder for settings.js: next to the .exe, else the web folder of the repo."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return web_dir()


def web_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base / "web"


def count_pedals() -> int:
    if sys.platform == "win32":
        from .hid_win import find_device_paths
        paths = find_device_paths()
        return len([p for p in paths if "mi_03" in p.lower()] or paths)
    return 1 if find_hidraw() else 0


class Bridge:
    """One open pedal, a reader thread, and the event streams of the open editor windows."""

    def __init__(self) -> None:
        self.dev: GE100Pro | None = None
        self.lock = threading.Lock()
        self.clients: list[queue.Queue] = []
        self.last_client = time.monotonic()

    def open(self) -> str:
        with self.lock:
            if self.dev is None:
                self.dev = GE100Pro()
                threading.Thread(target=self._read_loop, args=(self.dev,), daemon=True).start()
            return "GE100 Pro"

    def send(self, report: bytes) -> None:
        dev = self.dev
        if dev is None:
            raise OSError("the pedal is not open")
        dev._io.write_report(report)

    def _read_loop(self, dev: GE100Pro) -> None:
        try:
            while self.dev is dev:
                r = dev._io.read_report(200)
                if r:
                    self._emit("report", r[:64].ljust(64, b"\0").hex())
        except OSError:
            pass
        with self.lock:
            if self.dev is dev:
                self.dev = None
                try:
                    dev.close()
                except OSError:
                    pass
        self._emit("disconnect", "")

    def _emit(self, event: str, data: str) -> None:
        for q in list(self.clients):
            q.put((event, data))


BRIDGE = Bridge()


class Handler(BaseHTTPRequestHandler):
    server_version = "GE100ProEditor"

    def log_message(self, *args) -> None:  # quiet
        pass

    def _json(self, obj, code: int = 200) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        if path == "/bridge/devices":
            return self._json({"count": count_pedals(), "open": BRIDGE.dev is not None})
        if path == "/bridge/events":
            return self._events()
        if path in ("/", ""):
            path = "/index.html"
        if path == "/settings.js":                       # the person's settings live next to the app
            f = app_dir() / "settings.js"
        else:
            f = (web_dir() / path.lstrip("/")).resolve()
            if web_dir().resolve() not in f.parents:
                return self.send_error(404)
        if not f.is_file():
            return self.send_error(404)
        data = f.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(f.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        try:
            if self.path == "/bridge/open":
                return self._json({"ok": True, "name": BRIDGE.open()})
            if self.path == "/bridge/send":
                if len(body) != 64:
                    return self._json({"ok": False, "error": "a report is 64 bytes"}, 400)
                BRIDGE.send(body)
                return self._json({"ok": True})
            if self.path == "/bridge/settings":
                (app_dir() / "settings.js").write_bytes(body)
                return self._json({"ok": True, "file": str(app_dir() / "settings.js")})
        except (OSError, FileNotFoundError, PermissionError) as e:
            return self._json({"ok": False, "error": str(e)}, 500)
        self.send_error(404)

    def _events(self) -> None:
        q: queue.Queue = queue.Queue()
        BRIDGE.clients.append(q)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(b": hello\n\n")
            self.wfile.flush()
            while True:
                try:
                    event, data = q.get(timeout=5)
                    self.wfile.write(f"event: {event}\ndata: {data}\n\n".encode())
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")    # notices a closed window
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            BRIDGE.clients.remove(q)
            BRIDGE.last_client = time.monotonic()


def open_window(url: str) -> None:
    """An app-style window (Edge or Chrome without address bar) if one of them is there, else the browser."""
    candidates = []
    if sys.platform == "win32":
        for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
            if base:
                candidates += [Path(base, "Microsoft/Edge/Application/msedge.exe"),
                               Path(base, "Google/Chrome/Application/chrome.exe"),
                               Path(base, "BraveSoftware/Brave-Browser/Application/brave.exe")]
    else:
        candidates += [Path(p) for p in (shutil.which("chromium"), shutil.which("chromium-browser"),
                                         shutil.which("google-chrome")) if p]
    for exe in candidates:
        if exe.is_file():
            subprocess.Popen([str(exe), f"--app={url}", "--window-size=1440,900"])
            return
    webbrowser.open(url)


def main(argv: list[str] | None = None) -> int:
    if sys.stdout is None:                    # windowed .exe: no console
        sys.stdout = sys.stderr = open(os.devnull, "w")
    with socket.socket() as s:                # a free port on this computer only
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{port}/index.html"
    print(f"GE100 Pro editor: {url}")
    if "--no-window" not in (argv if argv is not None else sys.argv[1:]):
        open_window(url)
    started = time.monotonic()
    try:
        while True:                           # stop once every editor window has been closed for a while
            time.sleep(1)
            idle = not BRIDGE.clients and time.monotonic() - max(BRIDGE.last_client, started + 20) > IDLE_EXIT_S
            if idle:
                break
    except KeyboardInterrupt:
        pass
    server.shutdown()
    if BRIDGE.dev:
        BRIDGE.dev.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
