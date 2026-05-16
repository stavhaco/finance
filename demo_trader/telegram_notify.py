from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from typing import Sequence

TELEGRAM_MAX_MESSAGE_LEN = 4096


def send_message(
    *,
    bot_token: str,
    chat_id: str,
    text: str,
    timeout_sec: int = 30,
) -> None:
    """Send a Telegram message; splits into chunks if needed."""
    if not bot_token.strip():
        raise ValueError("telegram bot token is empty")
    if not chat_id.strip():
        raise ValueError("telegram chat id is empty")
    for chunk in _split_message(text):
        _post_chunk(bot_token=bot_token, chat_id=chat_id, text=chunk, timeout_sec=timeout_sec)


def _split_message(text: str, limit: int = TELEGRAM_MAX_MESSAGE_LEN) -> Sequence[str]:
    if len(text) <= limit:
        return (text,)
    parts: list[str] = []
    buf = ""
    for line in text.splitlines(keepends=True):
        if len(line) > limit:
            if buf:
                parts.append(buf)
                buf = ""
            for i in range(0, len(line), limit):
                parts.append(line[i : i + limit])
            continue
        if len(buf) + len(line) > limit:
            parts.append(buf)
            buf = line
        else:
            buf += line
    if buf:
        parts.append(buf)
    return tuple(parts)


def _post_chunk(*, bot_token: str, chat_id: str, text: str, timeout_sec: int) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            if resp.status >= 400:
                body = resp.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"telegram API HTTP {resp.status}: {body}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"telegram API HTTP {e.code}: {body}") from e
