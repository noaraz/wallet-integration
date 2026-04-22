"""Vision service facade.

Everything outside ``services/`` — handlers, main.py, ``scripts/eval_ocr.py``,
the debugging skill — imports vision capabilities from THIS module. The
concrete implementation (Gemini today, possibly Claude Vision / local VLM
later) lives in :mod:`wallet_bot.services.gemini_vision` and is reached only
through the factories below. Changing the backend = swap one import here.

Two capabilities are exposed:

* :class:`VisionServiceProtocol` — structured ``ExtractedTicket`` extraction
  for production handlers.
* :class:`TextDumpProtocol` — raw-text reading-order dump used by the OCR
  evaluation harness and debugging flows.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from wallet_bot.models.ticket import ExtractedTicket


class VisionExtractionError(Exception):
    """Raised when the vision backend fails to extract a ticket.

    Message is deliberately generic — do not interpolate backend error text
    into it (may leak API keys, prompts, or request metadata into logs/replies).
    """


@runtime_checkable
class VisionServiceProtocol(Protocol):
    async def extract(self, image_bytes: bytes, mime_type: str) -> ExtractedTicket: ...


@runtime_checkable
class TextDumpProtocol(Protocol):
    def dump_file(self, path: Path) -> str: ...


# --- factories (the single swap point) --------------------------------------


def create_default_service(api_key: str) -> VisionServiceProtocol:
    """Return the default production vision service for the given API key."""
    from wallet_bot.services.gemini_vision import GeminiVisionService, build_client

    return GeminiVisionService(client=build_client(api_key))


def create_default_text_dumper(api_key: str) -> TextDumpProtocol:
    """Return the default raw-text dumper (used by scripts/eval_ocr.py)."""
    from wallet_bot.services.gemini_vision import (
        GeminiTextDumper,
        build_client,
    )

    return GeminiTextDumper(client=build_client(api_key))
