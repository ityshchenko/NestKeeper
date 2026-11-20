"""Render wrangler.toml from wrangler.toml.tmpl using environment variables.

Usage: uv run python scripts/render_wrangler.py [--out wrangler.toml]
"""

from __future__ import annotations

import argparse
import json
import os
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULTS = {"RESTRICT_SENDERS": "false", "D1_DATABASE_NAME": "nestkeeper"}


def render(template: str, env: dict[str, str]) -> str:
    tmpl = string.Template(template)
    missing = sorted(set(tmpl.get_identifiers()) - env.keys())
    if missing:
        raise KeyError(", ".join(missing))
    # json.dumps produces a valid TOML basic string; strip the quotes the template provides.
    return tmpl.substitute({k: json.dumps(v)[1:-1] for k, v in env.items()})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, default=ROOT / "wrangler.toml.tmpl")
    parser.add_argument("--out", type=Path, default=ROOT / "wrangler.toml")
    args = parser.parse_args()
    env = {**DEFAULTS, **{k: v for k, v in os.environ.items() if v}}
    try:
        args.out.write_text(render(args.template.read_text(), env))
    except KeyError as exc:
        print(f"missing environment variables: {exc.args[0]}", file=sys.stderr)
        return 1
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
