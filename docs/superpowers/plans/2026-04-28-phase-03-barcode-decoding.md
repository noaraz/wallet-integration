# Phase 03 — Barcode Decoding Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend Gemini's existing ticket-extraction call to also decode any QR/barcode in the photo, storing the result as a nullable `BarcodeResult` nested on `ExtractedTicket`.

**Architecture:** No new service or library — `BarcodeResult` is added to the domain model, the Pydantic schema is picked up automatically by the Gemini SDK's `response_schema`, and a single instruction sentence is added to `STRUCTURED_PROMPT`. The approve log is updated to exclude `barcode_value` (sensitive payload) while retaining `barcode_type`.

**Tech Stack:** Python 3.12, Pydantic v2 (`BaseModel`, `field_validator`), google-genai SDK, pytest-asyncio.

---

## Chunk 1: Data model + approve-log exclusion

### Task 1: Add `BarcodeResult` model and `barcode` field to `ExtractedTicket`

**Files:**
- Modify: `src/wallet_bot/models/ticket.py`
- Modify: `tests/unit/models/test_ticket.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/models/test_ticket.py` (after the existing imports, add `BarcodeResult`):

```python
from wallet_bot.models.ticket import BarcodeResult, DraftState, ExtractedTicket


class TestBarcodeResult:
    def test_valid_barcode(self) -> None:
        b = BarcodeResult(barcode_type="QR_CODE", barcode_value="https://ticket.example/abc123")
        assert b.barcode_type == "QR_CODE"
        assert b.barcode_value == "https://ticket.example/abc123"

    def test_empty_value_normalised_to_none(self) -> None:
        b = BarcodeResult(barcode_type="QR_CODE", barcode_value="")
        assert b.barcode_value is None

    def test_none_value_stays_none(self) -> None:
        b = BarcodeResult(barcode_type="QR_CODE", barcode_value=None)
        assert b.barcode_value is None

    def test_barcode_type_is_required(self) -> None:
        with pytest.raises(ValidationError):
            BarcodeResult(barcode_value="something")  # type: ignore[call-arg]


class TestExtractedTicketBarcode:
    def test_barcode_defaults_to_none(self) -> None:
        assert ExtractedTicket().barcode is None

    def test_barcode_parses_nested_dict(self) -> None:
        t = ExtractedTicket(
            barcode={"barcode_type": "QR_CODE", "barcode_value": "https://x.example"}
        )
        assert t.barcode is not None
        assert t.barcode.barcode_type == "QR_CODE"
        assert t.barcode.barcode_value == "https://x.example"

    def test_barcode_parses_instance(self) -> None:
        b = BarcodeResult(barcode_type="CODE_128", barcode_value="ABC-123")
        t = ExtractedTicket(barcode=b)
        assert t.barcode is b

    def test_model_dump_can_exclude_barcode_value(self) -> None:
        t = ExtractedTicket(
            event_name="גיא מזיג",
            barcode=BarcodeResult(barcode_type="QR_CODE", barcode_value="secret-token"),
        )
        dumped = t.model_dump(exclude={"raw_text": True, "barcode": {"barcode_value"}})
        assert "secret-token" not in str(dumped)
        assert dumped["barcode"]["barcode_type"] == "QR_CODE"
        assert "barcode_value" not in dumped["barcode"]

    def test_existing_fields_unaffected_by_barcode_addition(self) -> None:
        t = ExtractedTicket(event_name="גיא מזיג", venue="אמפי תל אביב")
        assert t.barcode is None
        assert t.event_name == "גיא מזיג"
```

- [ ] **Step 2: Run tests to confirm RED**

```bash
docker compose run --rm bot pytest tests/unit/models/test_ticket.py -v
```

Expected: `ImportError: cannot import name 'BarcodeResult'` (or similar attribute error).

- [ ] **Step 3: Implement `BarcodeResult` and extend `ExtractedTicket`**

In `src/wallet_bot/models/ticket.py`, add the import and model **before** `ExtractedTicket`:

