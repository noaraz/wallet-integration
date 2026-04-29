"""Barcode decoder facade.

Everything outside ``services/`` imports barcode capabilities from THIS module.
The concrete implementation (ZxingBarcodeDecoder today) lives here and is
reached only through the factory below. Changing the backend = swap one import.

Only one capability is exposed:

* :class:`BarcodeDecoderProtocol` — decode a barcode/QR from raw image bytes.
"""

from __future__ import annotations

import asyncio
import io
from typing import Protocol, runtime_checkable

from wallet_bot.models.ticket import BarcodeResult

# Module-level try/except so unit tests can mock zxingcpp and Image
# at the module level without requiring the libraries installed on the host.
try:
    import zxingcpp
    from PIL import Image
except ImportError:  # pragma: no cover
    zxingcpp = None  # type: ignore[assignment]
    Image = None  # type: ignore[assignment]

_ZXING_FORMAT_MAP: dict[str, str] = {
    "QRCode": "QR_CODE",
    "Code128": "CODE_128",
    "Code39": "CODE_39",
    "Aztec": "AZTEC",
    "PDF417": "PDF_417",
    "DataMatrix": "DATA_MATRIX",
    "EAN8": "EAN_8",
    "EAN13": "EAN_13",
    "UPCA": "UPC_A",
    "UPCE": "UPC_E",
}


@runtime_checkable
class BarcodeDecoderProtocol(Protocol):
    async def decode(self, image_bytes: bytes) -> BarcodeResult | None: ...


class ZxingBarcodeDecoder:
    """Decode barcodes and QR codes from image bytes using zxing-cpp."""

    async def decode(self, image_bytes: bytes) -> BarcodeResult | None:
        return await asyncio.to_thread(self._decode_sync, image_bytes)

    def _decode_sync(self, image_bytes: bytes) -> BarcodeResult | None:
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                results = zxingcpp.read_barcodes(img)
        except Exception:
            return None
        if not results:
            return None
        r = results[0]
        barcode_type = _ZXING_FORMAT_MAP.get(r.format.name, r.format.name.upper())
        return BarcodeResult(barcode_type=barcode_type, barcode_value=r.text or None)


def create_default_decoder() -> BarcodeDecoderProtocol:
    """Return the default barcode decoder for production use."""
    return ZxingBarcodeDecoder()
