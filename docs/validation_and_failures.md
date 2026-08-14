# Validation Logic & Known Failure Cases

This document details the rule-based business logic, sanity checks, and known failure modes for the **Document Data Extractor Agent**.

---

## 1. Validation Logic & Rules

The agent implements a dedicated, deterministic validation engine (`src/validator.py`) executing post-extraction sanity checks on the structured Pydantic model (`DocumentExtraction`).

All currency arithmetic checks employ a floating-point tolerance of **$\pm 0.02$** (`TOLERANCE = 0.02`) to accommodate standard rounding variations in tax and division.

| Check Name | Target Fields | Logic & Rule | Handling of Missing / Null Fields |
| :--- | :--- | :--- | :--- |
| **Line Item Math** | `quantity`, `unit_price`, `total` | $\lvert (\text{quantity} \times \text{unit\_price}) - \text{line\_total} \rvert \le 0.02$ | **Null-safe**: Skipped if `quantity` or `unit_price` is missing (standard for retail receipts). |
| **Subtotal Consistency** | `line_items[].total`, `subtotal` | $\lvert \sum \text{line\_totals} - \text{subtotal} \rvert \le 0.02$ | Checked only when both line items and `subtotal` are present. |
| **Grand Total Consistency** | `subtotal`, `tax`, `discount`, `total` | $\lvert (\text{effective\_subtotal} + \text{tax} - \text{discount}) - \text{total} \rvert \le 0.02$ | Defaults `tax` and `discount` to `0.0` if null; uses $\sum \text{line\_totals}$ if subtotal is omitted. |
| **Date Validity** | `date`, `due_date` | Multi-format parsing (`YYYY-MM-DD`, `DD/MM/YYYY`, `MM/DD/YYYY`, etc.) to verify calendar correctness. | Flags a warning if a date string is malformed or unparseable. |
| **Date Chronology** | `date`, `due_date` | $\text{due\_date} \ge \text{date}$ | Flagged as an **error** if due date precedes document issue date. |
| **Required Schema Fields** | `document_type`, `total`, `line_items` | Checks presence of core classification and financial total. | Flagged as an error if total is missing; warning if unclassified. |

### Severity Levels
- **`error`**: Indicates a mathematical discrepancy, missing total, or chronological contradiction that violates business rules.
- **`warning`**: Indicates missing optional metadata (e.g. unclassified document type, unparseable secondary date string).

---

## 2. Known Failure Cases & Edge Conditions

Real-world document extraction faces edge cases inherent in computer vision, OCR degradation, and varied layout conventions:

### Case 1: Thermal Receipt Degradation & Faded Ink
- **Symptom**: Faint or blurry text on thermal paper (e.g. cash registers) causes digit confusion (`8` read as `3`, `0` read as `O` or `6`).
- **How the Agent Handles It**: The **Line Item Math** and **Grand Total Consistency** checks catch the numerical discrepancy and flag the exact line item where the arithmetic failed, alerting the downstream reviewer.

### Case 2: Ambiguous Decimal & Thousand Separators (International Formats)
- **Symptom**: European invoices use periods for thousands and commas for decimals (e.g. `1.250,50 €` vs US `$1,250.50`).
- **How the Agent Handles It**: The prompt instructs the structuring model to output clean IEEE floats. If commas/dots are confused, the subtotal sum validation check fails, immediately isolating the formatting fault.

### Case 3: Compound Discounts vs Line-Item Discounts
- **Symptom**: Some B2B invoices apply discounts at the item level, while others apply a percentage discount on the entire subtotal after line-item totals are computed.
- **How the Agent Handles It**: If an invoice displays both item-level discounted prices and a summary-level discount, the grand total check isolates whether the discount was double-counted.

### Case 4: Multi-Page Invoices without Intermediate Subtotals
- **Symptom**: Invoices spanning 3+ pages where line items continue across page breaks with headers repeated.
- **How the Agent Handles It**: The document loader aggregates all pages into a unified markdown flow with `--- Page N ---` delimiters, allowing the structuring LLM to gather line items across boundaries.

### Case 5: Handwritten or Stamped Annotations
- **Symptom**: "PAID" rubber stamps or handwritten notes overlapping total boxes.
- **How the Agent Handles It**: `glm-ocr` treats stamps as text; if an overlapping stamp corrupts the OCR digits of the total amount, the subtotal vs grand total check fails and reports the discrepancy in `issues[]`.

---

## 3. Self-Correction & Recovery Architecture

When validation issues are detected:
1. The agent logs the exact failing field, expected value, and observed value in `ValidationIssue`.
2. The complete validation report is serialized into the final JSON output under the `"validation"` key:
```json
{
  "validation": {
    "is_valid": false,
    "issues": [
      {
        "field": "line_items[2]",
        "severity": "error",
        "message": "Line item 2 math mismatch: quantity (3) × unit_price (40.0) = 120.0, but extracted line total is 150.0.",
        "expected": "120.00",
        "actual": "150.00"
      }
    ]
  }
}
```
3. In extended mode, this structured issue list can be passed directly back to `structure_client.py` for targeted re-evaluation without needing a costly re-OCR pass.
