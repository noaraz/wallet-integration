---
name: tg-local-testing
description: Use when starting the wallet-bot locally for manual Telegram end-to-end testing — starts the uvicorn server in Docker, exposes it via ngrok, and registers the webhook with Telegram.
---

# tg-local-testing

Start the wallet-bot locally so you can send real Telegram messages and watch the bot respond.

## Prerequisites

`.env` must have `BOT_TOKEN`, `WEBHOOK_SECRET`, `ALLOWED_TG_USER_IDS`, `GEMINI_API_KEY` filled in.
Docker image must be built: `docker compose build`.

## Steps

### 1 — Start the server

Remove any leftover container first (safe to run even if none exists):

```bash
docker rm -f wallet-bot-local 2>/dev/null || true
```

Then start:

```bash
docker run -d \
  --name wallet-bot-local \
  -p 8080:8080 \
  --env-file .env \
  -v "$(pwd)/src:/app/src" \
  wallet-bot:dev \
  uvicorn wallet_bot.main:app --host 0.0.0.0 --port 8080 --reload
```

**Why `docker run`, not `docker compose up`:** `docker-compose.yml` runs `bash` (for tests), not uvicorn, and doesn't bind port 8080 to the host.
**Why `--env-file .env`:** `docker-compose.yml` only forwards `GEMINI_API_KEY` — `BOT_TOKEN`, `WEBHOOK_SECRET`, `ALLOWED_TG_USER_IDS` would be missing otherwise.

Confirm startup:
```bash
docker logs wallet-bot-local
# Expected: INFO: Application startup complete.
```

### 2 — Start ngrok

```bash
ngrok http 8080 &
sleep 3
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels \
  | python3 -c "import sys,json; t=json.load(sys.stdin)['tunnels']; \
    print(next(x['public_url'] for x in t if x['proto']=='https'))")
echo $NGROK_URL
```

### 3 — Register the webhook

If ngrok is already running from a previous session, check whether re-registration is needed:

```bash
BOT_TOKEN=$(grep "^BOT_TOKEN=" .env | cut -d= -f2)
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | python3 -m json.tool
```

If the `url` in the response matches your current ngrok URL, skip to Step 4. Otherwise register:



```bash
BOT_TOKEN=$(grep "^BOT_TOKEN=" .env | cut -d= -f2)
WEBHOOK_SECRET=$(grep "^WEBHOOK_SECRET=" .env | cut -d= -f2)

curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
  -d "url=${NGROK_URL}/telegram/webhook" \
  -d "secret_token=${WEBHOOK_SECRET}"
# Expected: {"ok":true,"result":true,"description":"Webhook was set"}
```

**Webhook path is `/telegram/webhook`** — not `/webhook`. Verify in `src/wallet_bot/main.py` if in doubt.
**Never hardcode** `BOT_TOKEN` or `WEBHOOK_SECRET` in commands — always read from `.env`.

### 4 — Watch logs

```bash
docker logs -f wallet-bot-local
```

## Teardown

```bash
docker rm -f wallet-bot-local
pkill -f "ngrok http"
```

Re-register the webhook after every ngrok restart (new URL each time).

## Common mistakes

| Mistake | Fix |
|---|---|
| `docker compose up` → no response | Use `docker run` with `-p 8080:8080 --env-file .env` and explicit `uvicorn` command |
| Container name conflict error | Run `docker rm -f wallet-bot-local 2>/dev/null \|\| true` before Step 1 |
| 404 on webhook | Path must be `/telegram/webhook`, not `/webhook` |
| 403 from bot | Your Telegram user ID must be in `ALLOWED_TG_USER_IDS` in `.env` |
| Credentials in curl command | Always read from `.env` with `grep + cut` |
| ngrok URL changed | Re-run Step 3 after every ngrok restart |
