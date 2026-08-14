from typing import Literal, Optional
from pydantic import BaseModel, Field


class LineItem(BaseModel):
    """Represents a single line item in an invoice, receipt, or purchase order."""
    description: str = Field(description="Description or name of the item/service")
    quantity: Optional[float] = Field(default=None, description="Quantity purchased or ordered")
    unit_price: Optional[float] = Field(default=None, description="Price per unit")
    total: float = Field(description="Total price for this line item")


class ValidationIssue(BaseModel):
    """Represents a validation or sanity check issue discovered in the extracted data."""
    field: str = Field(description="The field name or section where the issue occurred")
    severity: Literal["error", "warning"] = Field(description="Severity level of the issue")
    message: str = Field(description="Detailed explanation of the issue")
    expected: Optional[str] = Field(default=None, description="Expected value or formula")
    actual: Optional[str] = Field(default=None, description="Actual observed value")


class ValidationResult(BaseModel):
    """Overall outcome of business logic and sanity check validations."""
    is_valid: bool = Field(description="True if all critical validation checks passed")
    issues: list[ValidationIssue] = Field(default_factory=list, description="List of validation errors or warnings")


class DocumentExtraction(BaseModel):
    """Unified schema for extracted data from invoices, receipts, and purchase orders."""
    document_type: Literal["invoice", "receipt", "purchase_order", "unknown"] = Field(
        default="unknown", description="Classified type of document"
    )
    vendor_name: Optional[str] = Field(default=None, description="Name of the selling vendor or business")
    vendor_address: Optional[str] = Field(default=None, description="Address or contact details of the vendor")
    customer_name: Optional[str] = Field(default=None, description="Name of the customer or buyer")
    customer_address: Optional[str] = Field(default=None, description="Address or contact details of the customer")
    document_id: Optional[str] = Field(default=None, description="Identifier (e.g. Invoice #, Receipt #, PO #)")
    date: Optional[str] = Field(default=None, description="Issue date in YYYY-MM-DD or document format")
    due_date: Optional[str] = Field(default=None, description="Due date or delivery date in YYYY-MM-DD format")
    line_items: list[LineItem] = Field(default_factory=list, description="List of extracted line items")
    subtotal: Optional[float] = Field(default=None, description="Subtotal amount before tax/discounts")
    tax: Optional[float] = Field(default=None, description="Tax or VAT amount")
    shipping: Optional[float] = Field(default=None, description="Shipping or freight charge")
    discount: Optional[float] = Field(default=None, description="Discount amount applied")
    total: Optional[float] = Field(default=None, description="Grand total amount")
    currency: Optional[str] = Field(default=None, description="Currency symbol or code (e.g. USD, EUR, INR, $)")
    payment_method: Optional[str] = Field(default=None, description="Payment method used (e.g. Cash, Card, Net30)")
    notes: Optional[str] = Field(default=None, description="Additional terms, comments, or notes")
    validation: Optional[ValidationResult] = Field(
        default=None, description="Sanity check and validation results"
    )
