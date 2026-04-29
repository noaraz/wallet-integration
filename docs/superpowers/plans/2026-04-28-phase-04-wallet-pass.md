# Phase 04 — Google Wallet Pass Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Design spec:** [`docs/superpowers/specs/2026-04-28-phase-04-wallet-pass-design.md`](../specs/2026-04-28-phase-04-wallet-pass-design.md)

**Goal:** Build Google Wallet `eventTicketObject` JWTs from approved tickets, reply with an "Add to Google Wallet" inline URL button, and support multi-ticket bundling (one pass save URL per event).

**Architecture:** New `WalletService` builds object dicts and signs `savetowallet` JWTs (RS256 via `google-auth`). New `PassStore` tracks per-chat bundles in memory. The callback handler's `APPROVE` branch gains full bundle logic. Three new callback IDs (`WALLET_GET_LINK`, `WALLET_BUNDLE_YES`, `WALLET_BUNDLE_NO`) drive the "get link" and manual-confirm flows.

**Tech Stack:** `google-auth` + `google.auth.jwt`, pydantic v2, python-telegram-bot `InlineKeyboardButton(url=…)`, FastAPI `app.state` DI.

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `src/wallet_bot/models/wallet.py` | `WalletObject`, `PassBundle` domain models |
| Create | `src/wallet_bot/services/pass_store.py` | In-memory bundle tracker (mirrors `DraftStore`) |
| Create | `src/wallet_bot/services/wallet_service.py` | Object builder + RS256 JWT signer → save URL |
| Create | `tests/unit/models/test_wallet.py` | Model unit tests |
| Create | `tests/unit/services/test_pass_store.py` | PassStore unit tests |
| Create | `tests/unit/services/test_wallet_service.py` | WalletService unit tests |
| Modify | `pyproject.toml` | Add `google-auth`, `google-auth-httplib2` |
| Modify | `src/wallet_bot/config.py` | Add `wallet_issuer_id`, `wallet_sa_json`, `wallet_origins` |
| Modify | `src/wallet_bot/models/callback_ids.py` | Add `WALLET_GET_LINK`, `WALLET_BUNDLE_YES`, `WALLET_BUNDLE_NO` |
| Modify | `src/wallet_bot/services/telegram_client.py` | Add `send_url_button` to Protocol + impl |
| Modify | `tests/conftest.py` | Add `send_url_button` to `FakeClient` |
| Modify | `src/wallet_bot/handlers/callback_handler.py` | Replace placeholder; handle wallet callbacks |
| Modify | `src/wallet_bot/handlers/start_handler.py` | Explain multi-ticket bundle flow |
| Modify | `src/wallet_bot/handlers/help_handler.py` | Explain multi-ticket bundle flow |
| Modify | `src/wallet_bot/main.py` | Wire `WalletService` + `PassStore` in lifespan |

---

## Chunk 1: Foundation — deps, models, config, callback IDs

### Task 1: Add google-auth dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add dependencies**

  In `pyproject.toml`, add to `dependencies`:
  ```toml
  "google-auth>=2.29",
  "google-auth-httplib2>=0.2",
  ```

- [ ] **Step 2: Rebuild the Docker image**

  ```bash
  docker compose build
  ```
  Expected: build succeeds, `google-auth` importable.

- [ ] **Step 3: Verify import**

  ```bash
  docker compose run --rm bot python -c "from google.auth import crypt, jwt as gjwt; print('ok')"
  ```
  Expected: `ok`

- [ ] **Step 4: Commit**

  ```bash
  git add pyproject.toml
  git commit -m "chore: add google-auth dependency for Wallet JWT signing"
  ```

---

### Task 2: Wallet domain models

**Files:**
- Create: `src/wallet_bot/models/wallet.py`
- Create: `tests/unit/models/test_wallet.py`

- [ ] **Step 1: Write the failing tests**

  `tests/unit/models/test_wallet.py`:
  ```python
  """Tests for wallet domain models."""
  from __future__ import annotations

  from wallet_bot.models.wallet import PassBundle, WalletObject


  def test_wallet_object_stores_dict_and_barcode() -> None:
      obj = WalletObject(
          object_dict={"id": "123.abc", "classId": "123.evt", "state": "ACTIVE"},
          class_id="123.evt",
          barcode_value="TICKET-001",
      )
      assert obj.object_dict["id"] == "123.abc"
      assert obj.barcode_value == "TICKET-001"


  def test_wallet_object_barcode_value_optional() -> None:
      obj = WalletObject(
          object_dict={"id": "123.abc", "classId": "123.evt", "state": "ACTIVE"},
          class_id="123.evt",
      )
      assert obj.barcode_value is None


  def test_pass_bundle_starts_empty() -> None:
      from datetime import UTC, datetime

      bundle = PassBundle(
          event_name="Rock Concert",
          date="2026-05-01",
          class_id="123.evt",
          created_at=datetime.now(tz=UTC),
      )
      assert bundle.objects == []
      assert bundle.pending_object is None


  def test_pass_bundle_has_barcode_true() -> None:
      from datetime import UTC, datetime

      obj = WalletObject(
          object_dict={}, class_id="123.evt", barcode_value="BARCODE-XYZ"
      )
      bundle = PassBundle(
          event_name="Concert",
          date="2026-05-01",
          class_id="123.evt",
          objects=[obj],
          created_at=datetime.now(tz=UTC),
      )
      assert bundle.has_barcode("BARCODE-XYZ") is True
      assert bundle.has_barcode("OTHER") is False


  def test_pass_bundle_has_barcode_ignores_none_values() -> None:
      from datetime import UTC, datetime

      obj = WalletObject(object_dict={}, class_id="123.evt", barcode_value=None)
      bundle = PassBundle(
          event_name="Concert",
          date="2026-05-01",
          class_id="123.evt",
          objects=[obj],
          created_at=datetime.now(tz=UTC),
      )
      assert bundle.has_barcode("anything") is False
  ```

