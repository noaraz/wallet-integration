"""Services — external integrations.

Each service encapsulates one external dependency and exposes a small
async interface consumable by handlers. No Telegram update shapes here.

Planned modules:
    telegram_client  (Phase 1) — sendMessage, downloadFile, setWebhook
    vision           (Phase 2) — Claude Vision extraction
    barcode          (Phase 3) — QR / Code128 / Aztec decoding
    wallet           (Phase 4) — build eventTicketObject, sign JWT, save URL
"""
