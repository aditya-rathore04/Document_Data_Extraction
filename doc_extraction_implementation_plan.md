# Document Data Extractor Agent — 24-Hour Implementation Plan

A **Perceive → Structure → Validate** pipeline that extracts structured JSON from
messy documents (invoices, receipts, purchase orders) using two small local
Ollama models. CPU-friendly, zero API cost, ~4.5GB total model footprint.

This plan supersedes the original single-VLM design. Two changes drive
everything below:
1. **Split perception and structuring into two small models** instead of one
   large vision model doing both.
2. **Self-correction is a stretch goal, not a core deliverable** — validation
   reporting is core; automatic re-querying is only added if time remains.

---

## Architecture

```
  Document (PDF / Image / Text)
          │
          ▼
  ┌───────────────────┐
  │  1. PERCEIVE      │   PyMuPDF renders PDF pages → PIL Images
  │  (Document Loader)│   Images pass through directly
  └────────┬──────────┘   Text files skip straight to step 3
           │
           ▼
  ┌───────────────────┐
  │  2. OCR           │   GLM-OCR (0.9B, ~2.5GB RAM) via Ollama
  │  (glm-ocr)        │   Image → clean markdown (text, tables, formulas)
  └────────┬──────────┘   num_ctx MUST be set to 16384+ (default 4096 crashes on images)
           │
           ▼
  ┌───────────────────┐
  │  3. STRUCTURE     │   Small text-only instruct LLM (qwen2.5:3b-instruct
  │  (text LLM)       │   or llama3.2:3b, ~2GB) via Ollama
  └────────┬──────────┘   Markdown + schema prompt → JSON → Pydantic model
           │
           ▼
  ┌───────────────────┐
  │  4. VALIDATE      │   Rule-based, no LLM:
  │  (Business Logic) │   • qty × unit_price ≈ line_total (tolerance 0.02)
  └────────┬──────────┘   • Σ line_totals ≈ subtotal
           │              • subtotal + tax - discount ≈ total
           │              • dates parse and due_date ≥ date
           ▼
     is_valid: true/false + issues[] written into output JSON
           │
           ▼
  ┌───────────────────┐
  │  5. SELF-CORRECT  │   STRETCH GOAL ONLY (see Cut List)
  │  (optional)       │   One retry, feedback goes to step 3 (text LLM),
  └───────────────────┘   not step 2 — cheaper and more controllable.
```