- [ ] **Step 2: Run tests — expect failure**

  ```bash
  docker compose run --rm bot pytest tests/unit/models/test_wallet.py -v
  ```
  Expected: `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Implement models**

  `src/wallet_bot/models/wallet.py`:
  ```python
  """Domain models for Google Wallet pass building."""

  from __future__ import annotations

  from datetime import UTC, datetime

  from pydantic import BaseModel, Field


  class WalletObject(BaseModel):
      """A built eventTicketObject dict plus metadata for dedup."""

      object_dict: dict  # type: ignore[type-arg]
      class_id: str
      barcode_value: str | None = None


  class PassBundle(BaseModel):
      """Active per-chat bundle accumulating objects for one event."""

      event_name: str
      date: str
      class_id: str
      objects: list[WalletObject] = Field(default_factory=list)
      pending_object: WalletObject | None = None
      created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

      def has_barcode(self, barcode_value: str) -> bool:
          """Return True if any confirmed object in the bundle carries this barcode."""
          return any(
              obj.barcode_value == barcode_value
              for obj in self.objects
              if obj.barcode_value is not None
          )
  ```

- [ ] **Step 4: Run tests — expect pass**

  ```bash
  docker compose run --rm bot pytest tests/unit/models/test_wallet.py -v
  ```
  Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

  ```bash
  git add src/wallet_bot/models/wallet.py tests/unit/models/test_wallet.py
  git commit -m "feat: wallet domain models (WalletObject, PassBundle)"
  ```

---

### Task 3: Config — wallet fields

**Files:**
- Modify: `src/wallet_bot/config.py`

> Wallet fields are optional with safe defaults so existing tests keep passing. `WalletService` raises `RuntimeError` if called when `wallet_sa_json` is unset (guarded in main.py).

- [ ] **Step 1: Write the failing test**

  In `tests/unit/test_config.py`, add at the end:
  ```python
  def test_wallet_config_defaults(monkeypatch) -> None:
      """Wallet fields are optional — existing envs don't break."""
      monkeypatch.setenv("BOT_TOKEN", "123:fake")
      monkeypatch.setenv("WEBHOOK_SECRET", "s")
      monkeypatch.setenv("ALLOWED_TG_USER_IDS", "1")
      monkeypatch.setenv("GEMINI_API_KEY", "g")
      from wallet_bot.config import Settings

      s = Settings()
      assert s.wallet_issuer_id == ""
      assert s.wallet_sa_json is None
      assert s.wallet_origins == []


  def test_wallet_config_from_env(monkeypatch) -> None:
      monkeypatch.setenv("BOT_TOKEN", "123:fake")
      monkeypatch.setenv("WEBHOOK_SECRET", "s")
      monkeypatch.setenv("ALLOWED_TG_USER_IDS", "1")
      monkeypatch.setenv("GEMINI_API_KEY", "g")
      monkeypatch.setenv("WALLET_ISSUER_ID", "3388000000012345678")
      monkeypatch.setenv("WALLET_SA_JSON", '{"type":"service_account"}')
      monkeypatch.setenv("WALLET_ORIGINS", "https://example.com,https://bot.example.com")
      from wallet_bot.config import Settings

      s = Settings()
      assert s.wallet_issuer_id == "3388000000012345678"
      assert s.wallet_sa_json is not None
      assert s.wallet_origins == ["https://example.com", "https://bot.example.com"]
  ```

- [ ] **Step 2: Run — expect failure**

  ```bash
  docker compose run --rm bot pytest tests/unit/test_config.py::test_wallet_config_defaults tests/unit/test_config.py::test_wallet_config_from_env -v
  ```

- [ ] **Step 3: Implement**

  In `src/wallet_bot/config.py`, add to `Settings` after `gemini_model`:
  ```python
  wallet_issuer_id: str = ""  # env: WALLET_ISSUER_ID
  wallet_sa_json: SecretStr | None = None  # env: WALLET_SA_JSON (full SA JSON; local dev only)
  wallet_origins: list[str] = []  # env: WALLET_ORIGINS (comma-separated)
  ```

  Also update `_EnvWithCommaIds.prepare_field_value` to handle `wallet_origins`:
  ```python
  if field_name in {"allowed_tg_user_ids"} and isinstance(value, str):
      return _split_ids(value)
  if field_name == "wallet_origins" and isinstance(value, str):
      return [x.strip() for x in value.split(",") if x.strip()]
  return super().prepare_field_value(field_name, field, value, value_is_complex)
  ```

- [ ] **Step 4: Run — expect pass**

  ```bash
  docker compose run --rm bot pytest tests/unit/test_config.py -v
  ```

- [ ] **Step 5: Commit**

  ```bash
  git add src/wallet_bot/config.py tests/unit/test_config.py
  git commit -m "feat: add wallet config fields (wallet_issuer_id, wallet_sa_json, wallet_origins)"
  ```

---

### Task 4: Callback IDs — wallet actions

**Files:**
- Modify: `src/wallet_bot/models/callback_ids.py`

- [ ] **Step 1: Write the failing test**

  In `tests/unit/models/test_callback_ids.py`, add:
  ```python
  def test_wallet_callback_ids_are_whitelisted() -> None:
      from wallet_bot.models.callback_ids import CallbackId, parse_callback_id

      assert parse_callback_id("wallet_get_link") is CallbackId.WALLET_GET_LINK
      assert parse_callback_id("wallet_bundle_yes") is CallbackId.WALLET_BUNDLE_YES
      assert parse_callback_id("wallet_bundle_no") is CallbackId.WALLET_BUNDLE_NO
  ```

- [ ] **Step 2: Run — expect failure**

  ```bash
  docker compose run --rm bot pytest tests/unit/models/test_callback_ids.py -v
  ```

- [ ] **Step 3: Implement**

  In `src/wallet_bot/models/callback_ids.py`, add to `CallbackId`:
  ```python
  WALLET_GET_LINK = "wallet_get_link"
  WALLET_BUNDLE_YES = "wallet_bundle_yes"
  WALLET_BUNDLE_NO = "wallet_bundle_no"
  ```

- [ ] **Step 4: Run — expect pass**

  ```bash
  docker compose run --rm bot pytest tests/unit/models/test_callback_ids.py -v
  ```

- [ ] **Step 5: Commit**

  ```bash
  git add src/wallet_bot/models/callback_ids.py tests/unit/models/test_callback_ids.py
  git commit -m "feat: add WALLET_GET_LINK, WALLET_BUNDLE_YES, WALLET_BUNDLE_NO callback IDs"
  ```

---

## Chunk 2: PassStore + WalletService

### Task 5: PassStore

**Files:**
- Create: `src/wallet_bot/services/pass_store.py`
- Create: `tests/unit/services/test_pass_store.py`

- [ ] **Step 1: Write the failing tests**

  `tests/unit/services/test_pass_store.py`:
  ```python
  """Tests for PassStore."""
  from __future__ import annotations

  import pytest

  from wallet_bot.models.wallet import PassBundle, WalletObject
  from wallet_bot.services.pass_store import PassStore


  def _obj(barcode: str | None = "B1") -> WalletObject:
      return WalletObject(object_dict={"id": "x"}, class_id="c", barcode_value=barcode)


  def _bundle(**kw) -> PassBundle:
      from datetime import UTC, datetime

      return PassBundle(
          event_name=kw.get("event_name", "Concert"),
          date=kw.get("date", "2026-05-01"),
          class_id=kw.get("class_id", "123.evt"),
          created_at=datetime.now(tz=UTC),
      )


  async def test_get_returns_none_for_unknown_chat() -> None:
      store = PassStore()
      assert await store.get(999) is None


  async def test_put_and_get_roundtrip() -> None:
      store = PassStore()
      bundle = _bundle()
      await store.put(42, bundle)
      result = await store.get(42)
      assert result is not None
      assert result.event_name == "Concert"


  async def test_add_object_appends() -> None:
      store = PassStore()
      await store.put(42, _bundle())
      await store.add_object(42, _obj("B1"))
      await store.add_object(42, _obj("B2"))
      bundle = await store.get(42)
      assert bundle is not None
      assert len(bundle.objects) == 2


  async def test_has_barcode_true_and_false() -> None:
      store = PassStore()
      await store.put(42, _bundle())
      await store.add_object(42, _obj("B1"))
      assert await store.has_barcode(42, "B1") is True
      assert await store.has_barcode(42, "OTHER") is False


  async def test_has_barcode_false_when_no_bundle() -> None:
      store = PassStore()
      assert await store.has_barcode(99, "anything") is False


  async def test_set_pending_and_confirm() -> None:
      store = PassStore()
      await store.put(42, _bundle())
      pending = _obj("P1")
      await store.set_pending(42, pending)
      bundle = await store.get(42)
      assert bundle is not None
      assert bundle.pending_object is not None
      assert bundle.pending_object.barcode_value == "P1"
      assert len(bundle.objects) == 0

      await store.confirm_pending(42)
      bundle = await store.get(42)
      assert bundle is not None
      assert bundle.pending_object is None
      assert len(bundle.objects) == 1
      assert bundle.objects[0].barcode_value == "P1"


  async def test_discard_pending() -> None:
      store = PassStore()
      await store.put(42, _bundle())
      await store.set_pending(42, _obj("P1"))
      await store.discard_pending(42)
      bundle = await store.get(42)
      assert bundle is not None
      assert bundle.pending_object is None
      assert len(bundle.objects) == 0


  async def test_clear_removes_bundle() -> None:
      store = PassStore()
      await store.put(42, _bundle())
      await store.clear(42)
      assert await store.get(42) is None


  async def test_add_object_noop_when_no_bundle() -> None:
      store = PassStore()
      await store.add_object(99, _obj())  # no crash
      assert await store.get(99) is None
  ```

- [ ] **Step 2: Run — expect failure**

  ```bash
  docker compose run --rm bot pytest tests/unit/services/test_pass_store.py -v
  ```

- [ ] **Step 3: Implement**

  `src/wallet_bot/services/pass_store.py`:
  ```python
  """In-memory per-chat pass bundle store.

  Tracks approved WalletObjects grouped by event for the multi-ticket bundle
  flow. Mirrors DraftStore's locking pattern. No TTL in Phase 04 — the bundle
  is cleared explicitly when the user taps "Get Wallet link".
  """

  from __future__ import annotations

  import asyncio

  from wallet_bot.models.wallet import PassBundle, WalletObject


  class PassStore:
      def __init__(self) -> None:
          self._data: dict[int, PassBundle] = {}
          self._locks: dict[int, asyncio.Lock] = {}

      def _lock_for(self, chat_id: int) -> asyncio.Lock:
          if chat_id not in self._locks:
              self._locks[chat_id] = asyncio.Lock()
          return self._locks[chat_id]

      async def get(self, chat_id: int) -> PassBundle | None:
          async with self._lock_for(chat_id):
              return self._data.get(chat_id)

      async def put(self, chat_id: int, bundle: PassBundle) -> None:
          async with self._lock_for(chat_id):
              self._data[chat_id] = bundle

      async def add_object(self, chat_id: int, obj: WalletObject) -> None:
          async with self._lock_for(chat_id):
              bundle = self._data.get(chat_id)
              if bundle is None:
                  return
              self._data[chat_id] = bundle.model_copy(
                  update={"objects": [*bundle.objects, obj]}
              )

      async def has_barcode(self, chat_id: int, barcode_value: str) -> bool:
          async with self._lock_for(chat_id):
              bundle = self._data.get(chat_id)
              if bundle is None:
                  return False
              return bundle.has_barcode(barcode_value)

      async def set_pending(self, chat_id: int, obj: WalletObject) -> None:
          async with self._lock_for(chat_id):
              bundle = self._data.get(chat_id)
              if bundle is None:
                  return
              self._data[chat_id] = bundle.model_copy(update={"pending_object": obj})

      async def confirm_pending(self, chat_id: int) -> None:
          async with self._lock_for(chat_id):
              bundle = self._data.get(chat_id)
              if bundle is None or bundle.pending_object is None:
                  return
              self._data[chat_id] = bundle.model_copy(
                  update={
                      "objects": [*bundle.objects, bundle.pending_object],
                      "pending_object": None,
                  }
              )

      async def discard_pending(self, chat_id: int) -> None:
          async with self._lock_for(chat_id):
              bundle = self._data.get(chat_id)
              if bundle is None:
                  return
              self._data[chat_id] = bundle.model_copy(update={"pending_object": None})

      async def clear(self, chat_id: int) -> None:
          async with self._lock_for(chat_id):
              self._data.pop(chat_id, None)


  _default_pass_store = PassStore()


  def get_default_pass_store() -> PassStore:
      return _default_pass_store
  ```

- [ ] **Step 4: Run — expect pass**

  ```bash
  docker compose run --rm bot pytest tests/unit/services/test_pass_store.py -v
  ```

- [ ] **Step 5: Commit**

  ```bash
  git add src/wallet_bot/services/pass_store.py tests/unit/services/test_pass_store.py
  git commit -m "feat: PassStore — in-memory per-chat bundle tracker"
  ```

---

### Task 6: WalletService — object builder

**Files:**
- Create: `src/wallet_bot/services/wallet_service.py` (partial)
- Create: `tests/unit/services/test_wallet_service.py` (partial)

> We build in two steps: object builder first (no JWT signing), then the signer in Task 7.

- [ ] **Step 1: Write the failing tests**

  `tests/unit/services/test_wallet_service.py`:
  ```python
  """Tests for WalletService."""
  from __future__ import annotations

  import json

  import pytest

  from wallet_bot.models.ticket import BarcodeResult, ExtractedTicket
  from wallet_bot.models.wallet import WalletObject


  # ── helpers ──────────────────────────────────────────────────────────────────

  def _make_sa_json() -> str:
      """Generate a minimal fake service-account JSON with a real RSA key."""
      from cryptography.hazmat.primitives import serialization
      from cryptography.hazmat.primitives.asymmetric import rsa

      private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
      pem = private_key.private_bytes(
          encoding=serialization.Encoding.PEM,
          format=serialization.PrivateFormat.PKCS8,
          encryption_algorithm=serialization.NoEncryption(),
      ).decode()
      return json.dumps(
          {
              "type": "service_account",
              "project_id": "test",
              "private_key_id": "k1",
              "private_key": pem,
              "client_email": "bot@test.iam.gserviceaccount.com",
              "client_id": "1",
              "token_uri": "https://oauth2.googleapis.com/token",
          }
      )


  ISSUER_ID = "3388000000012345678"


  @pytest.fixture
  def svc():
      from wallet_bot.services.wallet_service import WalletService

      return WalletService(
          issuer_id=ISSUER_ID,
          sa_json=_make_sa_json(),
          origins=["https://example.com"],
      )


  # ── build_object tests ────────────────────────────────────────────────────────

  def test_build_object_returns_wallet_object(svc) -> None:
      ticket = ExtractedTicket(event_name="Rock Fest", date="2026-06-01")
      obj = svc.build_object(chat_id=42, ticket=ticket)
      assert isinstance(obj, WalletObject)


  def test_build_object_id_starts_with_issuer(svc) -> None:
      ticket = ExtractedTicket(event_name="Rock Fest", date="2026-06-01")
      obj = svc.build_object(chat_id=42, ticket=ticket)
      assert obj.object_dict["id"].startswith(ISSUER_ID + ".")


  def test_build_object_class_id_is_deterministic(svc) -> None:
      ticket = ExtractedTicket(event_name="Rock Fest", date="2026-06-01")
      obj1 = svc.build_object(chat_id=42, ticket=ticket)
      obj2 = svc.build_object(chat_id=42, ticket=ticket)
      assert obj1.class_id == obj2.class_id
      assert obj1.object_dict["classId"] == obj2.object_dict["classId"]


  def test_build_object_includes_barcode_when_present(svc) -> None:
      ticket = ExtractedTicket(
          event_name="Rock Fest",
          date="2026-06-01",
          barcode=BarcodeResult(barcode_type="QR_CODE", barcode_value="TICKET123"),
      )
      obj = svc.build_object(chat_id=42, ticket=ticket)
      assert "barcode" in obj.object_dict
      assert obj.object_dict["barcode"]["value"] == "TICKET123"
      assert obj.barcode_value == "TICKET123"


  def test_build_object_omits_barcode_when_value_is_none(svc) -> None:
      ticket = ExtractedTicket(
          event_name="Rock Fest",
          date="2026-06-01",
          barcode=BarcodeResult(barcode_type="QR_CODE", barcode_value=None),
      )
      obj = svc.build_object(chat_id=42, ticket=ticket)
      assert "barcode" not in obj.object_dict
      assert obj.barcode_value is None


  def test_build_object_omits_barcode_when_no_barcode_field(svc) -> None:
      ticket = ExtractedTicket(event_name="Concert", date="2026-06-01")
      obj = svc.build_object(chat_id=42, ticket=ticket)
      assert "barcode" not in obj.object_dict


  def test_build_object_state_is_active(svc) -> None:
      ticket = ExtractedTicket(event_name="Concert", date="2026-06-01")
      obj = svc.build_object(chat_id=42, ticket=ticket)
      assert obj.object_dict["state"] == "ACTIVE"


  def test_build_object_object_id_stable_with_barcode(svc) -> None:
      """Same barcode → same object ID (deterministic, enables dedup at Wallet API)."""
      ticket = ExtractedTicket(
          event_name="Concert",
          date="2026-06-01",
          barcode=BarcodeResult(barcode_type="QR_CODE", barcode_value="BC-999"),
      )
      id1 = svc.build_object(chat_id=42, ticket=ticket).object_dict["id"]
      id2 = svc.build_object(chat_id=42, ticket=ticket).object_dict["id"]
      assert id1 == id2


  def test_build_object_different_chat_ids_differ(svc) -> None:
      ticket = ExtractedTicket(
          event_name="Concert",
          date="2026-06-01",
          barcode=BarcodeResult(barcode_type="QR_CODE", barcode_value="BC-999"),
      )
      id1 = svc.build_object(chat_id=42, ticket=ticket).object_dict["id"]
      id2 = svc.build_object(chat_id=99, ticket=ticket).object_dict["id"]
      assert id1 != id2
  ```

- [ ] **Step 2: Run — expect failure**

  ```bash
  docker compose run --rm bot pytest tests/unit/services/test_wallet_service.py -v
  ```

- [ ] **Step 3: Implement object builder (no signing yet)**

  `src/wallet_bot/services/wallet_service.py`:
  ```python
  """Google Wallet pass builder and JWT signer.

  Local dev: pass ``sa_json`` (full service-account JSON string).
  Prod (Phase 07+): migrate to ADC / IAM signing; ``sa_json`` can be None.
  """

  from __future__ import annotations

  import hashlib
  import json
  import time

  from google.auth import crypt, jwt as google_jwt

  from wallet_bot.models.ticket import ExtractedTicket
  from wallet_bot.models.wallet import PassBundle, WalletObject

  _BARCODE_TYPE_MAP: dict[str, str] = {
      "QR_CODE": "QR_CODE",
      "QR": "QR_CODE",
      "CODE_128": "CODE_128",
      "BARCODE_128": "CODE_128",
      "CODE128": "CODE_128",
      "AZTEC": "AZTEC",
      "PDF_417": "PDF_417",
      "PDF417": "PDF_417",
  }
  _DEFAULT_BARCODE_TYPE = "QR_CODE"


  def _stable_hash(text: str) -> str:
      return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


  def _map_barcode_type(raw: str) -> str:
      return _BARCODE_TYPE_MAP.get(raw.upper(), _DEFAULT_BARCODE_TYPE)


  class WalletService:
      def __init__(
          self,
          issuer_id: str,
          sa_json: str,
          origins: list[str],
      ) -> None:
          info = json.loads(sa_json)
          self._signer = crypt.RSASigner.from_service_account_info(info)
          self._issuer_id = issuer_id
          self._issuer_email: str = info["client_email"]
          self._origins = origins

      def build_object(self, chat_id: int, ticket: ExtractedTicket) -> WalletObject:
          """Build an eventTicketObject dict from an approved ticket."""
          class_id = self._class_id(ticket)
          object_id = self._object_id(chat_id, ticket)

          obj: dict = {  # type: ignore[type-arg]
              "id": object_id,
              "classId": class_id,
              "state": "ACTIVE",
          }

          if ticket.event_name:
              obj["eventName"] = {
                  "defaultValue": {"language": "iw", "value": ticket.event_name}
              }
          if ticket.holder_name:
              obj["ticketHolderName"] = ticket.holder_name
          if ticket.venue:
              obj["venue"] = {
                  "name": {"defaultValue": {"language": "iw", "value": ticket.venue}}
              }
          if ticket.date or ticket.time:
              date_str = ticket.date or ""
              time_str = ticket.time or ""
              obj["dateTime"] = f"{date_str} {time_str}".strip()
          if ticket.section:
              obj["seatInfo"] = {
                  "section": {"defaultValue": {"language": "iw", "value": ticket.section}}
              }

          # Barcode: omit entirely when value is absent — it is an optional field.
          if ticket.barcode and ticket.barcode.barcode_value:
              obj["barcode"] = {
                  "type": _map_barcode_type(ticket.barcode.barcode_type),
                  "value": ticket.barcode.barcode_value,
              }

          barcode_value = (
              ticket.barcode.barcode_value
              if ticket.barcode and ticket.barcode.barcode_value
              else None
          )
          return WalletObject(
              object_dict=obj,
              class_id=class_id,
              barcode_value=barcode_value,
          )

      def _class_id(self, ticket: ExtractedTicket) -> str:
          key = f"{ticket.event_name or ''}|{ticket.date or ''}"
          return f"{self._issuer_id}.event_{_stable_hash(key)}"

      def _object_id(self, chat_id: int, ticket: ExtractedTicket) -> str:
          raw = (
              (ticket.barcode.barcode_value if ticket.barcode else None)
              or ticket.ticket_id
          )
          if raw:
              suffix = _stable_hash(raw)
          else:
              import uuid
              suffix = uuid.uuid4().hex[:20]
          return f"{self._issuer_id}.{chat_id}_{suffix}"

      def build_save_url(self, objects: list[WalletObject]) -> str:
          """Sign a savetowallet JWT and return the Google Wallet save URL."""
          payload = {
              "iss": self._issuer_email,
              "aud": "google",
              "typ": "savetowallet",
              "iat": int(time.time()),
              "origins": self._origins,
              "payload": {
                  "eventTicketObjects": [obj.object_dict for obj in objects],
              },
          }
          token: bytes = google_jwt.encode(self._signer, payload)
          return f"https://pay.google.com/gp/v/save/{token.decode()}"
  ```

- [ ] **Step 4: Run — expect pass**

  ```bash
  docker compose run --rm bot pytest tests/unit/services/test_wallet_service.py -v
  ```

- [ ] **Step 5: Commit**

  ```bash
  git add src/wallet_bot/services/wallet_service.py tests/unit/services/test_wallet_service.py
  git commit -m "feat: WalletService — object builder and RS256 JWT signer"
  ```

---

### Task 7: WalletService — JWT signer tests

**Files:**
- Modify: `tests/unit/services/test_wallet_service.py`

> The signer is already implemented in Task 6. These tests verify JWT correctness.

- [ ] **Step 1: Add JWT tests**

  Append to `tests/unit/services/test_wallet_service.py`:
  ```python
  # ── build_save_url tests ─────────────────────────────────────────────────────

  def test_build_save_url_format(svc) -> None:
      ticket = ExtractedTicket(event_name="Concert", date="2026-06-01")
      obj = svc.build_object(chat_id=42, ticket=ticket)
      url = svc.build_save_url([obj])
      assert url.startswith("https://pay.google.com/gp/v/save/")


  def test_build_save_url_jwt_has_three_parts(svc) -> None:
      ticket = ExtractedTicket(event_name="Concert", date="2026-06-01")
      obj = svc.build_object(chat_id=42, ticket=ticket)
      url = svc.build_save_url([obj])
      jwt_part = url.removeprefix("https://pay.google.com/gp/v/save/")
      assert jwt_part.count(".") == 2


  def test_build_save_url_payload_claims(svc) -> None:
      import base64

      ticket = ExtractedTicket(event_name="Concert", date="2026-06-01")
      obj = svc.build_object(chat_id=42, ticket=ticket)
      url = svc.build_save_url([obj])
      jwt_part = url.removeprefix("https://pay.google.com/gp/v/save/")
      _, payload_b64, _ = jwt_part.split(".")
      # Add padding
      payload_b64 += "=" * (-len(payload_b64) % 4)
      payload = json.loads(base64.urlsafe_b64decode(payload_b64))
      assert payload["aud"] == "google"
      assert payload["typ"] == "savetowallet"
      assert payload["iss"] == "bot@test.iam.gserviceaccount.com"
      assert "iat" in payload
      assert "payload" in payload
      assert "eventTicketObjects" in payload["payload"]
      assert len(payload["payload"]["eventTicketObjects"]) == 1


  def test_build_save_url_multiple_objects(svc) -> None:
      import base64

      ticket1 = ExtractedTicket(
          event_name="Concert",
          date="2026-06-01",
          barcode=BarcodeResult(barcode_type="QR_CODE", barcode_value="BC1"),
      )
      ticket2 = ExtractedTicket(
          event_name="Concert",
          date="2026-06-01",
          barcode=BarcodeResult(barcode_type="QR_CODE", barcode_value="BC2"),
      )
      objects = [
          svc.build_object(chat_id=42, ticket=ticket1),
          svc.build_object(chat_id=42, ticket=ticket2),
      ]
      url = svc.build_save_url(objects)
      jwt_part = url.removeprefix("https://pay.google.com/gp/v/save/")
      _, payload_b64, _ = jwt_part.split(".")
      payload_b64 += "=" * (-len(payload_b64) % 4)
      payload = json.loads(base64.urlsafe_b64decode(payload_b64))
      assert len(payload["payload"]["eventTicketObjects"]) == 2
  ```

- [ ] **Step 2: Run — expect pass (already implemented)**

  ```bash
  docker compose run --rm bot pytest tests/unit/services/test_wallet_service.py -v
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add tests/unit/services/test_wallet_service.py
  git commit -m "test: JWT signer tests for WalletService.build_save_url"
  ```

---

### Task 8: TelegramClient — send_url_button

**Files:**
- Modify: `src/wallet_bot/services/telegram_client.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write the failing test**

  In `tests/unit/services/test_telegram_client.py`, add:
  ```python
  async def test_fake_client_records_url_button() -> None:
      """FakeClient.send_url_button appends to sent_url_buttons."""
      from tests.conftest import FakeClient

      client = FakeClient()
      await client.send_url_button(42, "Ready!", "Add to Wallet", "https://pay.google.com/x")
      assert client.sent_url_buttons == [
          (42, "Ready!", "Add to Wallet", "https://pay.google.com/x")
      ]
  ```

