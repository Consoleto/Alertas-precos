import os
import re
import json
from html import unescape
import requests

CONFIG_FILE = "config.json"
STATE_FILE = "state.json"

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_messages(group):
    """Le a pagina de previa publica do Telegram (t.me/s/<grupo>), que nao exige login."""
    url = f"https://t.me/s/{group}"
    resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    html = resp.text

    pattern = re.compile(
        r'data-post="' + re.escape(group) + r'/(\d+)".*?tgme_widget_message_text[^>]*>(.*?)</div>',
        re.S,
    )
    messages = []
    for post_id, text in pattern.findall(html):
        clean_text = unescape(re.sub("<[^<]+?>", " ", text))
        clean_text = re.sub(r"\s+", " ", clean_text).strip()
        messages.append((int(post_id), clean_text, f"https://t.me/{group}/{post_id}"))
    return messages


def send_alert(group, keyword, text, link):
    msg = f'🔔 "{keyword}" encontrado em {group}\n\n{text[:500]}\n\n{link}'
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg},
        timeout=15,
    )


def main():
    config = load_json(CONFIG_FILE, {"groups": [], "keywords": []})
    state = load_json(STATE_FILE, {})

    groups = config.get("groups", [])
    keywords = [k.lower().strip() for k in config.get("keywords", []) if k.strip()]

    for group in groups:
        group = group.strip()
        if not group:
            continue

        first_run = group not in state
        last_seen = state.get(group, 0)

        try:
            messages = fetch_messages(group)
        except Exception as e:
            print(f"Erro ao buscar o grupo {group}: {e}")
            continue

        max_id = last_seen
        for post_id, text, link in messages:
            if post_id <= last_seen:
                continue
            max_id = max(max_id, post_id)

            # Na primeira vez que um grupo e monitorado, so registramos o ponto de
            # partida (para nao disparar um alerta para CADA mensagem antiga do grupo).
            if first_run:
                continue

            lower_text = text.lower()
            for kw in keywords:
                if kw in lower_text:
                    send_alert(group, kw, text, link)
                    break

        state[group] = max_id

    save_json(STATE_FILE, state)


if __name__ == "__main__":
    main()
