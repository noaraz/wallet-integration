"""Gemini 2.5 Flash vision backend.

Implementation of the :mod:`wallet_bot.services.vision_service` facade. All
callers — handlers, ``scripts/eval_ocr.py``, and the debugging-hebrew-ocr
skill — reach Gemini through the facade's factories, never by importing this
module directly. Swap the backend = swap one import in ``vision_service.py``.

Single source of truth for prompts, model name, mime normalisation, and
client construction. Do not duplicate Gemini SDK calls elsewhere.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from wallet_bot.models.ticket import ExtractedTicket
from wallet_bot.services.vision_service import VisionExtractionError

if TYPE_CHECKING:
    from google.genai import Client

# --- shared constants -------------------------------------------------------

GEMINI_DEFAULT_MODEL = "gemini-2.5-flash"

RAW_TEXT_PROMPT = (
    "Extract ALL text from this ticket exactly as it appears, preserving Hebrew. "
    "Output only the raw text in natural reading order, one field per line. "
    "No commentary, no JSON, no markdown."
)

STRUCTURED_PROMPT = (
    "Extract ticket fields from this image. Preserve Hebrew text verbatim. "
    "Leave a field null when the value is not clearly present — never guess. "
    "Return raw_text as the full transcribed reading-order dump of the ticket."
)


# --- mime helpers -----------------------------------------------------------

_STRUCTURED_IMAGE_MIMES = {"image/png", "image/jpeg"}
_RAW_TEXT_MIMES = _STRUCTURED_IMAGE_MIMES | {"application/pdf"}


def _normalise_mime(raw: str) -> str:
    """Normalise an image mime for the structured extraction path.

    Accepts ``image/png`` and ``image/jpeg``; rewrites ``image/jpg`` (which
    Gemini rejects) to ``image/jpeg``. Case-insensitive. Raises ``ValueError``
    for anything else (PDFs and other mimes go through the raw-text path
    used by the eval script, not production extraction).
    """
    lowered = raw.lower()
    if lowered == "image/jpg":
        lowered = "image/jpeg"
    if lowered not in _STRUCTURED_IMAGE_MIMES:
        raise ValueError(f"unsupported mime for structured extraction: {raw!r}")
    return lowered


def _mime_from_path(path: Path) -> str:
    """Derive a Gemini-acceptable mime from a file extension (script use)."""
    suffix = path.suffix.lstrip(".").lower()
    if suffix == "pdf":
        return "application/pdf"
    if suffix == "jpg":
        return "image/jpeg"
    mime = f"image/{suffix}"
    if mime not in _RAW_TEXT_MIMES:
        raise ValueError(f"unsupported file extension for Gemini: {path.suffix!r}")
    return mime


# --- client factory ---------------------------------------------------------


def build_client(api_key: str) -> Client:
    """Construct a google-genai client. Lazy-imports the SDK so unit tests
    don't require it installed."""
    from google import genai

    return genai.Client(api_key=api_key)


# --- raw-text path (used by eval script + optional debugging) ---------------


def extract_raw_text_from_bytes(
    data: bytes,
    mime: str,
    *,
    client: Client,
    model: str = GEMINI_DEFAULT_MODEL,
) -> str:
    """Ask Gemini for the full transcribed text (reading order, Hebrew preserved)."""
    from google.genai import types

    part = types.Part.from_bytes(data=data, mime_type=mime)
    response = client.models.generate_content(
        model=model,
        contents=[part, RAW_TEXT_PROMPT],
    )
    return (response.text or "").strip()


def extract_raw_text_from_file(
    path: Path,
    *,
    client: Client,
    model: str = GEMINI_DEFAULT_MODEL,
) -> str:
    """Convenience wrapper for CLI tools: infer mime from suffix, read bytes."""
    mime = _mime_from_path(path)
    return extract_raw_text_from_bytes(path.read_bytes(), mime, client=client, model=model)


class GeminiTextDumper:
    """Adapter implementing :class:`TextDumpProtocol` for CLI/debug use."""

    def __init__(self, *, client: Any, model: str = GEMINI_DEFAULT_MODEL) -> None:
        self._client = client
        self._model = model

    def dump_file(self, path: Path) -> str:
        return extract_raw_text_from_file(path, client=self._client, model=self._model)


# --- structured extraction (production) -------------------------------------


class GeminiVisionService:
    """Production vision service. Emits :class:`ExtractedTicket` via JSON schema.

    Construct with a pre-built google-genai client (kept as a constructor
    arg for DI and testability — unit tests pass a ``MagicMock``).
    """

    def __init__(self, *, client: Any, model: str = GEMINI_DEFAULT_MODEL) -> None:
        self._client = client
        self._model = model

    async def extract(self, image_bytes: bytes, mime_type: str) -> ExtractedTicket:
        mime = _normalise_mime(mime_type)
        # The SDK call is blocking; run it in a worker thread so we don't
        # stall the FastAPI event loop.
        return await asyncio.to_thread(self._extract_sync, image_bytes, mime)

    def _extract_sync(self, image_bytes: bytes, mime: str) -> ExtractedTicket:
        try:
            from google.genai import types

            part = types.Part.from_bytes(data=image_bytes, mime_type=mime)
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ExtractedTicket,
            )
            response = self._client.models.generate_content(
                model=self._model,
                contents=[part, STRUCTURED_PROMPT],
                config=config,
            )
        except Exception as e:
            # Never surface SDK error text (may contain API keys, headers, etc.).
            raise VisionExtractionError("gemini call failed") from e

        # Prefer SDK-parsed model if present; fall back to JSON decode.
        # Barcode is decoded by barcode_service, not Gemini — always clear it.
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, ExtractedTicket):
            return parsed.model_copy(update={"barcode": None})
        try:
            payload = json.loads(response.text or "{}")
        except json.JSONDecodeError as e:
            raise VisionExtractionError("gemini returned unparseable JSON") from e
        try:
            return ExtractedTicket.model_validate(payload).model_copy(update={"barcode": None})
        except Exception as e:
            raise VisionExtractionError("gemini response did not match schema") from e