- [ ] **Step 2: Run — expect failure**

  ```bash
  docker compose run --rm bot pytest tests/unit/services/test_telegram_client.py -v -k test_fake_client_records_url_button
  ```

- [ ] **Step 3: Add to Protocol and TelegramClient**

  In `src/wallet_bot/services/telegram_client.py`:

  Add to `TelegramClientProtocol` after `send_chat_action`:
  ```python
  async def send_url_button(
      self, chat_id: int, text: str, button_text: str, url: str
  ) -> None: ...
  ```

  Add to `TelegramClient` after `send_chat_action`:
  ```python
  async def send_url_button(
      self, chat_id: int, text: str, button_text: str, url: str
  ) -> None:
      markup = InlineKeyboardMarkup(
          [[InlineKeyboardButton(text=button_text, url=url)]]
      )
      await self._bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)
  ```

  In `tests/conftest.py`, add to `FakeClient.__init__`:
  ```python
  self.sent_url_buttons: list[tuple[int, str, str, str]] = []
  ```

  Add method to `FakeClient`:
  ```python
  async def send_url_button(
      self, chat_id: int, text: str, button_text: str, url: str
  ) -> None:
      self.sent_url_buttons.append((chat_id, text, button_text, url))
  ```

- [ ] **Step 4: Run — expect pass**

  ```bash
  docker compose run --rm bot pytest tests/unit/services/test_telegram_client.py -v
  ```

