from __future__ import annotations

import json
from typing import Any

from nestkeeper.app import App, HttpReply, HttpRequest
from tests.conftest import WEBHOOK_SECRET

BASE = "https://nestkeeper.example.workers.dev"


async def post_update(app: App, update: dict[str, Any], secret: str = WEBHOOK_SECRET) -> HttpReply:
    return await app.handle_http(
        HttpRequest(
            method="POST",
            url=f"{BASE}/webhook",
            headers={"X-Telegram-Bot-Api-Secret-Token": secret},
            body=json.dumps(update),
        )
    )
