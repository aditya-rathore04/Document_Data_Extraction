import json
import re
import html
from typing import Optional
import requests
from pydantic import ValidationError
from src.schemas import DocumentExtraction, LineItem


SYSTEM_PROMPT = """You are an expert financial and document data extraction assistant.
Your task is to analyze the provided OCR text of an invoice, receipt, or purchase order, and extract all key data fields into a clean, valid JSON object matching the requested schema.

Schema requirements:
{
  "document_type": "invoice" | "receipt" | "purchase_order" | "unknown",
  "vendor_name": "string or null",
  "vendor_address": "string or null",
  "customer_name": "string or null",
  "customer_address": "string or null",
  "document_id": "string or null (e.g. Invoice #, Receipt #, PO #)",
  "date": "YYYY-MM-DD string or null",
  "due_date": "YYYY-MM-DD string or null",
  "line_items": [
    {
      "description": "string",
      "quantity": float or null,
      "unit_price": float or null,
      "total": float
    }
  ],
  "subtotal": float or null,
  "tax": float or null,
  "shipping": float or null,
  "discount": float or null,
  "total": float or null,
  "currency": "string or null (e.g. USD, CAD, EUR, INR, $)",
  "payment_method": "string or null (e.g. Cash, Visa, Net30)",
  "notes": "string or null"
}

Critical Extraction Rules:
1. Return ONLY the raw JSON object. Do not wrap in markdown quotes if possible, and do not include conversational text.
2. Grouping & Line Items: For each numbered item (01, 02, 03, etc.), extract ONE line item where "description" is the full service/item name. The value in the PRICE/final column (e.g. $72.25, $46.75, $30.60) is the line item "total". Do NOT create separate line items for sub-bullet descriptions.
3. Subtotal & Discount: Set "subtotal" to the subtotal amount (e.g. 149.60 or 176.00). If there is a discount, extract it as a POSITIVE number (e.g. 26.40, NEVER -26.40).
4. Document Type: If the document is a store receipt or customer bill (or has "RECEIPT" header), set "document_type" to "receipt".
5. Clean numeric fields: values must be pure numbers without currency symbols (e.g. 157.08, not "$157.08 CAD").
6. Standardize dates to YYYY-MM-DD whenever discernible.
"""


class StructureClient:
    """Client for calling a text-only instruct LLM (e.g. qwen2.5:3b) to convert OCR markdown into structured JSON."""

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "qwen2.5:3b",
        timeout: int = 120,
    ):
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _preprocess_ocr_text(self, text: str) -> str:
        """Cleans HTML tables and entities produced by vision models into clean text lines."""
        # Unescape HTML entities (&amp;, &#39;, &lt;, etc.)
        t = html.unescape(text)
        # Replace <br> tags with space
        t = re.sub(r"<br\s*/?>", " ", t, flags=re.IGNORECASE)
        # Replace <tr> tags with newline
        t = re.sub(r"</tr>", "\n", t, flags=re.IGNORECASE)
        # Replace <td> and <th> tags with tab / space
        t = re.sub(r"</t[dh]>", " | ", t, flags=re.IGNORECASE)
        # Remove remaining HTML tags
        t = re.sub(r"<[^>]+>", "", t)
        # Clean multiple spaces and blank lines
        lines = [re.sub(r"\s+", " ", line).strip() for line in t.splitlines()]
        cleaned = "\n".join(line for line in lines if line)
        return cleaned

    def _extract_json_substring(self, text: str) -> str:
        """Extracts JSON substring using regex or code-fence stripping."""
        text = text.strip()

        # Strip markdown ```json ... ``` or ``` ... ```
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()

        # If it parses directly, return
        try:
            json.loads(text)
            return text
        except Exception:
            pass

        # Try to find the outer-most JSON object {...}
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            candidate = match.group(1).strip()
            try:
                json.loads(candidate)
                return candidate
            except Exception:
                pass

        return text

    def structure_document(self, markdown_text: str) -> DocumentExtraction:
        """
        Takes raw markdown text from OCR or text input and parses it into a validated DocumentExtraction Pydantic model.
        """
        cleaned_text = self._preprocess_ocr_text(markdown_text)
        user_prompt = f"Extract structured document data from the following OCR text:\n\n{cleaned_text}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": 0.0,
            },
        }

        try:
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            raw_response = data.get("message", {}).get("content", "").strip()

            # Clean and extract JSON string
            json_str = self._extract_json_substring(raw_response)
            parsed_dict = json.loads(json_str)

            # Validate against Pydantic schema
            return DocumentExtraction.model_validate(parsed_dict)

        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Could not connect to Ollama at {self.ollama_url}. Is Ollama running?"
            )
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                raise ValueError(
                    f"Model '{self.model}' not found in Ollama. Please run: ollama pull {self.model}"
                )
            raise RuntimeError(f"Ollama API error: {e}")
        except json.JSONDecodeError as e:
            # Fallback: create an empty extraction object with error notes instead of crashing
            return DocumentExtraction(
                document_type="unknown",
                notes=f"Failed to decode JSON from LLM response: {e}. Raw response snippet: {raw_response[:200]}",
            )
        except ValidationError as e:
            # If validation fails, try best-effort dictionary loading
            return DocumentExtraction(
                document_type="unknown",
                notes=f"Schema validation error: {e}",
            )
        except Exception as e:
            raise RuntimeError(f"Unexpected error during structuring: {e}")