- [ ] **Step 5: Commit**

  ```bash
  git add src/wallet_bot/services/telegram_client.py tests/conftest.py tests/unit/services/test_telegram_client.py
  git commit -m "feat: add send_url_button to TelegramClient and FakeClient"
  ```

---

## Chunk 3: Handler + Wiring + UX

### Task 9: Callback handler — bundle flow

**Files:**
- Modify: `src/wallet_bot/handlers/callback_handler.py`
- Modify: `tests/unit/handlers/test_callback_handler.py`

> This is the largest task. Write all tests first, then implement.

- [ ] **Step 1: Write the failing tests**

  Append to `tests/unit/handlers/test_callback_handler.py`:
  ```python
  # ── wallet bundle flow fixtures ───────────────────────────────────────────────

  import json as _json

  import pytest

  from wallet_bot.models.callback_ids import CallbackId
  from wallet_bot.models.ticket import BarcodeResult, ExtractedTicket
  from wallet_bot.models.wallet import PassBundle, WalletObject
  from wallet_bot.services.pass_store import PassStore


  def _approved_ticket(
      event: str = "Rock Concert",
      date: str = "2026-06-01",
      barcode: str | None = "BC001",
  ) -> ExtractedTicket:
      return ExtractedTicket(
          event_name=event,
          date=date,
          barcode=BarcodeResult(barcode_type="QR_CODE", barcode_value=barcode)
          if barcode
          else None,
      )


  class FakeWalletService:
      def __init__(self) -> None:
          self._counter = 0

      def build_object(self, chat_id: int, ticket: ExtractedTicket) -> WalletObject:
          self._counter += 1
          return WalletObject(
              object_dict={
                  "id": f"123.{chat_id}_{self._counter}",
                  "classId": "123.evt",
                  "state": "ACTIVE",
              },
              class_id="123.evt",
              barcode_value=ticket.barcode.barcode_value if ticket.barcode else None,
          )

      def build_save_url(self, objects: list[WalletObject]) -> str:
          return f"https://pay.google.com/gp/v/save/fake_jwt_{len(objects)}"


  @pytest.fixture
  def pass_store() -> PassStore:
      return PassStore()


  @pytest.fixture
  def wallet_svc() -> FakeWalletService:
      return FakeWalletService()


  # helper: push a ticket through approve in the handler
  async def _approve(chat_id, client, store, pass_store, wallet_svc, ticket):
      from wallet_bot.handlers.callback_handler import handle_callback

      await store.put(
          chat_id,
          __import__(
              "wallet_bot.models.ticket", fromlist=["DraftState"]
          ).DraftState(
              ticket=ticket,
              message_id=1,
              created_at=__import__("datetime").datetime.now(
                  tz=__import__("datetime").timezone.utc
              ),
          ),
      )
      await handle_callback(
          chat_id=chat_id,
          client=client,
          callback_query_id="q1",
          callback_data=CallbackId.APPROVE,
          store=store,
          pass_store=pass_store,
          wallet_service=wallet_svc,
      )


  # ── APPROVE → new bundle ──────────────────────────────────────────────────────

  async def test_approve_creates_bundle_and_sends_get_link_button(
      fake_client, store, pass_store, wallet_svc
  ) -> None:
      await _approve(42, fake_client, store, pass_store, wallet_svc, _approved_ticket())
      bundle = await pass_store.get(42)
      assert bundle is not None
      assert len(bundle.objects) == 1
      # Should send a keyboard message with "Get Wallet link" button
      assert len(fake_client.sent_with_keyboard) == 1
      rows = fake_client.sent_with_keyboard[0][2]
      assert rows[0][0].callback_data == CallbackId.WALLET_GET_LINK


  # ── APPROVE → exact match → add to bundle ────────────────────────────────────

  async def test_approve_exact_match_adds_to_bundle(
      fake_client, store, pass_store, wallet_svc
  ) -> None:
      ticket1 = _approved_ticket(barcode="BC001")
      ticket2 = _approved_ticket(barcode="BC002")
      await _approve(42, fake_client, store, pass_store, wallet_svc, ticket1)
      fake_client.sent_with_keyboard.clear()
      await _approve(42, fake_client, store, pass_store, wallet_svc, ticket2)
      bundle = await pass_store.get(42)
      assert bundle is not None
      assert len(bundle.objects) == 2
      assert "2 tickets" in fake_client.sent_with_keyboard[0][1]


  # ── APPROVE → duplicate barcode ───────────────────────────────────────────────

  async def test_approve_duplicate_barcode_ignored(
      fake_client, store, pass_store, wallet_svc
  ) -> None:
      ticket = _approved_ticket(barcode="BC001")
      await _approve(42, fake_client, store, pass_store, wallet_svc, ticket)
      fake_client.sent.clear()
      await _approve(42, fake_client, store, pass_store, wallet_svc, ticket)
      bundle = await pass_store.get(42)
      assert bundle is not None
      assert len(bundle.objects) == 1  # not duplicated
      assert any("already" in t.lower() for _, t in fake_client.sent)


  # ── APPROVE → close match → manual confirm ───────────────────────────────────

  async def test_approve_close_match_asks_user(
      fake_client, store, pass_store, wallet_svc
  ) -> None:
      ticket1 = _approved_ticket(event="Rock Concert", date="2026-06-01")
      ticket2 = _approved_ticket(event="Rock Concert Festival", date="2026-06-01", barcode="BC002")
      await _approve(42, fake_client, store, pass_store, wallet_svc, ticket1)
      fake_client.sent_with_keyboard.clear()
      await _approve(42, fake_client, store, pass_store, wallet_svc, ticket2)
      # Should ask for confirmation, not add to bundle yet
      bundle = await pass_store.get(42)
      assert bundle is not None
      assert len(bundle.objects) == 1  # still only 1 confirmed
      assert bundle.pending_object is not None
      rows = fake_client.sent_with_keyboard[0][2]
      cb_ids = {btn.callback_data for row in rows for btn in row}
      assert CallbackId.WALLET_BUNDLE_YES in cb_ids
      assert CallbackId.WALLET_BUNDLE_NO in cb_ids


  # ── APPROVE → no match ────────────────────────────────────────────────────────

  async def test_approve_no_match_ignores_ticket(
      fake_client, store, pass_store, wallet_svc
  ) -> None:
      ticket1 = _approved_ticket(event="Rock Concert", date="2026-06-01")
      ticket2 = _approved_ticket(event="Jazz Night", date="2026-07-15", barcode="BC002")
      await _approve(42, fake_client, store, pass_store, wallet_svc, ticket1)
      fake_client.sent.clear()
      await _approve(42, fake_client, store, pass_store, wallet_svc, ticket2)
      bundle = await pass_store.get(42)
      assert bundle is not None
      assert len(bundle.objects) == 1  # unchanged
      assert any("ignored" in t.lower() for _, t in fake_client.sent)


  # ── WALLET_GET_LINK ───────────────────────────────────────────────────────────

  async def test_wallet_get_link_sends_url_button_and_clears_bundle(
      fake_client, store, pass_store, wallet_svc
  ) -> None:
      from wallet_bot.handlers.callback_handler import handle_callback

      await _approve(42, fake_client, store, pass_store, wallet_svc, _approved_ticket())
      fake_client.sent_url_buttons.clear()
      await handle_callback(
          chat_id=42,
          client=fake_client,
          callback_query_id="q2",
          callback_data=CallbackId.WALLET_GET_LINK,
          store=store,
          pass_store=pass_store,
          wallet_service=wallet_svc,
      )
      assert len(fake_client.sent_url_buttons) == 1
      _, _, btn_text, url = fake_client.sent_url_buttons[0]
      assert "wallet" in btn_text.lower()
      assert url.startswith("https://pay.google.com/gp/v/save/")
      assert await pass_store.get(42) is None  # cleared


  # ── WALLET_BUNDLE_YES ─────────────────────────────────────────────────────────

  async def test_wallet_bundle_yes_confirms_pending(
      fake_client, store, pass_store, wallet_svc
  ) -> None:
      from wallet_bot.handlers.callback_handler import handle_callback

      ticket1 = _approved_ticket(event="Rock Concert", date="2026-06-01")
      ticket2 = _approved_ticket(
          event="Rock Concert Festival", date="2026-06-01", barcode="BC002"
      )
      await _approve(42, fake_client, store, pass_store, wallet_svc, ticket1)
      await _approve(42, fake_client, store, pass_store, wallet_svc, ticket2)
      assert (await pass_store.get(42)).pending_object is not None

      fake_client.sent_with_keyboard.clear()
      await handle_callback(
          chat_id=42,
          client=fake_client,
          callback_query_id="q3",
          callback_data=CallbackId.WALLET_BUNDLE_YES,
          store=store,
          pass_store=pass_store,
          wallet_service=wallet_svc,
      )
      bundle = await pass_store.get(42)
      assert bundle is not None
      assert len(bundle.objects) == 2
      assert bundle.pending_object is None


  # ── WALLET_BUNDLE_NO ──────────────────────────────────────────────────────────

  async def test_wallet_bundle_no_discards_pending(
      fake_client, store, pass_store, wallet_svc
  ) -> None:
      from wallet_bot.handlers.callback_handler import handle_callback

      ticket1 = _approved_ticket(event="Rock Concert", date="2026-06-01")
      ticket2 = _approved_ticket(
          event="Rock Concert Festival", date="2026-06-01", barcode="BC002"
      )
      await _approve(42, fake_client, store, pass_store, wallet_svc, ticket1)
      await _approve(42, fake_client, store, pass_store, wallet_svc, ticket2)

      await handle_callback(
          chat_id=42,
          client=fake_client,
          callback_query_id="q4",
          callback_data=CallbackId.WALLET_BUNDLE_NO,
          store=store,
          pass_store=pass_store,
          wallet_service=wallet_svc,
      )
      bundle = await pass_store.get(42)
      assert bundle is not None
      assert len(bundle.objects) == 1
      assert bundle.pending_object is None
      assert any("ignored" in t.lower() for _, t in fake_client.sent)
  ```

  > Note: the `store` fixture already exists in `test_callback_handler.py`. Add `pass_store` and `wallet_svc` as fixtures in that file's fixture section (or use the parametrized ones defined above).

