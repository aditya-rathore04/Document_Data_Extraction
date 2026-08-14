import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def create_invoice_pdf(output_path: Path):
    """Layout 1: Corporate B2B Invoice PDF with multi-column table and taxes."""
    doc = SimpleDocTemplate(str(output_path), pagesize=letter, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Heading1"],
        fontSize=24,
        textColor=colors.HexColor("#1A365D"),
        spaceAfter=15,
    )
    normal_style = styles["Normal"]

    # Header section
    story.append(Paragraph("<b>TAX INVOICE</b>", title_style))
    story.append(Spacer(1, 10))

    header_data = [
        [
            Paragraph("<b>Vendor:</b><br/>Acme Cloud Solutions Inc.<br/>100 Enterprise Way, Suite 400<br/>San Francisco, CA 94105<br/>billing@acmecloud.com", normal_style),
            Paragraph("<b>Invoice #:</b> INV-2024-0091<br/><b>Invoice Date:</b> 2024-10-15<br/><b>Due Date:</b> 2024-11-14<br/><b>Currency:</b> USD", normal_style),
        ],
        [
            Paragraph("<b>Billed To:</b><br/>Global Logistics Corp.<br/>450 Industrial Parkway<br/>Chicago, IL 60601", normal_style),
            Paragraph("<b>Payment Terms:</b> Net 30<br/><b>PO Reference:</b> PO-88320", normal_style),
        ]
    ]

    header_table = Table(header_data, colWidths=[260, 260])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 20))

    # Line Items Table
    items_data = [
        ["#", "Item Description", "Qty", "Unit Price ($)", "Total ($)"],
        ["1", "Enterprise Cloud Server Hosting - Standard", "2", "450.00", "900.00"],
        ["2", "Database Storage Allocation (1TB SSD)", "4", "75.00", "300.00"],
        ["3", "Premium Support & SLA Guarantee (Monthly)", "1", "250.00", "250.00"],
        ["4", "SSL Certificate & Domain Management", "1", "50.00", "50.00"],
        ["", "", "", "Subtotal:", "1500.00"],
        ["", "", "", "Tax (10%):", "150.00"],
        ["", "", "", "Grand Total:", "1650.00"],
    ]

    items_table = Table(items_data, colWidths=[30, 270, 45, 95, 80])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, 4), 0.5, colors.HexColor("#CBD5E0")),
        ('FONTNAME', (3, 5), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (3, 7), (-1, 7), colors.HexColor("#EDF2F7")),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 30))

    story.append(Paragraph("<b>Notes & Terms:</b> Payment is due within 30 days. Thank you for your business!", normal_style))
    doc.build(story)


def create_receipt_image(output_path: Path):
    """Layout 2: Retail / Coffee Shop Thermal Receipt Image (JPG)."""
    img_w, img_h = 420, 620
    img = Image.new("RGB", (img_w, img_h), color="#FFFDF7")
    draw = ImageDraw.Draw(img)

    # Use default bitmap font
    font = ImageFont.load_default()

    lines = [
        ("SUNSHINE CAFE & BAKERY", True),
        ("742 Evergreen Terrace", False),
        ("Tel: (555) 019-2834", False),
        ("----------------------------------------", False),
        ("Receipt #: RCPT-84729", False),
        ("Date: 2024-11-02 14:23", False),
        ("Server: Maria S. | Table: 04", False),
        ("----------------------------------------", False),
        ("ITEMS                            TOTAL", True),
        ("----------------------------------------", False),
        ("2x Caramel Macchiato              9.50", False),
        ("1x Almond Croissant                4.75", False),
        ("1x Avocado Toast w/ Egg            8.25", False),
        ("1x Sparkling Mineral Water         3.50", False),
        ("----------------------------------------", False),
        ("Subtotal:                        26.00", False),
        ("Tax (8.5%):                       2.21", False),
        ("TOTAL:                          $28.21", True),
        ("----------------------------------------", False),
        ("Payment Method: VISA (Ending 4092)", False),
        ("Auth Code: 091823", False),
        ("", False),
        ("Thank you for visiting Sunshine Cafe!", False),
        ("Have a wonderful day!", False),
    ]

    y = 25
    for text, is_bold in lines:
        draw.text((30, y), text, fill="#1A1A1A", font=font)
        y += 22

    img.save(output_path, "JPEG", quality=95)


def create_purchase_order_pdf(output_path: Path):
    """Layout 3: Formal Enterprise Purchase Order PDF."""
    doc = SimpleDocTemplate(str(output_path), pagesize=letter, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "POTitle",
        parent=styles["Heading1"],
        fontSize=22,
        textColor=colors.HexColor("#2D3748"),
        spaceAfter=15,
    )
    normal_style = styles["Normal"]

    story.append(Paragraph("<b>OFFICIAL PURCHASE ORDER</b>", title_style))
    story.append(Spacer(1, 10))

    header_data = [
        [
            Paragraph("<b>ISSUED BY:</b><br/>Apex Manufacturing Ltd.<br/>1200 Industrial Blvd<br/>Detroit, MI 48201", normal_style),
            Paragraph("<b>PURCHASE ORDER #:</b> PO-2024-904<br/><b>Date:</b> 2024-09-20<br/><b>Expected Delivery:</b> 2024-10-10", normal_style),
        ],
        [
            Paragraph("<b>VENDOR / SUPPLIER:</b><br/>Precision Tool & Die Co.<br/>88 Machining Way<br/>Cleveland, OH 44101", normal_style),
            Paragraph("<b>SHIP TO:</b><br/>Apex Plant #3 Receiving Dock<br/>1200 Industrial Blvd<br/>Detroit, MI 48201", normal_style),
        ]
    ]

    header_table = Table(header_data, colWidths=[260, 260])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 15))

    items_data = [
        ["Line", "Item SKU", "Description", "Qty", "Unit Price", "Total"],
        ["1", "SKU-9921", "Carbide End Mill 1/2-inch 4-Flute", "10", "$32.00", "$320.00"],
        ["2", "SKU-4402", "High-Speed Steel Drill Bit Set (29-pc)", "5", "$65.00", "$325.00"],
        ["3", "SKU-1190", "Industrial Coolant Fluid (5 Gallon)", "3", "$85.00", "$255.00"],
        ["", "", "", "", "Subtotal:", "$900.00"],
        ["", "", "", "", "Shipping & Freight:", "$50.00"],
        ["", "", "", "", "Grand Total:", "$950.00"],
    ]

    items_table = Table(items_data, colWidths=[35, 75, 230, 40, 70, 70])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#4A5568")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, 3), 0.5, colors.HexColor("#E2E8F0")),
        ('FONTNAME', (4, 4), (-1, -1), 'Helvetica-Bold'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 20))

    story.append(Paragraph("<b>Authorized Signature:</b> ___________________________    <b>Date:</b> 2024-09-20", normal_style))
    doc.build(story)


if __name__ == "__main__":
    samples_dir = Path("sample_documents")
    samples_dir.mkdir(exist_ok=True)

    print("Generating sample document 1: invoice_01.pdf...")
    create_invoice_pdf(samples_dir / "invoice_01.pdf")

    print("Generating sample document 2: receipt_01.jpg...")
    create_receipt_image(samples_dir / "receipt_01.jpg")

    print("Generating sample document 3: purchase_order_01.pdf...")
    create_purchase_order_pdf(samples_dir / "purchase_order_01.pdf")

    print("All 3 diverse layout sample documents generated successfully in sample_documents/!")
