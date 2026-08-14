import json
import re
from typing import Optional
import requests
from pydantic import ValidationError
from src.schemas import DocumentExtraction, LineItem


SYSTEM_PROMPT = """You are an expert financial and document data extraction assistant.
Your task is to analyze the provided OCR markdown text of an invoice, receipt, or purchase order, and extract all key data fields into a clean, valid JSON object matching the requested schema.

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
  "currency": "string or null (e.g. USD, EUR, INR, $)",
  "payment_method": "string or null (e.g. Cash, Visa, Net30)",
  "notes": "string or null"
}

Important Rules:
1. Return ONLY the raw JSON object. Do not wrap in markdown quotes if possible, and do not include conversational explanation.
2. If a field is not present or cannot be determined with confidence, use null.
3. Clean numeric fields: values should be pure floats (e.g. 120.50, not "$120.50").
4. Extract all line items accurately. For receipts where unit price is omitted, leave unit_price as null and populate total.
5. Standardize dates to YYYY-MM-DD whenever discernible.
"""


class StructureClient:
    """Client for calling a text-only instruct LLM (e.g. qwen2.5:3b) to convert OCR markdown into structured JSON."""

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "qwen2.5:3b",
        timeout: int = 60,
    ):
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model
        self.timeout = timeout

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
        user_prompt = f"Extract structured document data from the following OCR text:\n\n{markdown_text}"

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