- [ ] **Step 2: Run — expect failure**

  ```bash
  docker compose run --rm bot pytest tests/unit/handlers/test_callback_handler.py -v -k "bundle or wallet or approve"
  ```

- [ ] **Step 3: Implement bundle logic in callback_handler.py**

  Replace the contents of `src/wallet_bot/handlers/callback_handler.py` with:
  ```python
  """Inline-button callback handler — routes callback_query to bundle flow."""

  from __future__ import annotations

  import json
  import logging
  import re

  from wallet_bot.handlers._render import field_prompt, label_for
  from wallet_bot.handlers._safe import safe_handler
  from wallet_bot.models.callback_ids import (
      EDIT_FIELD_TO_TICKET_ATTR,
      CallbackId,
      parse_callback_id,
  )
  from wallet_bot.models.ticket import ExtractedTicket
  from wallet_bot.models.wallet import PassBundle
  from wallet_bot.services.draft_store import DraftStore
  from wallet_bot.services.pass_store import PassStore
  from wallet_bot.services.telegram_client import InlineButton, TelegramClientProtocol
  from wallet_bot.services.wallet_service import WalletService

  _logger = logging.getLogger(__name__)
  _CANCELLED_MSG = "Cancelled."


  def _normalize(text: str) -> str:
      text = text.lower()
      text = re.sub(r"[^\w\s]", "", text)
      return re.sub(r"\s+", " ", text).strip()


  def _is_exact_match(ticket: ExtractedTicket, bundle: PassBundle) -> bool:
      return _normalize(ticket.event_name or "") == _normalize(bundle.event_name) and (
          _normalize(ticket.date or "") == _normalize(bundle.date)
      )


  def _is_close_match(ticket: ExtractedTicket, bundle: PassBundle) -> bool:
      """Date matches exactly but event name differs after normalization."""
      return _normalize(ticket.date or "") == _normalize(bundle.date) and (
          _normalize(ticket.event_name or "") != _normalize(bundle.event_name)
      )


  def _event_label(ticket: ExtractedTicket) -> str:
      parts = [ticket.event_name or "?", ticket.date or "?"]
      return " · ".join(p for p in parts if p != "?") or "this event"


  @safe_handler
  async def handle_callback(
      chat_id: int,
      client: TelegramClientProtocol,
      *,
      callback_query_id: str,
      callback_data: str,
      store: DraftStore,
      pass_store: PassStore,
      wallet_service: WalletService,
  ) -> None:
      await client.answer_callback_query(callback_query_id=callback_query_id)

      cb = parse_callback_id(callback_data)
      if cb is None:
          _logger.info("dropped unknown callback_data from chat_id=%s", chat_id)
          return

      # ── WALLET_GET_LINK ────────────────────────────────────────────────────────
      if cb is CallbackId.WALLET_GET_LINK:
          bundle = await pass_store.get(chat_id)
          if bundle is None or not bundle.objects:
              await client.send_text(chat_id, "No active bundle. Send a ticket photo first.")
              return
          save_url = wallet_service.build_save_url(bundle.objects)
          await client.send_url_button(
              chat_id, "Your pass is ready!", "Add to Google Wallet", save_url
          )
          await pass_store.clear(chat_id)
          return

      # ── WALLET_BUNDLE_YES ──────────────────────────────────────────────────────
      if cb is CallbackId.WALLET_BUNDLE_YES:
          bundle = await pass_store.get(chat_id)
          if bundle is None or bundle.pending_object is None:
              return
          await pass_store.confirm_pending(chat_id)
          updated = await pass_store.get(chat_id)
          n = len(updated.objects) if updated else 1
          await client.send_with_inline_keyboard(
              chat_id,
              f"Added · bundle now has {n} tickets for {bundle.event_name} · {bundle.date}.",
              rows=[[InlineButton(text="Get Wallet link", callback_data=CallbackId.WALLET_GET_LINK)]],
          )
          return

      # ── WALLET_BUNDLE_NO ───────────────────────────────────────────────────────
      if cb is CallbackId.WALLET_BUNDLE_NO:
          await pass_store.discard_pending(chat_id)
          await client.send_text(chat_id, "Ticket ignored.")
          return

      # ── Existing draft callbacks ───────────────────────────────────────────────
      draft = await store.get(chat_id)
      if draft is None:
          return

      if cb is CallbackId.APPROVE:
          # Guard: wallet not configured
          if wallet_service is None:
              await store.clear(chat_id)
              await client.send_text(
                  chat_id,
                  "Wallet not configured. Set WALLET_ISSUER_ID and WALLET_SA_JSON.",
              )
              return

          ticket = draft.ticket
          _logger.info(
              "ticket_approved %s",
              json.dumps(
                  ticket.model_dump(exclude={"raw_text": True, "barcode": {"barcode_value"}}),
                  ensure_ascii=False,
              ),
          )

          # Build wallet object BEFORE clearing the draft, so a build failure
          # leaves the draft intact and lets the user retry.
          wallet_obj = wallet_service.build_object(chat_id, ticket)
          await store.clear(chat_id)
          bundle = await pass_store.get(chat_id)

          if bundle is None:
              await pass_store.put(
                  chat_id,
                  PassBundle(
                      event_name=ticket.event_name or "",
                      date=ticket.date or "",
                      class_id=wallet_obj.class_id,
                      objects=[wallet_obj],
                  ),
              )
              label = _event_label(ticket)
              await client.send_with_inline_keyboard(
                  chat_id,
                  f"Saved ✓ for {label}.\nSend more tickets for this event, or tap below.",
                  rows=[[InlineButton(text="Get Wallet link", callback_data=CallbackId.WALLET_GET_LINK)]],
              )
              return

          if _is_exact_match(ticket, bundle):
              if wallet_obj.barcode_value and await pass_store.has_barcode(
                  chat_id, wallet_obj.barcode_value
              ):
                  await client.send_text(chat_id, "This ticket is already in your bundle.")
                  return
              await pass_store.add_object(chat_id, wallet_obj)
              updated = await pass_store.get(chat_id)
              n = len(updated.objects) if updated else 1
              label = _event_label(ticket)
              await client.send_with_inline_keyboard(
                  chat_id,
                  f"Added · bundle now has {n} tickets for {label}.",
                  rows=[[InlineButton(text="Get Wallet link", callback_data=CallbackId.WALLET_GET_LINK)]],
              )
              return

          if _is_close_match(ticket, bundle):
              await pass_store.set_pending(chat_id, wallet_obj)
              await client.send_with_inline_keyboard(
                  chat_id,
                  f"Is this the same event as {bundle.event_name} on {bundle.date}?",
                  rows=[[
                      InlineButton(text="Yes, add to bundle", callback_data=CallbackId.WALLET_BUNDLE_YES),
                      InlineButton(text="No, ignore", callback_data=CallbackId.WALLET_BUNDLE_NO),
                  ]],
              )
              return

          # No match
          label = _event_label(ticket)
          await client.send_text(
              chat_id,
              f"This ticket is for {label}, but your bundle is for {bundle.event_name} · {bundle.date}. Ticket ignored.",
          )
          return

      if cb is CallbackId.CANCEL:
          await store.clear(chat_id)
          await client.send_text(chat_id, _CANCELLED_MSG)
          return

      attr = EDIT_FIELD_TO_TICKET_ATTR[cb]
      await store.set_editing_field(chat_id, attr)
      label = label_for(cb) or attr
      await client.send_force_reply(chat_id=chat_id, text=field_prompt(label))
  ```

