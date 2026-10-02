"""Notifications et commandes Telegram (optionnel)."""
import logging

import requests

log = logging.getLogger(__name__)


class Telegram:
    def __init__(self, token: str, chat_id: str, enabled: bool = True):
        self.enabled = enabled and bool(token and chat_id)
        self.base = f"https://api.telegram.org/bot{token}"
        self.chat_id = str(chat_id)
        self.offset = 0

    def send(self, text: str) -> None:
        log.info(text.replace("\n", " | "))
        if not self.enabled:
            return
        try:
            requests.post(f"{self.base}/sendMessage",
                          json={"chat_id": self.chat_id, "text": text}, timeout=10)
        except requests.RequestException as e:
            log.warning("Telegram injoignable : %s", e)

    def commands(self) -> list:
        """Commandes reçues depuis le dernier appel, uniquement depuis TON chat."""
        if not self.enabled:
            return []
        try:
            r = requests.get(f"{self.base}/getUpdates",
                             params={"offset": self.offset, "timeout": 0}, timeout=10).json()
        except (requests.RequestException, ValueError):
            return []
        out = []
        for upd in r.get("result", []):
            self.offset = upd["update_id"] + 1
            msg = upd.get("message") or {}
            if str(msg.get("chat", {}).get("id")) == self.chat_id and msg.get("text", "").startswith("/"):
                out.append(msg["text"].split()[0].split("@")[0].lower())
        return out
