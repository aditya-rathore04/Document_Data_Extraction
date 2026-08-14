# 📄 Document Data Extractor Agent (Category 2 — Advanced)

> An intelligent, privacy-first **Perceive → OCR → Structure → Validate** pipeline that extracts structured JSON from invoices, retail receipts, and purchase orders using local Ollama models with rule-based business logic validation.

---

## ⚡ 30-Second Review

Reviewers can inspect the deliverables immediately without setting up dependencies:

| Deliverable | Description | File Link |
| :--- | :--- | :--- |
| **Sample Layout 1 (Invoice)** | Corporate B2B Invoice (PDF with multi-column table & tax) | [`sample_documents/invoice_01.pdf`](sample_documents/invoice_01.pdf) |
| **Extracted JSON 1** | Validated JSON with 100% sanity checks passed | [`output/invoice_01.json`](output/invoice_01.json) |
| **Sample Layout 2 (Receipt)** | Retail / Coffee Shop Thermal Receipt (JPG image) | [`sample_documents/receipt_01.jpg`](sample_documents/receipt_01.jpg) |
| **Extracted JSON 2** | Validated JSON with null-safe line item math | [`output/receipt_01.json`](output/receipt_01.json) |
| **Sample Layout 3 (PO)** | Formal Industrial Purchase Order (PDF with SKU items) | [`sample_documents/purchase_order_01.pdf`](sample_documents/purchase_order_01.pdf) |
| **Extracted JSON 3** | Validated JSON with shipping & PO metadata | [`output/purchase_order_01.json`](output/purchase_order_01.json) |
| **Validation & Failure Notes** | Detailed explanation of math checks & 5 failure cases | [`docs/validation_and_failures.md`](docs/validation_and_failures.md) |

---

## 🚀 Quick Start (1-Command Run)

### Linux / macOS
```bash
bash run.sh
```

### Windows
```cmd
run.bat
```

### Manual Run
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Check Ollama server and models
python main.py check-connection

# 3. Process all sample documents
python main.py extract-all

# 4. Or process a single document
python main.py extract sample_documents/invoice_01.pdf
```

---

## 🏗️ Architecture

```
   Document (PDF / Image / Excel / Text)
               │
               ▼
   ┌───────────────────────┐
   │  1. PERCEIVE          │   • PDFs: extracts native text or renders pages to PIL Images
   │  (document_loader.py) │   • Excel (.xlsx/.xls): converts sheets into Markdown tables
   │                       │   • Text (.txt/.csv/.md): reads directly (instant execution)
   │                       │   • Images (.jpg/.png): passes PIL Images to OCR stage
   └───────────┬───────────┘
               │
               ▼
   ┌───────────────────────┐
   │  2. OCR PERCEPTION    │   GLM-OCR Q8 (glm-ocr:q8_0) via Ollama
   │  (ocr_client.py)      │   (Fallback: local EasyOCR engine on CPU)
   └───────────┬───────────┘
               │
               ▼
   ┌───────────────────────┐
   │  3. STRUCTURING       │   Qwen 2.5 (qwen2.5:3b) via Ollama
   │  (structure_client.py)│   Schema alignment into Pydantic DocumentExtraction
   └───────────┬───────────┘
               │
               ▼
   ┌───────────────────────┐
   │  4. VALIDATION        │   Pure Python rule-based sanity checks:
   │  (validator.py)       │   • Line item math: (qty × unit_price == line_total)
   │                       │   • Subtotal check: (Σ line_items == subtotal)
   │                       │   • Grand total check: (subtotal + tax + shipping - discount == total)
   │                       │   • Date logic: (valid calendar dates, due_date >= date)
   └───────────┬───────────┘
               │
               ▼
   Validated JSON Output (output/*.json) + Rich Terminal UI
```

---

## 💡 Key Design Decisions & Tradeoffs

1. **Why Split OCR (`glm-ocr`) and Structuring (`qwen2.5:3b`):**
   - **`glm-ocr` (0.9B)** is SOTA at document OCR and table recognition from images, but its small decoder is not built for complex arbitrary JSON instruction-following.
   - **`qwen2.5:3b` (3B)** is fast and accurate at mapping text to a strict Pydantic JSON schema.
   - Splitting them into two specialized models achieves higher accuracy and runs comfortably on standard CPU hardware (**~4.5GB total RAM**) without requiring a heavy 8B+ VLM.

2. **Crucial Context Window Requirement (`num_ctx: 16384`):**
   - High-resolution document images generate thousands of visual tokens. Ollama's default context of `4096` causes truncation or crashes on full-page invoices. Setting `num_ctx: 16384` explicitly guarantees flawless multi-column table extraction.

3. **Null-Safe Validation for Real-World Variety:**
   - Real retail receipts frequently omit `quantity` or `unit_price` (listing only item and total amount). The validation engine gracefully skips unit arithmetic when fields are null while preserving subtotal and total integrity.

4. **Zero API Cost & 100% Data Privacy:**
   - Sensitive financial and invoice data never leaves the local machine.

---

## 🧪 Testing

Run the automated pytest test suite covering the document loader, schema parsing, and all validation edge cases:

```bash
python -m pytest tests/
```

Output:
```
tests/test_pipeline.py ...... [100%]
6 passed in 0.88s
```

---

## 📁 Repository Structure

```
Document_Data_Extraction/
├── README.md                      # Reviewer guide & documentation
├── requirements.txt               # Pinned Python dependencies
├── run.sh                         # Linux/macOS 1-command runner
├── run.bat                        # Windows 1-command runner
├── main.py                        # CLI entry point with Rich terminal tables
├── src/
│   ├── __init__.py
│   ├── schemas.py                 # Pydantic v2 data models
│   ├── document_loader.py         # PyMuPDF rendering & image/text loader
│   ├── ocr_client.py              # GLM-OCR caller (num_ctx: 16384)
│   ├── structure_client.py        # Qwen2.5-3B structuring caller & JSON parser
│   ├── validator.py               # Rule-based business logic & sanity checker
│   └── agent.py                   # End-to-end pipeline orchestrator
├── sample_documents/              # 3 distinct document layouts
│   ├── invoice_01.pdf             # Corporate B2B invoice (PDF)
│   ├── receipt_01.jpg             # Retail thermal receipt (Image)
│   └── purchase_order_01.pdf      # Industrial purchase order (PDF)
├── output/                        # Extracted JSON files with embedded validation
│   ├── invoice_01.json
│   ├── receipt_01.json
│   └── purchase_order_01.json
├── docs/
│   └── validation_and_failures.md  # Validation rules & failure case analysis
└── tests/
    └── test_pipeline.py           # Pytest test suite
```