- [ ] **Step 4: Run new tests — expect pass**

  ```bash
  docker compose run --rm bot pytest tests/unit/handlers/test_callback_handler.py -v
  ```

- [ ] **Step 5: Run full suite — all existing tests must stay green**

  ```bash
  docker compose run --rm bot pytest -v
  ```

- [ ] **Step 6: Commit**

  ```bash
  git add src/wallet_bot/handlers/callback_handler.py tests/unit/handlers/test_callback_handler.py
  git commit -m "feat: callback handler — full multi-ticket bundle flow (WALLET_GET_LINK, WALLET_BUNDLE_YES/NO)"
  ```

---

### Task 10: Start and Help — explain multi-ticket flow

**Files:**
- Modify: `src/wallet_bot/handlers/start_handler.py`
- Modify: `src/wallet_bot/handlers/help_handler.py`

- [ ] **Step 1: Write failing tests**

  In `tests/unit/test_handlers.py` (or start a new file), add:
  ```python
  async def test_start_explains_multi_ticket_flow(fake_client) -> None:
      from wallet_bot.handlers.start_handler import handle_start

      await handle_start(42, fake_client)
      text = fake_client.sent[0][1].lower()
      assert "wallet" in text
      assert "ticket" in text
      # Must mention that multiple tickets can be sent and linked together
      assert any(kw in text for kw in ("more ticket", "bundle", "get wallet link", "tap"))


  async def test_help_explains_multi_ticket_flow(fake_client) -> None:
      from wallet_bot.handlers.help_handler import handle_help

      await handle_help(42, fake_client)
      text = fake_client.sent[0][1].lower()
      assert "wallet" in text
      assert "ticket" in text
      assert any(kw in text for kw in ("multiple", "bundle", "more ticket", "get wallet link"))
  ```

