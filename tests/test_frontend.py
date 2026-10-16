"""Browser-Smoke-Test der Oberfläche (benötigt Playwright + Chromium, sonst übersprungen)."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

pytest.importorskip("playwright")


def test_frontend_smoke():
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("frontend_smoke.py"))],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if proc.returncode == 77:
        pytest.skip(proc.stdout.strip())
    assert proc.returncode == 0, proc.stdout + proc.stderr
