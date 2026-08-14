import pytest
from pathlib import Path
from src.document_loader import load_document
from src.schemas import DocumentExtraction, LineItem
from src.validator import validate_document


def test_document_loader():
    """Verify document loader properly loads PDFs, images, Excel files, and text."""
    samples_dir = Path("sample_documents")

    # 1. Test vector PDF loading (has native text layer)
    pdf_doc = load_document(samples_dir / "test_invoice_text_1.pdf")
    assert pdf_doc.is_text is True
    assert len(pdf_doc.text_content) > 10

    # 2. Test Image loading (treated as visual document)
    img_doc = load_document(samples_dir / "McDonalds_receipt.jpg")
    assert not img_doc.is_text
    assert img_doc.page_count == 1
    assert len(img_doc.images) == 1

    # 3. Test Excel spreadsheet loading
    excel_doc = load_document(samples_dir / "purchase_order.xlsx")
    assert excel_doc.is_text is True
    assert "PO-001" in excel_doc.text_content
    assert "Brochure design" in excel_doc.text_content

    # 4. Test Plain text invoice loading
    txt_doc = load_document(samples_dir / "groceryReceipt.txt")
    assert txt_doc.is_text is True
    assert len(txt_doc.text_content) > 10


def test_validator_perfect_invoice():
    """Verify validator passes a completely consistent invoice."""
    doc = DocumentExtraction(
        document_type="invoice",
        document_id="INV-100",
        date="2024-05-10",
        due_date="2024-06-10",
        line_items=[
            LineItem(description="Web Design", quantity=10, unit_price=50.0, total=500.0),
            LineItem(description="Hosting", quantity=1, unit_price=100.0, total=100.0),
        ],
        subtotal=600.0,
        tax=60.0,
        discount=0.0,
        total=660.0,
        currency="USD",
    )
    result = validate_document(doc)
    assert result.is_valid is True
    assert len(result.issues) == 0


def test_validator_line_item_math_mismatch():
    """Verify validator detects line item quantity * price != total."""
    doc = DocumentExtraction(
        document_type="invoice",
        document_id="INV-101",
        date="2024-05-10",
        line_items=[
            # 2 * 50 should be 100, but total is 120
            LineItem(description="Consulting", quantity=2, unit_price=50.0, total=120.0),
        ],
        subtotal=120.0,
        total=120.0,
    )
    result = validate_document(doc)
    assert result.is_valid is False
    assert any("math mismatch" in issue.message for issue in result.issues)


def test_validator_subtotal_mismatch():
    """Verify validator detects when sum(line_items) != subtotal."""
    doc = DocumentExtraction(
        document_type="invoice",
        document_id="INV-102",
        date="2024-05-10",
        line_items=[
            LineItem(description="Item 1", quantity=1, unit_price=100.0, total=100.0),
            LineItem(description="Item 2", quantity=1, unit_price=200.0, total=200.0),
        ],
        subtotal=250.0,  # Should be 300.0
        total=250.0,
    )
    result = validate_document(doc)
    assert result.is_valid is False
    assert any("Subtotal mismatch" in issue.message for issue in result.issues)


def test_validator_date_chronology_violation():
    """Verify validator detects when due_date is before issue date."""
    doc = DocumentExtraction(
        document_type="invoice",
        document_id="INV-103",
        date="2024-06-15",
        due_date="2024-06-01",  # Precedes issue date!
        line_items=[
            LineItem(description="Service", quantity=1, unit_price=100.0, total=100.0),
        ],
        subtotal=100.0,
        total=100.0,
    )
    result = validate_document(doc)
    assert result.is_valid is False
    assert any("Date logic violation" in issue.message for issue in result.issues)


def test_validator_null_safe_receipt():
    """Verify validator passes receipts where unit_price is omitted."""
    doc = DocumentExtraction(
        document_type="receipt",
        document_id="RCPT-001",
        date="2024-05-10",
        line_items=[
            LineItem(description="Coffee", quantity=None, unit_price=None, total=4.50),
            LineItem(description="Bagel", quantity=1, unit_price=None, total=3.50),
        ],
        subtotal=8.00,
        tax=0.80,
        total=8.80,
    )
    result = validate_document(doc)
    assert result.is_valid is True


def test_validator_shipping_and_discount_math():
    """Verify validator correctly computes subtotal + tax + shipping - discount = total."""
    doc = DocumentExtraction(
        document_type="purchase_order",
        document_id="PO-777",
        date="2024-05-10",
        line_items=[
            LineItem(description="Parts", quantity=1, unit_price=100.0, total=100.0),
        ],
        subtotal=100.0,
        tax=10.0,
        shipping=15.0,
        discount=5.0,
        total=120.0,  # 100 + 10 + 15 - 5 = 120
    )
    result = validate_document(doc)
    assert result.is_valid is True
    assert len(result.issues) == 0


def test_structure_client_html_preprocessor():
    """Verify HTML table preprocessor cleans HTML entities and tags into markdown lines."""
    from src.structure_client import StructureClient

    client = StructureClient()
    raw_html = "<table><tr><td>Item &amp; Service</td><td>$50.00</td></tr></table>"
    cleaned = client._preprocess_ocr_text(raw_html)
    assert "Item & Service" in cleaned
    assert "50.00" in cleaned
    assert "<table" not in cleaned

