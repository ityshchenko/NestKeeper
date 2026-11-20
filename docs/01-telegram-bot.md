# 1. Telegram bot

The bot username is **never hard-coded**: the code reads it from the `BOT_USERNAME`
variable (GitHub variable → `wrangler.toml [vars]`). Production uses `NestKeeperApp`.

## 1.1 Create the bot and get the token

1. In Telegram, open [@BotFather](https://t.me/BotFather) and send `/newbot`.
2. Enter a display name (e.g. `NestKeeper`) and the username (`NestKeeperApp`).
3. BotFather replies with a token like `123456789:AA...`. This is the **`BOT_TOKEN`** secret.
   Keep it private. If it leaks, run `/revoke` and follow [07-operations](07-operations.md#rotating-secrets).

## 1.2 Configure the bot

Send these to @BotFather and pick the bot when asked:

| Command | Value | Why |
|---|---|---|
| `/setprivacy` | **Enable** | The bot only receives commands addressed to it and replies to its own messages, not the whole group chat. |
| `/setjoingroups` | **Enable** | Lets admins add the bot to groups. |
| `/setdescription` | e.g. «Бот розсилки ініціативної групи» | Shown in the bot's profile (Ukrainian, like all user-facing text). |

You don't need `/setcommands`: the deploy pipeline calls `setMyCommands` (default + `uk`
language, scope `all_group_chats`) using the Ukrainian descriptions in `src/nestkeeper/texts.py`.

## 1.3 Add the bot to the group

1. Open the group → **Add members** → search `@NestKeeperApp`.
2. *(Recommended)* Make the bot an admin with only **Delete messages**. Then it can delete a
   user's e-mail when they reply with it in the group. Without the right, everything else still
   works and the bot logs `delete_message_failed`.

## 1.4 Find the group chat id

`ALLOWED_CHAT_IDS` is a comma-separated list of group ids (supergroups look like
`-1001234567890`). Two ways to find an id:

* **Before the first deploy** (no webhook set yet): send any message in the group that mentions
  the bot, e.g. `/get_mail_list@NestKeeperApp`, then run
  ```sh
  curl -s "https://api.telegram.org/bot$BOT_TOKEN/getUpdates" | jq '.result[].message.chat'
  ```
* **After deploy:** run `/get_mail_list@NestKeeperApp` in the group. The bot ignores
  groups that aren't allow-listed but logs `{"event": "group_not_allowed", "chat_id": ...}`. Look it up in
  the Worker logs (see [07-operations](07-operations.md#logs)).

> When Telegram upgrades a group to a supergroup, the id changes. Update `ALLOWED_CHAT_IDS` if that happens.
