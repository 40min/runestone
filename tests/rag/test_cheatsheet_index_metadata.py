"""Regression checks for production cheatsheet index metadata."""

import json
from pathlib import Path


def test_time_and_days_keeps_swedish_grammar_tag():
    """Preserve generic grammar discoverability for the time prepositions cheatsheet."""
    entries = json.loads(Path("cheatsheets/index.json").read_text(encoding="utf-8"))

    time_and_days = next(entry for entry in entries if entry.get("path") == "prepositions/time_and_days.md")

    assert "swedish grammar" in time_and_days["tags"]