```python
from pydantic import BaseModel, Field, field_validator


class BarcodeResult(BaseModel):
    """Barcode or QR payload decoded from the ticket image by Gemini Vision."""

    barcode_type: str
    barcode_value: str | None = None

    @field_validator("barcode_value")
    @classmethod
    def _empty_to_none(cls, v: str | None) -> str | None:
        return None if v == "" else v
```

Then add one field at the end of `ExtractedTicket` (before `raw_text`):

```python
    barcode: BarcodeResult | None = None
    raw_text: str = Field(
        default="",
        description="Full Gemini transcription — DEBUG ONLY. Exclude from INFO logs.",
    )
```

The full updated file:

```python
"""Domain models for extracted Hebrew ticket data + draft state.

Fields are deliberately ``str | None`` so Hebrew text is preserved verbatim
from Gemini (no coercion to datetime/Decimal); Phase 04 re-parses when
building the wallet pass. ``raw_text`` holds Gemini's full transcription for
debugging only — it MUST NOT appear in INFO-level logs. ``barcode_value``
holds the decoded barcode payload — also excluded from INFO logs (may be a
signed token).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class BarcodeResult(BaseModel):
    """Barcode or QR payload decoded from the ticket image by Gemini Vision."""

    barcode_type: str
    barcode_value: str | None = None

    @field_validator("barcode_value")
    @classmethod
    def _empty_to_none(cls, v: str | None) -> str | None:
        return None if v == "" else v


class ExtractedTicket(BaseModel):
    """Structured ticket fields extracted by the vision service."""

    event_name: str | None = None
    venue: str | None = None
    venue_address: str | None = None
    date: str | None = None
    time: str | None = None
    section: str | None = None
    holder_name: str | None = None
    order_number: str | None = None
    ticket_id: str | None = None
    price: str | None = None
    barcode: BarcodeResult | None = None
    raw_text: str = Field(
        default="",
        description="Full Gemini transcription — DEBUG ONLY. Exclude from INFO logs.",
    )


class DraftState(BaseModel):
    """In-memory per-chat draft being edited before approval."""

    ticket: ExtractedTicket
    editing_field: str | None = None
    message_id: int
    created_at: datetime
```

- [ ] **Step 4: Run tests to confirm GREEN**

```bash
docker compose run --rm bot pytest tests/unit/models/test_ticket.py -v
```

Expected: All tests in `TestBarcodeResult`, `TestExtractedTicketBarcode`, and the pre-existing `TestExtractedTicket` / `TestDraftState` pass.

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
docker compose run --rm bot pytest -v
```

Expected: All existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/wallet_bot/models/ticket.py tests/unit/models/test_ticket.py
git commit -m "feat: add BarcodeResult model + barcode field to ExtractedTicket"
```

---

### Task 2: Exclude `barcode_value` from the approve log

**Files:**
- Modify: `src/wallet_bot/handlers/callback_handler.py`
- Modify: `tests/unit/handlers/test_callback_handler.py`

- [ ] **Step 1: Write failing test**

Add to `tests/unit/handlers/test_callback_handler.py`. Add `BarcodeResult` to the import:

```python
from wallet_bot.models.ticket import BarcodeResult, DraftState, ExtractedTicket
```

Then add the new test:

```python
async def test_approve_excludes_barcode_value_from_log(
    fake_client, caplog
) -> None:
    store = DraftStore()
    draft = DraftState(
        ticket=ExtractedTicket(
            event_name="גיא מזיג",
            barcode=BarcodeResult(
                barcode_type="QR_CODE",
                barcode_value="super-secret-signed-token",
            ),
            raw_text="debug dump",
        ),
        message_id=99,
        created_at=datetime.now(tz=UTC),
    )
    await store.put(42, draft)

    with caplog.at_level(logging.INFO):
        await handle_callback(
            chat_id=42,
            client=fake_client,
            callback_query_id="cb1",
            callback_data="approve",
            store=store,
        )

    approval_lines = [r for r in caplog.records if "ticket_approved" in r.getMessage()]
    assert len(approval_lines) == 1
    line_text = approval_lines[0].getMessage()
    # Sensitive payload must be absent.
    assert "super-secret-signed-token" not in line_text
    assert "barcode_value" not in line_text
    # Safe metadata stays.
    payload = json.loads(line_text.split("ticket_approved ", 1)[1])
    assert payload["barcode"]["barcode_type"] == "QR_CODE"
```

