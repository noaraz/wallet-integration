"""Unit tests for ZxingBarcodeDecoder — zxing_cpp is mocked throughout."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from wallet_bot.services.barcode_service import (
    BarcodeDecoderProtocol,
    ZxingBarcodeDecoder,
)


def _make_zxing_result(format_name: str, text: str) -> SimpleNamespace:
    fmt = SimpleNamespace(name=format_name)
    return SimpleNamespace(format=fmt, text=text)


class TestZxingBarcodeDecoder:
    async def test_decode_returns_qr_result(self) -> None:
        decoder = ZxingBarcodeDecoder()
        zxing_result = _make_zxing_result("QRCode", "https://ticket.example/abc123")
        with (
            patch("wallet_bot.services.barcode_service.zxing_cpp") as mock_zxing,
            patch("wallet_bot.services.barcode_service.Image"),
        ):
            mock_zxing.read_barcodes.return_value = [zxing_result]
            result = await decoder.decode(b"\x89PNG fake image bytes")

        assert result is not None
        assert result.barcode_type == "QR_CODE"
        assert result.barcode_value == "https://ticket.example/abc123"

    async def test_decode_returns_none_when_no_barcodes_found(self) -> None:
        decoder = ZxingBarcodeDecoder()
        with (
            patch("wallet_bot.services.barcode_service.zxing_cpp") as mock_zxing,
            patch("wallet_bot.services.barcode_service.Image"),
        ):
            mock_zxing.read_barcodes.return_value = []
            result = await decoder.decode(b"image with no barcode")

        assert result is None

    async def test_decode_maps_code128_format(self) -> None:
        decoder = ZxingBarcodeDecoder()
        zxing_result = _make_zxing_result("Code128", "1234567890")
        with (
            patch("wallet_bot.services.barcode_service.zxing_cpp") as mock_zxing,
            patch("wallet_bot.services.barcode_service.Image"),
        ):
            mock_zxing.read_barcodes.return_value = [zxing_result]
            result = await decoder.decode(b"img")

        assert result is not None
        assert result.barcode_type == "CODE_128"

    async def test_decode_maps_aztec_format(self) -> None:
        decoder = ZxingBarcodeDecoder()
        zxing_result = _make_zxing_result("Aztec", "payload")
        with (
            patch("wallet_bot.services.barcode_service.zxing_cpp") as mock_zxing,
            patch("wallet_bot.services.barcode_service.Image"),
        ):
            mock_zxing.read_barcodes.return_value = [zxing_result]
            result = await decoder.decode(b"img")

        assert result is not None
        assert result.barcode_type == "AZTEC"

    async def test_decode_returns_none_barcode_value_for_empty_text(self) -> None:
        decoder = ZxingBarcodeDecoder()
        zxing_result = _make_zxing_result("QRCode", "")
        with (
            patch("wallet_bot.services.barcode_service.zxing_cpp") as mock_zxing,
            patch("wallet_bot.services.barcode_service.Image"),
        ):
            mock_zxing.read_barcodes.return_value = [zxing_result]
            result = await decoder.decode(b"img")

        assert result is not None
        assert result.barcode_value is None

    async def test_decode_falls_back_to_uppercase_for_unknown_format(self) -> None:
        decoder = ZxingBarcodeDecoder()
        zxing_result = _make_zxing_result("SomeExoticFormat", "value")
        with (
            patch("wallet_bot.services.barcode_service.zxing_cpp") as mock_zxing,
            patch("wallet_bot.services.barcode_service.Image"),
        ):
            mock_zxing.read_barcodes.return_value = [zxing_result]
            result = await decoder.decode(b"img")

        assert result is not None
        assert result.barcode_type == "SOMEEXOTICFORMAT"

    async def test_decode_takes_first_barcode_when_multiple_found(self) -> None:
        decoder = ZxingBarcodeDecoder()
        first = _make_zxing_result("QRCode", "first-payload")
        second = _make_zxing_result("Code128", "second-payload")
        with (
            patch("wallet_bot.services.barcode_service.zxing_cpp") as mock_zxing,
            patch("wallet_bot.services.barcode_service.Image"),
        ):
            mock_zxing.read_barcodes.return_value = [first, second]
            result = await decoder.decode(b"img")

        assert result is not None
        assert result.barcode_value == "first-payload"

    def test_protocol_satisfied(self) -> None:
        decoder = ZxingBarcodeDecoder()
        assert isinstance(decoder, BarcodeDecoderProtocol)
