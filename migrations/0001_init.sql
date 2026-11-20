-- NestKeeper initial schema (Cloudflare D1 / SQLite). Timestamps are ISO-8601 UTC strings.

CREATE TABLE IF NOT EXISTS subscribers (
    tg_user_id     INTEGER PRIMARY KEY,
    tg_username    TEXT,
    email          TEXT    NOT NULL UNIQUE,
    source_chat_id INTEGER NOT NULL,
    verified       INTEGER NOT NULL DEFAULT 0,
    cf_address_id  TEXT,
    created_at     TEXT    NOT NULL,
    updated_at     TEXT    NOT NULL
);

-- Open "send me your e-mail" prompts. chat_id is where the reply is expected
-- (the group, or the user's private chat); source_chat_id is the allowed group.
CREATE TABLE IF NOT EXISTS pending (
    tg_user_id        INTEGER NOT NULL,
    chat_id           INTEGER NOT NULL,
    source_chat_id    INTEGER NOT NULL,
    prompt_message_id INTEGER NOT NULL,
    created_at        TEXT    NOT NULL,
    PRIMARY KEY (tg_user_id, chat_id)
);

-- Users seen issuing commands in allowed groups; gates the private DM flow.
CREATE TABLE IF NOT EXISTS members (
    tg_user_id INTEGER NOT NULL,
    chat_id    INTEGER NOT NULL,
    PRIMARY KEY (tg_user_id, chat_id)
);