- [ ] **Step 2: Run test to confirm RED**

```bash
docker compose run --rm bot pytest tests/unit/handlers/test_callback_handler.py::test_approve_excludes_barcode_value_from_log -v
```

Expected: FAIL — `"super-secret-signed-token"` appears in the log (the exclude set currently only covers `raw_text`).

- [ ] **Step 3: Update the exclude call in `callback_handler.py`**

In `src/wallet_bot/handlers/callback_handler.py`, line 59, change:

```python
        payload = draft.ticket.model_dump(exclude={"raw_text"})
```

to:

```python
        payload = draft.ticket.model_dump(
            exclude={"raw_text": True, "barcode": {"barcode_value"}}
        )
```

- [ ] **Step 4: Run test to confirm GREEN**

```bash
docker compose run --rm bot pytest tests/unit/handlers/test_callback_handler.py -v
```

Expected: All tests in the file pass, including the new one.

- [ ] **Step 5: Run full suite**

```bash
docker compose run --rm bot pytest -v
```

Expected: All tests pass.

- [ ] **Step 6: Lint**

```bash
docker compose run --rm bot ruff check src/ tests/
```

Expected: No issues.

- [ ] **Step 7: Commit**

```bash
git add src/wallet_bot/handlers/callback_handler.py tests/unit/handlers/test_callback_handler.py
git commit -m "feat: exclude barcode_value from approve log alongside raw_text"
```

---

## Chunk 2: Gemini prompt extension + handler tests + documentation

### Task 3: Extend `STRUCTURED_PROMPT` with barcode instruction

**Files:**
- Modify: `src/wallet_bot/services/gemini_vision.py`
- Modify: `tests/unit/services/test_gemini_vision.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/services/test_gemini_vision.py`, inside `TestGeminiVisionService`:

```python
    async def test_extract_returns_ticket_with_barcode(self) -> None:
        raw_json = (
            '{"event_name": "גיא מזיג", '
            '"barcode": {"barcode_type": "QR_CODE", "barcode_value": "https://ticket.example/abc123"}}'
        )
        client = self._make_fake_client(raw_json)
        svc = GeminiVisionService(client=client, model="gemini-2.5-flash")

        ticket = await svc.extract(b"\x89PNG fake", mime_type="image/png")

        assert ticket.barcode is not None
        assert ticket.barcode.barcode_type == "QR_CODE"
        assert ticket.barcode.barcode_value == "https://ticket.example/abc123"

    async def test_extract_returns_none_barcode_when_absent(self) -> None:
        raw_json = '{"event_name": "גיא מזיג"}'
        client = self._make_fake_client(raw_json)
        svc = GeminiVisionService(client=client, model="gemini-2.5-flash")

        ticket = await svc.extract(b"\x89PNG fake", mime_type="image/png")

        assert ticket.barcode is None

    async def test_extract_normalises_empty_barcode_value_to_none(self) -> None:
        raw_json = (
            '{"event_name": "גיא מזיג", '
            '"barcode": {"barcode_type": "QR_CODE", "barcode_value": ""}}'
        )
        client = self._make_fake_client(raw_json)
        svc = GeminiVisionService(client=client, model="gemini-2.5-flash")

        ticket = await svc.extract(b"\x89PNG fake", mime_type="image/png")

        assert ticket.barcode is not None
        assert ticket.barcode.barcode_value is None
```

Also add a standalone test (outside the class) to guard the prompt:

```python
def test_structured_prompt_instructs_barcode_extraction() -> None:
    from wallet_bot.services.gemini_vision import STRUCTURED_PROMPT

    assert "barcode" in STRUCTURED_PROMPT.lower()
    assert "barcode_type" in STRUCTURED_PROMPT
    assert "barcode_value" in STRUCTURED_PROMPT
```

- [ ] **Step 2: Run tests to confirm RED**

```bash
docker compose run --rm bot pytest tests/unit/services/test_gemini_vision.py -v
```

