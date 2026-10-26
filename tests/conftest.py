"""Keep rendering expectations independent of the invoking terminal's policy."""

import pytest


@pytest.fixture(autouse=True)
def color_environment(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("ANSI_COLORS_DISABLED", raising=False)
