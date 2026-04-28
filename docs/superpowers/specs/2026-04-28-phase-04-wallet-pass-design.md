# Phase 04 — Google Wallet Pass: Design Spec

**Date:** 2026-04-28
**Status:** Approved

---

## Problem / Goal

Phases 00–03 shipped a Telegram bot that extracts structured ticket fields via Gemini Vision, lets the user review/edit via inline keyboard, and on approval logs the ticket JSON with a placeholder message. Phase 04 replaces that placeholder with a real Google Wallet `eventTicketObject` JWT and replies with an "Add to Google Wallet" inline URL button.

Multi-ticket bundling is in scope: the bot groups multiple tickets for the same event under one `eventTicketClass` and emits a single batch save URL when the user signals they are done.

---

## Key Decisions

| Topic | Decision |
|---|---|
| Barcode null handling | Omit `barcode` field entirely — it is optional per the Wallet API |
| Credentials (prod) | Cloud Run ADC — no JSON key, `google.auth.default()` |
| Credentials (local) | `WALLET_SA_JSON` env var (full SA JSON string) in `.env` |
| Bot reply format | Inline keyboard URL button ("Add to Google Wallet") |
| Multi-ticket scope | Full — deterministic class ID, dedup by barcode, batch save URL |
| Bundle trigger | Explicit "Get Wallet link" button — user signals "done" |
| Event matching | Exact (normalized) match on event_name + date → auto-group |
| Close match | Date matches, names differ after normalization → manual confirm |
| No match | Tell user, ignore ticket — session handles one bundle |

---

## Architecture

### New files

#### `src/wallet_bot/services/wallet_service.py` — `WalletService`
Stateless service. Builds `eventTicketObject` dicts from `ExtractedTicket`, signs a `savetowallet` JWT (RS256), returns a save URL.

JWT claims: `iss=sa_email`, `aud="google"`, `typ="savetowallet"`, `iat=now`, `origins=[...]`, `payload.eventTicketObjects=[...]`

Object fields:
- `id`: `{issuer_id}.{chat_id}_{slug(barcode_value or ticket_id or uuid4())[:32]}`
- `classId`: `{issuer_id}.{slug(event_name)}_{slug(date)}`
- `state`: `"ACTIVE"`
- `barcode`: included only when `barcode_value is not None`
- `ticketHolderName`, `eventName`, `venue`, `dateTime` from ticket fields

#### `src/wallet_bot/services/pass_store.py` — `PassStore`
In-memory dict `chat_id → PassBundle`. Mirrors `DraftStore` pattern.
Operations: `get`, `add_object`, `has_barcode`, `clear`.

#### `src/wallet_bot/models/wallet.py`
```python
class WalletObject(BaseModel):   # built object dict + barcode_value for dedup
class PassBundle(BaseModel):     # event_name, date, class_id, objects: list[WalletObject]
```

### Modified files

| File | Change |
|---|---|
| `config.py` | Add `wallet_issuer_id`, `wallet_sa_json: SecretStr | None`, `wallet_origins: list[str]` |
| `models/callback_ids.py` | Add `WALLET_GET_LINK`, `WALLET_BUNDLE_YES`, `WALLET_BUNDLE_NO` |
| `services/telegram_client.py` | Add `send_inline_button(chat_id, text, url)` |
| `handlers/callback_handler.py` | Replace placeholder with full bundle logic; handle new callbacks |
| `handlers/start_handler.py` | Explain multi-ticket bundle flow |
| `handlers/help_handler.py` | Explain multi-ticket bundle flow |
| `main.py` | Wire `WalletService` + `PassStore` via DI |

---

## User Flow (post-approval)

```
User taps APPROVE
        │
Build WalletObject from ticket
        │
PassStore.get(chat_id) is None?
  → Create bundle; reply "Saved ✓ for [event] · [date]. Send more tickets
    for this event or tap below." + [Get Wallet link] button
        │
Active bundle — normalized match (event_name + date)?
  → Duplicate barcode? → "Already in your bundle."
  → Add; reply "Added · N tickets for [event] · [date]." + [Get Wallet link] button
        │
Active bundle — date matches, name close but not identical?
  → "Is this the same event as [bundle event] on [date]?"
    + [Yes, add to bundle] [No, ignore] buttons
        │
Active bundle — no match?
  → "This ticket is for [event] on [date], but your bundle is for
    [bundle event]. Ticket ignored."

User taps WALLET_GET_LINK
  → WalletService.build_save_url(bundle.objects)
  → send_inline_button("Add to Google Wallet", save_url)
  → PassStore.clear(chat_id)

User taps WALLET_BUNDLE_YES → add pending object → "Added · N tickets" reply
User taps WALLET_BUNDLE_NO  → discard → "Ticket ignored."
```

**Normalization:** lowercase + strip punctuation + collapse whitespace.
**"Close" match:** date exact AND event names differ after normalization.

---

## Class / Object ID Scheme

- Class: `{issuer_id}.{slug(event_name)}_{slug(date)}`
- Object: `{issuer_id}.{chat_id}_{slug(barcode_value or ticket_id or uuid4())[:32]}`

---

## Dependencies to add

- `google-auth`
- `google-auth-httplib2`
- Use `google.auth.jwt` for encoding (avoids extra dep over PyJWT)

---

## Testing

- `tests/unit/services/test_wallet_service.py` — object dict building, JWT signing with test RSA key, save URL shape, barcode omitted when None
- `tests/unit/services/test_pass_store.py` — add/get/dedup/clear
- `tests/unit/handlers/test_callback_handler.py` (extend) — all bundle flow branches
- JWT validation via `wallet-jwt-validator` agent after first green build
- All 134 existing tests must stay green

---

## Out of Scope (Phase 04)

- Wallet API REST upsert (`eventTicketObject.insert`) — Phase 05
- Persistent pass storage (survives restarts) — Phase 05
- `wallet-pass-preview` skill — created during this phase via `/superpowers:writing-skills`
