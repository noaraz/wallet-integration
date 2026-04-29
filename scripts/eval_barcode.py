#!/usr/bin/env python3
"""Decode barcodes/QR codes from a ticket image using zxing-cpp.

Usage:
    docker compose run --rm bot python scripts/eval_barcode.py <path-to-image>
"""

import sys
from pathlib import Path


def _try_decode(image_bytes: bytes):
    import io

    import zxingcpp
    from PIL import Image, ImageFilter, ImageOps

    results = []

    def _scan(img, label):
        found = zxingcpp.read_barcodes(img, try_rotate=True, try_invert=True)
        if found:
            results.append((label, found))

    with Image.open(io.BytesIO(image_bytes)) as img:
        print(f"image: {img.size[0]}x{img.size[1]} {img.mode}")

        # 1. original
        _scan(img.convert("RGB"), "original")

        # 2. greyscale + auto-contrast
        grey = ImageOps.autocontrast(img.convert("L"))
        _scan(grey, "greyscale+autocontrast")

        # 3. sharpen
        sharp = img.convert("L").filter(ImageFilter.SHARPEN)
        _scan(sharp, "sharpen")

        # 4. upscale 2× (helps with small codes in large images)
        w, h = img.size
        big = img.convert("L").resize((w * 2, h * 2), Image.LANCZOS)
        _scan(big, "2× upscale")

    return results


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/eval_barcode.py <path-to-image>", file=sys.stderr)
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    image_bytes = path.read_bytes()
    results = _try_decode(image_bytes)

    if not results:
        print("No barcode found (tried original, greyscale, sharpen, 2× upscale).")
        return

    from wallet_bot.services.barcode_service import _ZXING_FORMAT_MAP
    from wallet_bot.services.wallet_service import _map_barcode_type

    label, found = results[0]
    r = found[0]
    raw_type = _ZXING_FORMAT_MAP.get(r.format.name, r.format.name.upper())
    wallet_type = _map_barcode_type(raw_type)

    print(f"\nDecoded ({label}):")
    print(f"  raw type:    {r.format.name}")
    print(f"  raw value:   {r.text}")
    print("\nWallet pass barcode:")
    print(f"  type:  {wallet_type}")
    print(f"  value: {r.text}")

    # Re-encode and save so the user can see the exact barcode the wallet will use.
    import zxingcpp
    from PIL import Image as PILImage

    out_path = path.with_stem(path.stem + "_wallet_barcode").with_suffix(".png")
    rendered = zxingcpp.write_barcode_to_image(r, scale=8, add_quiet_zones=True)
    h, w = rendered.shape[:2]
    PILImage.frombytes("L", (w, h), bytes(memoryview(rendered))).save(out_path)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
