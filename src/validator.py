import re
from datetime import datetime
from typing import List, Optional
from src.schemas import DocumentExtraction, ValidationIssue, ValidationResult


TOLERANCE = 0.02  # Floating point tolerance for currency math checks


def parse_date_safely(date_str: Optional[str]) -> Optional[datetime]:
    """Attempts to parse a date string across common document date formats."""
    if not date_str:
        return None

    cleaned = date_str.strip()
    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%m-%d-%Y",
        "%d.%m.%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue

    return None


def validate_document(doc: DocumentExtraction) -> ValidationResult:
    """
    Executes rule-based business logic and sanity checks on extracted document data.
    Pure Python execution with no LLM dependency.
    """
    issues: List[ValidationIssue] = []

    # 1. Required Fields Check
    if doc.document_type == "unknown":
        issues.append(
            ValidationIssue(
                field="document_type",
                severity="warning",
                message="Document type could not be classified (invoice, receipt, or purchase_order).",
                expected="invoice | receipt | purchase_order",
                actual=doc.document_type,
            )
        )

    if doc.total is None:
        issues.append(
            ValidationIssue(
                field="total",
                severity="error",
                message="Grand total amount is missing from the extraction.",
                expected="Numeric total > 0",
                actual=None,
            )
        )

    if not doc.line_items:
        issues.append(
            ValidationIssue(
                field="line_items",
                severity="warning",
                message="No line items were extracted from the document.",
                expected="At least 1 line item",
                actual="0 items",
            )
        )

    # 2. Line Item Math Checks (Null-safe for receipts)
    line_item_sum = 0.0
    for idx, item in enumerate(doc.line_items, start=1):
        line_item_sum += item.total

        # Only perform qty * unit_price check if both fields are present
        if item.quantity is not None and item.unit_price is not None:
            expected_line_total = round(item.quantity * item.unit_price, 2)
            if abs(expected_line_total - item.total) > TOLERANCE:
                issues.append(
                    ValidationIssue(
                        field=f"line_items[{idx}]",
                        severity="error",
                        message=(
                            f"Line item {idx} ('{item.description}') math mismatch: "
                            f"quantity ({item.quantity}) × unit_price ({item.unit_price}) = {expected_line_total}, "
                            f"but extracted line total is {item.total}."
                        ),
                        expected=f"{expected_line_total:.2f}",
                        actual=f"{item.total:.2f}",
                    )
                )

    # 3. Subtotal Consistency Check
    if doc.subtotal is not None and doc.line_items:
        if abs(line_item_sum - doc.subtotal) > TOLERANCE:
            issues.append(
                ValidationIssue(
                    field="subtotal",
                    severity="error",
                    message=(
                        f"Subtotal mismatch: Sum of extracted line items ({line_item_sum:.2f}) "
                        f"does not equal extracted subtotal ({doc.subtotal:.2f})."
                    ),
                    expected=f"{line_item_sum:.2f}",
                    actual=f"{doc.subtotal:.2f}",
                )
            )

    # 4. Grand Total Consistency Check
    effective_base = doc.subtotal if doc.subtotal is not None else line_item_sum
    tax = doc.tax if doc.tax is not None else 0.0
    shipping = doc.shipping if doc.shipping is not None else 0.0
    discount = doc.discount if doc.discount is not None else 0.0

    if doc.total is not None and (doc.subtotal is not None or doc.line_items):
        expected_grand_total = round(effective_base + tax + shipping - discount, 2)
        if abs(expected_grand_total - doc.total) > TOLERANCE:
            issues.append(
                ValidationIssue(
                    field="total",
                    severity="error",
                    message=(
                        f"Grand total mismatch: Base ({effective_base:.2f}) + Tax ({tax:.2f}) + "
                        f"Shipping ({shipping:.2f}) - Discount ({discount:.2f}) = {expected_grand_total:.2f}, "
                        f"but extracted total is {doc.total:.2f}."
                    ),
                    expected=f"{expected_grand_total:.2f}",
                    actual=f"{doc.total:.2f}",
                )
            )

    # 5. Date Validity Checks
    parsed_date = None
    if doc.date:
        parsed_date = parse_date_safely(doc.date)
        if parsed_date is None:
            issues.append(
                ValidationIssue(
                    field="date",
                    severity="warning",
                    message=f"Date string '{doc.date}' could not be parsed into a valid calendar date.",
                    expected="Valid date (e.g. YYYY-MM-DD)",
                    actual=doc.date,
                )
            )

    parsed_due_date = None
    if doc.due_date:
        parsed_due_date = parse_date_safely(doc.due_date)
        if parsed_due_date is None:
            issues.append(
                ValidationIssue(
                    field="due_date",
                    severity="warning",
                    message=f"Due date string '{doc.due_date}' could not be parsed into a valid calendar date.",
                    expected="Valid date (e.g. YYYY-MM-DD)",
                    actual=doc.due_date,
                )
            )

    # 6. Date Chronology Check (Due Date >= Invoice Date)
    if parsed_date and parsed_due_date:
        if parsed_due_date < parsed_date:
            issues.append(
                ValidationIssue(
                    field="due_date",
                    severity="error",
                    message=(
                        f"Date logic violation: Due date ({doc.due_date}) precedes "
                        f"document issue date ({doc.date})."
                    ),
                    expected=f">= {doc.date}",
                    actual=doc.due_date,
                )
            )

    # Calculate overall is_valid: True if no error severity issues exist
    has_errors = any(issue.severity == "error" for issue in issues)
    return ValidationResult(is_valid=not has_errors, issues=issues)
