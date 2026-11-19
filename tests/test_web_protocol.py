"""Run the web editor's JavaScript protocol layer (web/protocol.js) against the same captures."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from ge100pro.pcapng import pedal_reports

HERE = Path(__file__).parent


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
def test_web_protocol_js(tmp_path):
    data = {
        name: [[d, r.hex()] for _, d, r in pedal_reports(str(HERE / "fixtures" / f"{name}.pcapng"))]
        for name in ("01_connect_ge100pro", "03_knob", "05_change_model")
    }
    reports = tmp_path / "reports.json"
    reports.write_text(json.dumps(data))
    out = subprocess.run(["node", str(HERE / "web" / "protocol.test.js"), str(reports)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "js protocol ok" in out.stdout