- [ ] **Step 2: Run — expect failure**

  ```bash
  docker compose run --rm bot pytest tests/unit/test_handlers.py -v -k "start_mentions or help_mentions"
  ```

- [ ] **Step 3: Update start_handler.py**

  ```python
  _TEXT = (
      "Welcome to Wallet Bot!\n\n"
      "Send me a photo of your event ticket and I'll convert it to a Google Wallet pass.\n\n"
      "How it works:\n"
      "1. Send a ticket photo\n"
      "2. Review the extracted details — edit any field if needed\n"
      "3. Tap Approve\n"
      "4. For the same event, send more ticket photos and approve each one\n"
      "5. Tap Get Wallet link to add all your tickets to Google Wallet in one tap"
  )
  ```

- [ ] **Step 4: Update help_handler.py**

  ```python
  _TEXT = (
      "Available commands:\n"
      "/start — show welcome message\n"
      "/help — show this message\n\n"
      "Send a ticket photo to generate a Google Wallet pass.\n\n"
      "Multi-ticket bundles: send multiple photos for the same event, "
      "approve each ticket, then tap Get Wallet link to add them all at once."
  )
  ```

- [ ] **Step 5: Run — expect pass**

  ```bash
  docker compose run --rm bot pytest tests/unit/test_handlers.py -v
  ```

