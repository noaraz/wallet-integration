#!/usr/bin/env python3
"""Standalone OCR benchmark: compare pdfplumber, tesseract, surya, and Gemini on a ticket file.

Usage:
    docker compose run --rm bot python scripts/eval_ocr.py <path-to-file>

Gemini requires GEMINI_API_KEY (or GOOGLE_API_KEY) in the environment.
Get a free key at https://aistudio.google.com/app/apikey
"""

import os  # used inside run_gemini via os.environ
import sys
from pathlib import Path

# Gemini model / prompt / client construction live in the production vision
# service so the script, skill, and handlers cannot drift.
from wallet_bot.services.gemini_vision import GEMINI_DEFAULT_MODEL as GEMINI_MODEL


def _sep(label: str) -> str:
    fill = "─" * max(1, 50 - len(label) - 4)
    return f"\n── {label} {fill}"


def _is_pdf(path: Path) -> bool:
    return path.suffix.lower() == ".pdf"


def _render_pdf(path: Path):
    """Return list of PIL Images, one per page. Raises ImportError if pdf2image missing."""
    from pdf2image import convert_from_path

    return convert_from_path(str(path))


def run_pdfplumber(path: Path) -> str:
    if not _is_pdf(path):
        return "N/A (not a PDF)"
    try:
        import pdfplumber
    except ImportError:
        return "SKIP: pdfplumber not installed"

    with pdfplumber.open(path) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages).strip() or "(no text extracted)"


def run_tesseract(path: Path) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as e:
        return f"SKIP: {e}"

    try:
        if _is_pdf(path):
            try:
                images = _render_pdf(path)
            except ImportError as e:
                return f"SKIP: {e}"
        else:
            images = [Image.open(path)]

        pages = [pytesseract.image_to_string(img, lang="heb+eng") for img in images]
        return "\n".join(pages).strip() or "(no text extracted)"
    except Exception as e:
        return f"ERROR: {e}"


def run_surya(path: Path) -> str:
    try:
        from PIL import Image
        from surya.model.detection.model import load_model as load_det_model
        from surya.model.detection.model import (
            load_processor as load_det_processor,
        )
        from surya.model.recognition.model import load_model as load_rec_model
        from surya.model.recognition.processor import (
            load_processor as load_rec_processor,
        )
        from surya.ocr import run_ocr
    except ImportError as e:
        return f"SKIP: {e}"

    try:
        if _is_pdf(path):
            try:
                images = _render_pdf(path)
            except ImportError as e:
                return f"SKIP: {e}"
        else:
            images = [Image.open(path).convert("RGB")]

        langs = [["he", "en"]] * len(images)
        det_model, det_processor = load_det_model(), load_det_processor()
        rec_model, rec_processor = load_rec_model(), load_rec_processor()
        predictions = run_ocr(images, langs, det_model, det_processor, rec_model, rec_processor)

        pages = []
        for result in predictions:
            page_text = "\n".join(line.text for line in result.text_lines)
            pages.append(page_text)
        return "\n".join(pages).strip() or "(no text extracted)"
    except Exception as e:
        return f"ERROR: {e}"


def run_gemini(path: Path) -> str:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return "SKIP: set GEMINI_API_KEY (https://aistudio.google.com/app/apikey)"

    try:
        from wallet_bot.services.vision_service import create_default_text_dumper
    except ImportError as e:
        return f"SKIP: {e} (pip install google-genai)"

    model = os.environ.get("GEMINI_MODEL")  # optional override for outages
    try:
        dumper = create_default_text_dumper(api_key, model=model)
        return dumper.dump_file(path).strip() or "(no text extracted)"
    except Exception as e:
        return f"ERROR: {e}"


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/eval_ocr.py <path-to-file>", file=sys.stderr)
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    print(_sep("pdfplumber"))
    print(run_pdfplumber(path))

    print(_sep("tesseract (heb+eng)"))
    print(run_tesseract(path))

    print(_sep("surya (he+en)"))
    print(run_surya(path))

    print(_sep(f"gemini ({GEMINI_MODEL})"))
    print(run_gemini(path))

    print()


if __name__ == "__main__":
    main()
