# Phase 01 — notes

## Library choices

- **FastAPI + uvicorn**: web framework. Cloud Run → `uvicorn wallet_bot.main:app --host 0.0.0.0 --port ${PORT}`.
- **python-telegram-bot v21 (thin PTB)**: import `Bot` for sending and `Update.de_json` for parsing only. Do NOT use the PTB `Application` or dispatcher — FastAPI owns the request lifecycle.
- **pydantic-settings v2**: `BaseSettings` with `SecretStr` for `bot_token` and `webhook_secret`. Comma-separated `ALLOWED_TG_USER_IDS` is parsed via `_EnvWithCommaIds` (subclass of `EnvSettingsSource`) to avoid pydantic-settings' automatic JSON-decode of list fields.

## Gotchas

### pydantic-settings v2 list fields

pydantic-settings v2 tries to JSON-decode env vars for list-typed fields before validators run. A plain `"123,456"` string is not valid JSON, so it raises `ValidationError` before any `field_validator(mode="before")` can touch it.

**Fix**: subclass `EnvSettingsSource`, override `prepare_field_value`, and split the string manually for `allowed_tg_user_ids`. Return the parsed `list[int]` directly.

### Command routing — strip @botname correctly

`msg.text.split("@")[0]` splits on the first `@` in the **entire message text**, breaking on any mention. The correct approach:

```python
parts = msg.text.split() if msg.text else []
cmd = parts[0].split("@")[0] if parts else None
```

### `assert` vs `if` guards in handlers

`assert update.effective_chat is not None` is stripped by Python's `-O` flag (used in some prod Docker images). Always use `if update.effective_chat is None: return`.

### `@lru_cache` on `get_settings`

Tests must call `get_settings.cache_clear()` both before **and** after (use `yield` fixture). The `test_env` fixture in `conftest.py` handles this automatically — all tests that boot the app should use `test_env`.

## Testing conventions

- `FakeClient(TelegramClientProtocol)` in `conftest.py` records `send_text` calls; declared as explicitly implementing the Protocol (`# type: ignore[misc]` required because Protocol subclassing is unusual).
- `app.dependency_overrides[get_client] = lambda: fake_client` in `test_app` fixture; cleared in `finally`.
- `LifespanManager(app)` wraps `AsyncClient` so lifespan events fire during tests.
- Handler unit tests call `Update.de_json(data, None)` directly — no HTTP stack needed.