Expected: The three new `test_extract_*` tests pass already (they test JSON parsing, which `BarcodeResult` already handles). The `test_structured_prompt_instructs_barcode_extraction` test **fails** because `STRUCTURED_PROMPT` doesn't mention barcode yet.

- [ ] **Step 3: Update `STRUCTURED_PROMPT` in `gemini_vision.py`**

In `src/wallet_bot/services/gemini_vision.py`, replace:

```python
STRUCTURED_PROMPT = (
    "Extract ticket fields from this image. Preserve Hebrew text verbatim. "
    "Leave a field null when the value is not clearly present — never guess. "
    "Return raw_text as the full transcribed reading-order dump of the ticket."
)
```

with:

```python
STRUCTURED_PROMPT = (
    "Extract ticket fields from this image. Preserve Hebrew text verbatim. "
    "Leave a field null when the value is not clearly present — never guess. "
    "Return raw_text as the full transcribed reading-order dump of the ticket. "
    "If the ticket contains a QR code, barcode, or any machine-readable symbol, "
    "set barcode_type to the format name (e.g. QR_CODE, CODE_128, AZTEC) and "
    "barcode_value to its decoded payload. "
    "If none is visible or readable, omit the barcode field entirely."
)
```

- [ ] **Step 4: Run tests to confirm GREEN**

```bash
docker compose run --rm bot pytest tests/unit/services/test_gemini_vision.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Run full suite**

```bash
docker compose run --rm bot pytest -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/wallet_bot/services/gemini_vision.py tests/unit/services/test_gemini_vision.py
git commit -m "feat: extend Gemini extraction prompt to include barcode/QR decoding"
```

---

### Task 4: Extend photo handler tests to cover barcode presence and absence

**Files:**
- Modify: `tests/unit/handlers/test_photo_handler.py`

These tests should **pass immediately** (no handler code changes needed — `ExtractedTicket.barcode` defaults to `None` and the draft stores whatever the vision service returns). The tests document the contract.

- [ ] **Step 1: Add tests**

Add `BarcodeResult` to the imports in `tests/unit/handlers/test_photo_handler.py`:

```python
from wallet_bot.models.ticket import BarcodeResult, ExtractedTicket
```

Add two new tests:

```python
async def test_draft_stores_barcode_when_present(fake_client, store) -> None:
    ticket = ExtractedTicket(
        event_name="גיא מזיג",
        barcode=BarcodeResult(
            barcode_type="QR_CODE",
            barcode_value="https://ticket.example/abc",
        ),
    )
    vision = _FakeVision(ticket)

    await handle_photo(
        chat_id=42,
        client=fake_client,
        file_id="PHOTO123",
        vision=vision,
        store=store,
    )

    draft = await store.get(42)
    assert draft is not None
    assert draft.ticket.barcode is not None
    assert draft.ticket.barcode.barcode_type == "QR_CODE"
    assert draft.ticket.barcode.barcode_value == "https://ticket.example/abc"


async def test_draft_stores_none_barcode_when_absent(fake_client, store) -> None:
    ticket = ExtractedTicket(event_name="גיא מזיג")  # barcode=None by default
    vision = _FakeVision(ticket)

    await handle_photo(
        chat_id=42,
        client=fake_client,
        file_id="PHOTO456",
        vision=vision,
        store=store,
    )

    draft = await store.get(42)
    assert draft is not None
    assert draft.ticket.barcode is None
```

- [ ] **Step 2: Run tests to confirm they pass immediately (GREEN from the start)**

```bash
docker compose run --rm bot pytest tests/unit/handlers/test_photo_handler.py -v
```

Expected: All tests pass (including the two new ones).

- [ ] **Step 3: Run full suite + lint**

```bash
docker compose run --rm bot pytest -v && docker compose run --rm bot ruff check src/ tests/
```

Expected: All tests pass, lint clean.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/handlers/test_photo_handler.py
git commit -m "test: cover barcode presence and absence in photo handler"
```

---

### Task 5: Write documentation

**Files:**
- Create: `docs/superpowers/specs/2026-04-28-phase-03-barcode-decoding-design.md`
- Modify: `phases/03-barcode-decode/plan.md`
- Modify: `STATUS.md`