**Why split OCR and structuring:** GLM-OCR is purpose-built to turn an image
into accurate markdown (it's SOTA on table/formula recognition), but it's a
0.5B-decoder OCR model, not a general instruction-follower — it's not the
right tool to reliably fill an arbitrary JSON schema. A small text-only LLM
is cheap, fast (no image encoding), and far more reliable at "map this text
into this schema" than either a single overloaded VLM or GLM-OCR alone.

---

## Project Structure

```
Document_Data_Extraction/
├── README.md                      # "30-second review" section first, full setup second
├── requirements.txt
├── run.sh                         # ONE command: pulls models if missing, runs extract-all
├── main.py                        # CLI entry point
├── src/
│   ├── __init__.py
│   ├── document_loader.py         # PDF/Image/Text → PIL Image(s) or raw text
│   ├── ocr_client.py              # GLM-OCR call (image → markdown), num_ctx=16384
│   ├── structure_client.py        # text LLM call (markdown → JSON), schema-aware prompt
│   ├── schemas.py                 # Pydantic models
│   ├── validator.py               # Math/date checks, no LLM
│   └── agent.py                   # Orchestrator: loader → ocr → structure → validate
├── sample_documents/              # REAL documents pulled from a public dataset
│   ├── invoice_01.pdf             # (SROIE / CORD, or a few anonymized real invoices)
│   ├── receipt_01.jpg
│   └── purchase_order_01.pdf
├── output/
│   ├── invoice_01.json
│   ├── receipt_01.json
│   └── purchase_order_01.json
├── demo.gif                        # 10-min-to-record terminal capture, run end-to-end
└── docs/
    └── validation_and_failures.md  # validation logic + known failure cases
```

---

## Core Components

### `src/schemas.py`
Single unified `DocumentExtraction` Pydantic model covering all three
document types (invoice/receipt/PO), same shape as originally planned:
`document_type`, vendor/customer fields, `document_id`, `date`, `due_date`,
`line_items: list[LineItem]`, `subtotal`, `tax`, `discount`, `total`,
`currency`, `payment_method`, `notes`. Add a `validation: ValidationResult`
field so the validation outcome ships inside the same JSON file.

### `src/document_loader.py`
- PDF → PyMuPDF (`fitz`) renders pages to PIL Images at 200 DPI
- Image (PNG/JPG/WEBP) → loaded directly via Pillow
- Text/CSV → read as raw string, skip OCR, go straight to Structure step

### `src/ocr_client.py`
- Calls `glm-ocr` via Ollama `/api/generate`, **`num_ctx: 16384` set explicitly
  on every request** (hard requirement — default context crashes on images)
- Returns markdown text preserving table structure

### `src/structure_client.py`
- Calls a small text-only instruct model (`qwen2.5:3b-instruct` or
  `llama3.2:3b`) with the OCR markdown + the JSON schema in the prompt
- Strips markdown code fences, falls back to regex JSON extraction if the
  model wraps output in explanation text
- Parses into the Pydantic model; catch and log parse failures rather than
  crashing

### `src/validator.py`
Pure Python, no LLM calls:

| Check | Logic |
|---|---|
| Line item math | `abs(qty × unit_price - line_total) < 0.02` — **skip gracefully if qty or unit_price is null** (many receipts only have item + price) |
| Subtotal consistency | `abs(Σ line_totals - subtotal) < 0.02` |
| Grand total consistency | `abs(subtotal + tax - discount - total) < 0.02` |
| Date validity | Parse dates, reject malformed (e.g. `2024-13-45`) |
| Date logic | `due_date >= date` if both present |
| Currency parsing | Strip currency symbols (`₹`, `$`, `€`) and thousands separators before parsing numbers — flag as a known failure case if ambiguous |
| Required fields | `document_type`, `total`, at least one line item |

### `src/agent.py`
Deterministic orchestrator, not a chatbot:
`load → ocr → structure → validate → write output JSON (with validation
issues embedded, is_valid flag set)`. Self-correction is NOT called by
default — see Cut List.

### `main.py`
```bash
python main.py extract sample_documents/invoice_01.pdf
python main.py extract-all
python main.py check-connection
```
`rich` for colored terminal output showing extracted fields + pass/fail.

### `run.sh`
```bash
#!/bin/bash
set -e
ollama pull glm-ocr 2>/dev/null || true
ollama pull qwen2.5:3b-instruct 2>/dev/null || true
pip install -r requirements.txt --quiet
python main.py extract-all
echo "Done — see output/ for results, docs/validation_and_failures.md for notes."
```
This is the single command a reviewer needs to reproduce everything.

---

## Sample Documents — use real ones, don't hand-build

Pull 3 documents with genuinely different layouts from a public dataset
(SROIE or CORD receipt/invoice datasets, or a few real anonymized invoice
PDFs found online) instead of generating synthetic ones with reportlab.
This saves 2+ hours and — importantly — makes "handles varied layouts" a
tested claim rather than one tuned against documents you made yourself.

---

## Cut List (what to drop if time runs short)

Ranked by what to cut first if the 24 hours get tight:

1. **Automatic self-correction / retry loop** — cut first. Ship
   `is_valid: false` + itemized `issues[]` in the output JSON instead. This
   satisfies "sanity checks" in the rubric without the retry-prompt
   engineering risk.
2. **Streamlit/web UI** — not required by the rubric; CLI + rich is enough.
3. **More than 3 sample documents** — 3 with genuinely different layouts is
   the requirement; don't over-invest here.
4. **Multi-page invoice handling** — document as a known failure case
   instead of solving it.

Do NOT cut: the validator (it's cheap to build and is the most rubric-visible
part), the README's "30-second review" section, or committing pre-generated
output JSONs.

---

## 24-Hour Schedule

| Hours | Task |
|---|---|
| 0–1 | Environment setup: install Ollama, pull `glm-ocr` and `qwen2.5:3b-instruct`, confirm `num_ctx=16384` works on a test image, `pip install` deps |
| 1–2.5 | `document_loader.py` — PDF/image/text handling |
| 2.5–3.5 | `schemas.py` — Pydantic models |
| 3.5–6 | `ocr_client.py` + `structure_client.py` — the highest-risk part; budget extra time for JSON-parsing reliability |
| 6–8 | `validator.py` — all checks, including null-safe line item math and currency parsing |
| 8–9 | `agent.py` orchestrator wiring it all together |
| 9–10 | `main.py` CLI + `rich` output |
| 10–11 | Pull 3 real sample documents (SROIE/CORD or web), run pipeline against them |
| 11–15 | End-to-end debugging — this WILL take this long, don't schedule anything else here |
| 15–16 | `docs/validation_and_failures.md` |
| 16–17 | README with "30-second review" section first |
| 17–17.5 | `run.sh` + verify it works from a clean environment |
| 17.5–18 | Record `demo.gif` |
| 18–20 | Buffer for whatever broke (something will) |
| 20–24 | **Only if ahead of schedule**: add single-retry self-correction, feedback routed to `structure_client.py` (text-only re-query, not a new OCR pass) |

---

## Reviewer Convenience Checklist

- [ ] `output/*.json` committed and populated — reviewer can inspect results
      with zero setup
- [ ] `docs/validation_and_failures.md` written and linked from the top of
      the README
- [ ] `run.sh` reproduces everything in one command
- [ ] `demo.gif` recorded showing a full run
- [ ] README leads with a "30-second review" section (links to output +
      failure doc + gif) before the full setup instructions
- [ ] Verified `run.sh` works from a genuinely clean clone, not just your
      dev machine

---

## Dependencies (`requirements.txt`)

```
PyMuPDF>=1.24.0
Pillow>=10.0.0
pydantic>=2.0.0
requests>=2.31.0
rich>=13.0.0
```

No `reportlab` needed — sample documents are real, not generated. No CUDA,
no torch, no GPU dependency; GPU requirement (if any) lives entirely on
Ollama's side and is optional given both models run comfortably on CPU.
