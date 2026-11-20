from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "render_wrangler", ROOT / "scripts/render_wrangler.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ENV = {
    "WORKER_NAME": "nestkeeper",
    "D1_DATABASE_NAME": "nestkeeper",
    "D1_DATABASE_ID": "00000000-0000-0000-0000-000000000000",
    "BOT_USERNAME": "NestKeeperApp",
    "MAIL_LIST": "list@example.org",
    "ALLOWED_CHAT_IDS": "-1001,-1002",
    "CLOUDFLARE_ACCOUNT_ID": "acc",
    "RESTRICT_SENDERS": "false",
}


def test_template_renders_valid_toml() -> None:
    rendered = _load().render((ROOT / "wrangler.toml.tmpl").read_text(), ENV)
    config = tomllib.loads(rendered)
    assert config["main"] == "src/worker.py"
    assert "python_workers" in config["compatibility_flags"]
    assert config["d1_databases"][0]["binding"] == "DB"
    assert config["vars"]["ALLOWED_CHAT_IDS"] == "-1001,-1002"
    assert config["observability"]["enabled"] is True


def test_template_missing_variable() -> None:
    env = dict(ENV)
    del env["MAIL_LIST"]
    with pytest.raises(KeyError, match="MAIL_LIST"):
        _load().render((ROOT / "wrangler.toml.tmpl").read_text(), env)


# Earliest compatibility_date for which Cloudflare runs each Python version (pywrangler metadata).
PYTHON_BY_COMPAT_DATE = {"3.14": "2026-09-08", "3.13": "2025-09-29"}


def test_compat_date_matches_project_python() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    python = pyproject["project"]["requires-python"].removeprefix(">=")
    assert (ROOT / ".python-version").read_text().strip() == python
    assert pyproject["tool"]["mypy"]["python_version"] == python
    assert pyproject["tool"]["ruff"]["target-version"] == "py" + python.replace(".", "")
    rendered = tomllib.loads(_load().render((ROOT / "wrangler.toml.tmpl").read_text(), ENV))
    assert rendered["compatibility_date"] >= PYTHON_BY_COMPAT_DATE[python]
