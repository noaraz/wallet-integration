---
name: debugging-hebrew-ocr
description: Use when Hebrew ticket extraction returns garbled text, missing fields (price, zone, date), or you need to pick/debug an OCR library for this wallet-integration project. Covers ticket PDFs, PNG screenshots, mixed heb+eng text, and watermarked images.
---

# Debugging Hebrew OCR for Wallet-Integration

## Overview

**Core rule: Run `scripts/eval_ocr.py <file>` on the actual failing ticket before recommending or changing anything.** Hebrew OCR performance varies wildly by input format (PNG vs rasterised PDF), by ticket vendor (Leaan / Eventim / קופת תל אביב), and by which field you care about. Speculation from "prior experience" is wrong often enough that it's forbidden here — measure, then decide.

This skill is a project-specific reference compiled from a real 4-engine benchmark on a Hebrew concert ticket (April 2026). If you think your situation is different, **run the benchmark** and update the tables below.

## When to use

- A Hebrew ticket screenshot / PDF comes in and the extraction is missing or garbled
- You're choosing which OCR library to depend on
- You're adding a new OCR engine to the stack
- A library claims Hebrew support and you want to verify it on this project's inputs

## Step 1 — Always benchmark first

```bash
# PDF or image accepted
docker compose run --rm bot python scripts/eval_ocr.py <path-to-file>
```

The script is at `scripts/eval_ocr.py` and runs four engines side-by-side: pdfplumber, tesseract (`heb+eng`), surya, Gemini 2.5 Flash. **Do not edit `src/` before reading its output.** The output tells you which engine is actually failing on *your* input, not the hypothetical average ticket.

**Required env:** `GEMINI_API_KEY` in `.env` (free at https://aistudio.google.com/app/apikey). docker-compose already passes it through.

## Step 2 — Interpret the output

### Engine ranking on real Israeli concert tickets (measured)

| Engine | Hebrew accuracy | Price / watermarked fields | Cost | Use for |
|---|---|---|---|---|
| **Gemini 2.5 Flash** | ~100% on PNG | ✅ recovers ₪amount, zone labels | Free tier covers personal bot | **Primary** |
| Tesseract `heb+eng` | ~80% | ❌ misses price, zone labels, decorative fonts | Free, CPU | Offline fallback only |
| pdfplumber | N/A unless text-layer PDF | — | Free | Pre-check: returns nothing on rasterised tickets (most of them) |
| Surya | Not benchmarked — pulls ~2 GB PyTorch+CUDA | — | Free but huge image | Skip for Cloud Run; script gracefully `SKIP`s when not installed |

### Input format preference — **PNG beats rasterised PDF**

Gemini reads the full PDF page including watermark layers. On this project's test ticket, the PDF path produced repeated `קופת תלאביב` watermark bleed; the same image as PNG came out clean. **If the user sends both, prefer PNG.** If you only get a PDF, render it via `pdf2image` before handing it to Gemini for best results.

## Step 3 — Known false leads (do NOT attempt)

These libraries are frequently suggested online but **do not support Hebrew out of the box**. Confirmed April 2026 — don't waste time:

- **EasyOCR** — 80+ languages, Hebrew **not** one of them
- **PaddleOCR** — 100+ languages, no Hebrew pretrained model (would need custom training)
- **docTR** — Latin scripts only
- **MMOCR, KerasOCR, RapidOCR** — same gap
- **hebOCR** (yaacov/hebocr) — Hebrew-only, fails on mixed `heb+eng` text found on every Israeli ticket
- **HebHTR** — handwriting only

If someone suggests any of these, push back and cite this skill.

## Step 4 — Gemini integration notes

- SDK: `google-genai` (not the deprecated `google-generativeai`)
- Model: `gemini-2.5-flash` (free tier is sufficient — 1500 req/day as of 2026-04; check current quotas)
- PDFs: pass directly with `mime_type="application/pdf"` — no rendering needed when Gemini is the engine
- Images: `mime_type="image/png"` / `"image/jpeg"` (note: `image/jpg` is invalid — normalise to `jpeg`)
- Prompt it for **raw text in reading order** for OCR comparison, or **strict JSON** matching your Pydantic model for production extraction

Minimal working call pattern is in `scripts/eval_ocr.py:run_gemini()`.

## Common mistakes

| Mistake | Fix |
|---|---|
| Suggesting EasyOCR / PaddleOCR for Hebrew | They don't support it. See Step 3. |
| Assuming Tesseract is "good enough" without running eval | It misses price and zone on Israeli tickets. Measure. |
| Feeding rasterised PDF to Gemini when a PNG is available | PNG wins — watermark bleed in PDF path |
| Adding `surya-ocr` to the main Docker image | Pulls 2 GB of torch+CUDA. Keep it out of the main `[eval]` extras; install manually only if benchmarking. |
| Recommending Claude Vision for "quality" on a cost-conscious personal bot | Use Gemini Flash free tier instead; same quality on Hebrew for this project's tickets |
| Speculating on engine quality from "prior experience" | Run `eval_ocr.py`. Always. |
| Using `image/jpg` mime type | It's `image/jpeg` — Gemini rejects `image/jpg` |
| Forgetting `heb+eng` lang pack for tesseract | Image has English digits + Hebrew text; `heb` alone drops digits |

## Red flags — stop and re-run the benchmark

- "I recall Tesseract handling this fine" — no, measure
- "EasyOCR should work because it lists 80+ languages" — check the actual list, Hebrew isn't there
- "I'll just add PaddleOCR as a fallback" — it has no Hebrew model
- "The user only sent a PDF, I'll just OCR that" — try rendering to PNG first if quality matters
- Editing `src/wallet_bot/services/` before running `scripts/eval_ocr.py` on the failing ticket

## If you update engine choices

Update this skill's tables with new measurements, and keep `scripts/eval_ocr.py` in sync so future debugging sessions start from truth, not memory.
