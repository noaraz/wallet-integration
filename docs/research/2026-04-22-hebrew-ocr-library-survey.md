# Hebrew OCR Library Survey — Phase 02

**Date:** 2026-04-22
**Context:** Choosing an OCR/extraction engine for the Telegram bot that converts Hebrew concert-ticket screenshots (PDF or PNG) into Google Wallet passes. Runs in Docker on Cloud Run (no GPU). Cost-conscious: prefer free tier.
**Harness:** `scripts/eval_ocr.py` — runs pdfplumber, tesseract, surya, Gemini 2.5 Flash side-by-side.
**Test input:** Real Hebrew concert ticket for *גיא מזיג* at *אמפי תל אביב*, 6.6 21:00, watermarked, קופת תל אביב vendor. Available as both PDF and PNG.

---

## TL;DR

Use **Gemini 2.5 Flash** (free tier, `google-genai` SDK) as the primary extractor. Keep **Tesseract `heb+eng`** as an offline fallback. Everything else is either unusable (no Hebrew support), too heavy for Cloud Run (Surya), or not free (Claude Vision).

**Prefer PNG input over rasterised PDF** — watermark layers bleed through in the PDF path on Gemini.

---

## Libraries evaluated

### ✅ Actually works — in ranked order

| Library | Hebrew? | Cost | Accuracy on test ticket | Notes |
|---|---|---|---|---|
| **Gemini 2.5 Flash** (`google-genai`) | Native | Free tier (~1500 req/day) | ~100% on PNG; watermark bleed on PDF | Best quality; handles structure, not just text. Accepts PDF or image directly. |
| **Tesseract** with `heb+eng` lang pack | Yes (official `heb.traineddata`) | Free, CPU-only | ~80% — got name, order#, date, venue, ticket ID; **missed price ₪134, zone label, ticket counter, days-to-event badge** | Reliable fallback. Fast. Ships in Debian (`tesseract-ocr-heb`). |
| **pdfplumber** | N/A — pure text-layer extraction | Free | Zero on this ticket (PDF is rasterised) | Useful only as a pre-check: if it returns text, skip OCR entirely. Most ticket exports are image-based PDFs. |
| **Surya** | Yes (`["he", "en"]`) | Free | Not measured (see caveat) | Pulls in PyTorch + NVIDIA CUDA libraries (~2 GB downloaded, 500 MB+ in image). Intentionally excluded from the default `[eval]` extras — `eval_ocr.py` will print `SKIP: No module named 'surya'`. Install manually if you want to benchmark. |

### ❌ Does NOT support Hebrew out of the box — **do not try**

Confirmed via WebSearch + vendor docs on 2026-04-22:

| Library | Why rejected |
|---|---|
| **EasyOCR** | Supports 80+ languages; Hebrew is NOT one of them. Common misconception. |
| **PaddleOCR** | 100+ languages supported; no pretrained Hebrew model. Would require custom training. |
| **docTR** | Pretrained models target English/French; Latin scripts only out of the box. |
| **MMOCR / KerasOCR / RapidOCR** | Same gap — no Hebrew weights. |
| **hebOCR** (yaacov/hebocr) | Hebrew-only; breaks on the mixed `heb+eng` found on every Israeli ticket (English digits for price, date numerals). |
| **HebHTR** | Handwriting-only, not for printed tickets. |
| **Kraken OCR** | RTL-aware but training-heavy; designed for historical manuscripts. Overkill. |

### ⚠️ Works but not picked

| Option | Why not |
|---|---|
| **Claude Vision (Sonnet / Haiku)** | Strong Hebrew accuracy; paid. Violates the free-tier constraint for this personal bot. Reasonable fallback if Gemini API is ever down. |
| **Google Cloud Vision** (`DOCUMENT_TEXT_DETECTION`) | Excellent Hebrew; paid after free tier (~1k images/month free). Gemini Flash free tier is more generous for this volume. |
| **Qwen2.5-VL / MiniCPM-V (local via Ollama)** | Strong on screenshots; free forever. But: no GPU on Cloud Run → 30-90 s per ticket on CPU; image bloat. Worth revisiting only if Gemini free tier becomes insufficient. |
| **Dots.OCR / PaddleOCR-VL** | New VLM-based OCR leaders on 2025 olmOCR-Bench (75–83%). Hebrew support unverified; not measured here. |

---

## Side-by-side results on the test ticket

### PNG input

| Field | Tesseract `heb+eng` | Gemini 2.5 Flash |
|---|---|---|
| Name (נועה רז) | ✅ | ✅ |
| Order # (66143-29558-12017) | ✅ | ✅ |
| Artist (גיא מזיג) | ✅ | ✅ |
| Date (6.6) | ✅ | ✅ |
| Day label (יום ש׳) | ✅ | יום שי (apostrophe→י) |
| Time (21:00) | ✅ | ✅ |
| Venue (אמפי תל אביב) | ✅ | ✅ |
| Zone label (אזור) | ❌ | ✅ |
| Category (עמידה) | ✅ | ✅ |
| **Price (₪134)** | ❌ garbled as `9 ₪` | ✅ |
| **Ticket counter (1/2)** | ❌ | ✅ |
| **Days-to-event (45 ימים)** | ❌ | ✅ |
| Ticket ID (13729590) | ✅ | ✅ |
| Vendor (קופת תל אביב) | ❌ garbled | ✅ |

### PDF input

- pdfplumber: 0 fields (no text layer)
- Tesseract: same fields as PNG, day label corrupted to `wor 6.6`
- Gemini: same content as PNG but with `קופת תלאביב` watermark repeated ~8× due to watermark-layer bleed

**Conclusion:** Prefer PNG. If the user only sends a PDF, render page 1 via `pdf2image` before handing to Gemini.

---

## Decision

1. **Primary engine:** Gemini 2.5 Flash via `google-genai` SDK. Free at this bot's volume.
2. **Offline fallback:** Tesseract `heb+eng`. Already installed in the dev Docker image. Sufficient for the critical-path fields (name, date, venue, order #, ticket ID) when the API is unavailable.
3. **Pre-check:** pdfplumber on PDFs — if it returns text, use that and skip OCR. Rare for tickets but free quality when it hits.
4. **Do not add:** EasyOCR, PaddleOCR, docTR, Surya-in-image, Claude Vision as primary. See rejection table above with specific reasons.
5. **Input handling:** Accept PDF or image. For Gemini, prefer rendering PDF to PNG first to avoid watermark bleed.

---

## References

- Benchmark harness: `scripts/eval_ocr.py`
- Debugging skill: `.claude/skills/debugging-hebrew-ocr/SKILL.md`
- Gemini free tier: https://aistudio.google.com/app/apikey
- EasyOCR language list (no Hebrew): https://github.com/JaidedAI/EasyOCR
- Tesseract `heb.traineddata`: Debian `tesseract-ocr-heb` package
- Hebrew OCR plugin discussion (confirms EasyOCR/PaddleOCR/MMOCR gap): https://medium.com/@2UPLAB/creating-a-plugin-for-hebrew-text-recognition-our-experience-and-solutions-97973d13eeae
- Docling + Hebrew (requires Tesseract backend): https://github.com/docling-project/docling/discussions/41
