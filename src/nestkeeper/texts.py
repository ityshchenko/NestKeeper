"""Single source of every user-facing (Ukrainian) string. Handlers never inline literals."""

from __future__ import annotations

from typing import Final

CMD_GET_MAIL_LIST: Final = "get_mail_list"
CMD_ADD_ME: Final = "add_me_to_mail_list"

COMMAND_DESCRIPTIONS: Final[dict[str, str]] = {
    CMD_GET_MAIL_LIST: "Отримати адресу розсилки",
    CMD_ADD_ME: "Додати мене до розсилки",
}

MAIL_LIST_REPLY: Final = "Адреса розсилки: {mail_list}"

ASK_EMAIL_GROUP: Final = (
    "Надішліть свою електронну адресу приватно або дайте відповідь на це повідомлення."
)
SEND_PRIVATELY_BUTTON: Final = "Надіслати приватно"
ASK_EMAIL_PRIVATE: Final = "Надішліть, будь ласка, свою електронну адресу у відповідь."
EMAIL_PLACEHOLDER: Final = "name@example.com"

INVALID_EMAIL: Final = "Схоже, це некоректна електронна адреса. Спробуйте ще раз."
SUCCESS_VERIFY: Final = (
    "Готово! Cloudflare надіслав лист для підтвердження — перейдіть за посиланням у ньому, "
    "щоб отримувати листи розсилки."
)
SUCCESS_ALREADY_VERIFIED: Final = (
    "Готово! Цю адресу вже підтверджено — ви отримуватимете листи розсилки."
)
EMAIL_TAKEN: Final = "Ця адреса вже використовується іншим учасником."
REGISTRATION_FAILED: Final = "Не вдалося додати адресу. Спробуйте пізніше."
PROMPT_EXPIRED: Final = "Час очікування минув. Повторіть команду /add_me_to_mail_list у групі."
