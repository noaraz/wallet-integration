"""Unit tests for GeminiVisionService — the google-genai client is mocked."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from wallet_bot.models.ticket import ExtractedTicket
from wallet_bot.services.gemini_vision import (
    GeminiVisionService,
    _normalise_mime,
)
from wallet_bot.services.vision_service import VisionExtractionError


class TestNormaliseMime:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("image/png", "image/png"),
            ("image/PNG", "image/png"),
            ("image/jpeg", "image/jpeg"),
            ("image/jpg", "image/jpeg"),  # Gemini rejects image/jpg
            ("image/JPG", "image/jpeg"),
        ],
    )
    def test_normalises(self, raw: str, expected: str) -> None:
        assert _normalise_mime(raw) == expected

    def test_rejects_non_image(self) -> None:
        with pytest.raises(ValueError):
            _normalise_mime("application/pdf")

    def test_rejects_unknown_image(self) -> None:
        with pytest.raises(ValueError):
            _normalise_mime("image/gif")


class TestGeminiVisionService:
    def _make_fake_client(self, response_text: str) -> MagicMock:
        response = SimpleNamespace(parsed=None, text=response_text)
        models = MagicMock()
        models.generate_content = MagicMock(return_value=response)
        return MagicMock(models=models)

    async def test_extract_returns_parsed_ticket(self) -> None:
        raw_json = (
            '{"event_name": "גיא מזיג", "venue": "אמפי תל אביב", "raw_text": "full transcription"}'
        )
        client = self._make_fake_client(raw_json)
        svc = GeminiVisionService(client=client, model="gemini-2.5-flash")

        ticket = await svc.extract(b"\x89PNG fake", mime_type="image/png")

        assert isinstance(ticket, ExtractedTicket)
        assert ticket.event_name == "גיא מזיג"
        assert ticket.venue == "אמפי תל אביב"
        assert ticket.raw_text == "full transcription"

    async def test_extract_sends_schema_and_json_mime(self) -> None:
        client = self._make_fake_client('{"event_name": "x"}')
        svc = GeminiVisionService(client=client, model="gemini-2.5-flash")

        await svc.extract(b"img", mime_type="image/jpeg")

        call = client.models.generate_content.call_args
        assert call.kwargs["model"] == "gemini-2.5-flash"
        cfg = call.kwargs["config"]
        assert cfg.response_mime_type == "application/json"
        assert cfg.response_schema is ExtractedTicket

    async def test_extract_normalises_jpg_mime(self) -> None:
        client = self._make_fake_client('{"event_name": "x"}')
        svc = GeminiVisionService(client=client, model="gemini-2.5-flash")

        await svc.extract(b"img", mime_type="image/jpg")

        part = client.models.generate_content.call_args.kwargs["contents"][0]
        assert part.inline_data.mime_type == "image/jpeg"

    async def test_extract_wraps_sdk_errors_in_vision_error(self) -> None:
        client = MagicMock()
        client.models.generate_content.side_effect = RuntimeError("boom: api down")
        svc = GeminiVisionService(client=client, model="gemini-2.5-flash")

        with pytest.raises(VisionExtractionError):
            await svc.extract(b"img", mime_type="image/png")

    async def test_extract_wraps_invalid_json(self) -> None:
        client = self._make_fake_client("not valid json {")
        svc = GeminiVisionService(client=client, model="gemini-2.5-flash")

        with pytest.raises(VisionExtractionError):
            await svc.extract(b"img", mime_type="image/png")

    async def test_extract_never_leaks_sdk_error_message(self) -> None:
        client = MagicMock()
        client.models.generate_content.side_effect = RuntimeError(
            "boom api key=abc123 leaked",
        )
        svc = GeminiVisionService(client=client, model="gemini-2.5-flash")

        try:
            await svc.extract(b"img", mime_type="image/png")
        except VisionExtractionError as e:
            assert "abc123" not in str(e)
            assert "api key" not in str(e).lower()
