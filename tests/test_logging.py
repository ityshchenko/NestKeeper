from __future__ import annotations

import json

import pytest

from nestkeeper.logging import configure_logging, get_logger, mask_email, mask_emails_processor


def test_mask_email() -> None:
    assert mask_email("to alice@example.com and b@x.org") == "to a***@example.com and b***@x.org"
    assert mask_email("nothing here") == "nothing here"


def test_processor_masks_nested_values() -> None:
    event = {"event": "x", "email": "alice@example.com", "nested": {"l": ["bob@ex.io", 3]}}
    out = mask_emails_processor(None, "info", event)
    assert out == {"event": "x", "email": "a***@example.com", "nested": {"l": ["b***@ex.io", 3]}}


def test_json_output_is_masked(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    get_logger("test").info("registered", email="carol@example.com", user_id=1)
    line = capsys.readouterr().out.strip().splitlines()[-1]
    record = json.loads(line)
    assert record["event"] == "registered"
    assert record["email"] == "c***@example.com"
    assert record["level"] == "info"
    assert "timestamp" in record