- [ ] **Step 6: Commit**

  ```bash
  git add src/wallet_bot/handlers/start_handler.py src/wallet_bot/handlers/help_handler.py tests/unit/test_handlers.py
  git commit -m "feat: update /start and /help to explain multi-ticket bundle flow"
  ```

---

### Task 11: main.py — wire WalletService and PassStore

**Files:**
- Modify: `src/wallet_bot/main.py`

- [ ] **Step 1: Write the failing test**

  In `tests/unit/test_smoke.py`, check that the app still starts:
  ```bash
  docker compose run --rm bot pytest tests/unit/test_smoke.py -v
  ```
  (Should pass already — we're adding wallet config defaults so startup still works without wallet env vars.)

- [ ] **Step 2: Update lifespan in main.py**

  Add imports:
  ```python
  from wallet_bot.services.pass_store import PassStore, get_default_pass_store
  from wallet_bot.services.wallet_service import WalletService
  ```

  In `lifespan`, after `app.state.draft_store = get_default_store()`:
  ```python
  app.state.pass_store = get_default_pass_store()
  sa_json = settings.wallet_sa_json
  if sa_json and settings.wallet_issuer_id:
      app.state.wallet_service = WalletService(
          issuer_id=settings.wallet_issuer_id,
          sa_json=sa_json.get_secret_value(),
          origins=settings.wallet_origins,
      )
  else:
      app.state.wallet_service = None
  ```

  Add dependency functions:
  ```python
  def get_pass_store(request: Request) -> PassStore:
      return request.app.state.pass_store  # type: ignore[no-any-return]


  def get_wallet_service(request: Request) -> WalletService | None:
      return request.app.state.wallet_service  # type: ignore[no-any-return]
  ```

  Update the webhook handler signature to inject `pass_store` and `wallet_service`:
  ```python
  @app.post("/telegram/webhook", status_code=200)
  async def webhook(
      request: Request,
      x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
      settings: Settings = Depends(get_settings),
      client: TelegramClientProtocol = Depends(get_client),
      store: DraftStore = Depends(get_store),
      pass_store: PassStore = Depends(get_pass_store),
      wallet_service: WalletService | None = Depends(get_wallet_service),
  ) -> dict[str, str]:
  ```

  In the callback query branch, pass the new services:
  ```python
  await handle_callback(
      chat_id=chat_id,
      client=client,
      callback_query_id=cbq.id,
      callback_data=cbq.data or "",
      store=store,
      pass_store=pass_store,
      wallet_service=wallet_service,  # type: ignore[arg-type]
  )
  ```

  > When `wallet_service` is `None` (wallet env vars not set), `handle_callback` will fail at `wallet_service.build_object()`. Add a guard at the top of the `APPROVE` branch:
  > ```python
  > if cb is CallbackId.APPROVE:
  >     if wallet_service is None:
  >         await store.clear(chat_id)
  >         await client.send_text(chat_id, "Wallet not configured. Set WALLET_ISSUER_ID and WALLET_SA_JSON.")
  >         return
  >     ...
  > ```

- [ ] **Step 3: Run full suite**

  ```bash
  docker compose run --rm bot pytest -v
  ```
  Expected: all tests pass (smoke test, webhook tests, handler tests).

- [ ] **Step 4: Lint**

  ```bash
  docker compose run --rm bot ruff check src/ tests/
  docker compose run --rm bot ruff format src/ tests/
  ```

- [ ] **Step 5: Commit**

  ```bash
  git add src/wallet_bot/main.py
  git commit -m "feat: wire WalletService and PassStore into FastAPI DI"
  ```

---

## Chunk 4: Verification

### Task 12: Full test run + JWT validation

- [ ] **Step 1: Final full test run**

  ```bash
  docker compose run --rm bot pytest -v --tb=short
  ```
  Expected: all tests pass (≥134 existing + new Phase 04 tests).

- [ ] **Step 2: Validate a real JWT**

  Set real wallet credentials in `.env`:
  ```
  WALLET_ISSUER_ID=<your issuer id>
  WALLET_SA_JSON=<contents of your service account JSON, single line>
  WALLET_ORIGINS=https://example.com
  ```

  Run a one-shot validation script:
  ```bash
  docker compose run --rm bot python - <<'EOF'
  import json, asyncio
  from wallet_bot.config import get_settings
  from wallet_bot.models.ticket import BarcodeResult, ExtractedTicket
  from wallet_bot.services.wallet_service import WalletService

  s = get_settings()
  svc = WalletService(
      issuer_id=s.wallet_issuer_id,
      sa_json=s.wallet_sa_json.get_secret_value(),
      origins=s.wallet_origins,
  )
  ticket = ExtractedTicket(
      event_name="Test Event",
      date="2026-06-01",
      barcode=BarcodeResult(barcode_type="QR_CODE", barcode_value="TEST-001"),
  )
  obj = svc.build_object(chat_id=42, ticket=ticket)
  url = svc.build_save_url([obj])
  jwt_part = url.removeprefix("https://pay.google.com/gp/v/save/")
  print(jwt_part)
  EOF
  ```

  Then pass the JWT to the `wallet-jwt-validator` agent (see [`.claude/agents/wallet-jwt-validator.md`](../../.claude/agents/wallet-jwt-validator.md)) for validation. **This step is required before the PR is merged.** The validator must report all claims as ✅ and produce a valid save URL. If it flags issues, fix them before continuing to `/ship`.

- [ ] **Step 3: Update STATUS.md and phase plan**

  Mark Phase 04 as in-progress in `STATUS.md`. Update `phases/04-wallet-pass/plan.md` checklist.

  ```bash
  git add STATUS.md phases/04-wallet-pass/plan.md
  git commit -m "chore: mark Phase 04 in-progress"
  ```

- [ ] **Step 4: Create wallet-pass-preview skill**

  Run `/superpowers:writing-skills` to create `.claude/skills/wallet-pass-preview/SKILL.md`.
  Follow TDD: write a failing pressure test, write minimum skill, refactor.

---

## Notes

- All run commands assume `docker compose run --rm bot <cmd>` (see CLAUDE.md).
- `wallet_service` type annotation in the webhook is `WalletService | None` — the `APPROVE` guard handles the unconfigured case gracefully.
- Hebrew field values use language code `"iw"` (Google Wallet uses `"iw"` not `"he"`).
- The `wallet-jwt-validator` agent can dry-run against the Wallet API staging environment once real credentials are set.