- [ ] **Step 1: Write design doc**

Copy the approved brainstorm design into a permanent spec file. Create `docs/superpowers/specs/2026-04-28-phase-03-barcode-decoding-design.md` with the content from `~/.claude/plans/phase-03-crystalline-fairy.md`.

- [ ] **Step 2: Update `phases/03-barcode-decode/plan.md`**

Replace the placeholder with an executed-plan summary (mirror the style of `phases/02-vision-extraction/plan.md`):

```markdown
# Phase 03 — Barcode decoding ✅

> Executed. Design doc at
> `docs/superpowers/specs/2026-04-28-phase-03-barcode-decoding-design.md`.

## What this phase delivers

Gemini's existing vision call is extended to also decode any QR code or barcode
visible in the ticket photo. The payload is stored as a nullable `BarcodeResult`
nested on `ExtractedTicket`. Phase 04 reads `ticket.barcode.barcode_type` and
`ticket.barcode.barcode_value` when building the Google Wallet pass.

## Decisions

- **No barcode library.** Target tickets are Israeli concert/sports QR codes
  with text/URL payloads. Gemini Vision reads these directly — zero new native
  deps, zero Docker changes.
- **Nested `BarcodeResult` model** (not flat fields) so Phase 04 gets a clean
  `ticket.barcode` interface. Field names `barcode_type` / `barcode_value`
  avoid shadowing `builtins.type` and are `mypy --strict`-friendly (Phase 07).
- **Empty-string normalisation.** A `field_validator` converts `""` →
  `None` so Phase 04 always receives `None` or a meaningful string.
- **Silent fallback** when `barcode` is `None`. No user-facing warning in
  Phase 03; Phase 04 decides whether a barcode is required.
- **`barcode_value` excluded from INFO logs** (may be a signed token or
  PII-adjacent). `barcode_type` is safe metadata and stays in the log.

## What landed

| Component | Notes |
|---|---|
| `models/ticket.py` | `BarcodeResult` (barcode_type, barcode_value + empty→None validator); `ExtractedTicket.barcode: BarcodeResult \| None` |
| `services/gemini_vision.py` | `STRUCTURED_PROMPT` extended with barcode instruction |
| `handlers/callback_handler.py` | `model_dump(exclude={"raw_text": True, "barcode": {"barcode_value"}})` |

## Coverage

All existing tests still pass. New tests added to `test_ticket.py`,
`test_gemini_vision.py`, `test_callback_handler.py`, `test_photo_handler.py`.

## Superpowers checklist

- [x] `/superpowers:brainstorming`
- [x] `/superpowers:writing-plans`
- [x] `/superpowers:test-driven-development`
- [ ] `/ship`
```

- [ ] **Step 3: Update `STATUS.md`**

In `STATUS.md`, change the Phase 03 row from `⬜ not started` to `🔄 in progress` (or `✅ done` after merge), and add a Phase 03 task table below the Phase 02 section:

```markdown
## Phase 03 — Barcode decoding ✅

| Task | Status |
|------|--------|
| `BarcodeResult` model + `ExtractedTicket.barcode` field | ✅ |
| `barcode_value` excluded from approve log | ✅ |
| `STRUCTURED_PROMPT` extended with barcode instruction | ✅ |
| Photo handler tests cover barcode presence/absence | ✅ |
| Design doc + `phases/03-barcode-decode/plan.md` updated | ✅ |
| `STATUS.md` updated, current focus → Phase 04 | ✅ |
| PR merged to main | ✅ |
```

Also update the **Current Focus** section header to point to Phase 04.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-04-28-phase-03-barcode-decoding-design.md \
        phases/03-barcode-decode/plan.md \
        STATUS.md
git commit -m "docs: Phase 03 design doc, plan summary, STATUS update"
```

---

## Final verification

- [ ] Run full suite one last time:

```bash
docker compose run --rm bot pytest -v --tb=short
```

Expected: All tests pass, coverage ≥80%.

- [ ] Lint:

```bash
docker compose run --rm bot ruff check src/ tests/
```

Expected: No issues.

- [ ] Then run `/ship` to open the PR.
