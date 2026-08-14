import base64
import io
import os
import numpy as np
from typing import Optional
from PIL import Image
import requests

_EASYOCR_READER = None


def get_easyocr_reader():
    """Lazily initializes the EasyOCR reader instance."""
    global _EASYOCR_READER
    if _EASYOCR_READER is None:
        try:
            import easyocr
            _EASYOCR_READER = easyocr.Reader(["en"], gpu=False, verbose=False)
        except Exception:
            _EASYOCR_READER = False
    return _EASYOCR_READER


class OCRClient:
    """Client for performing fast OCR on document images via EasyOCR with Ollama VLM fallback."""

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "glm-ocr",
        timeout: int = 120,
        max_image_dim: int = 1024,
    ):
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_image_dim = max_image_dim

    def _extract_via_easyocr(self, image: Image.Image) -> Optional[str]:
        """Runs fast local OCR via EasyOCR."""
        reader = get_easyocr_reader()
        if not reader:
            return None

        # Convert PIL image to numpy array
        img_np = np.array(image.convert("RGB"))
        results = reader.readtext(img_np, detail=0)
        if results:
            return "\n".join(results)
        return None

    def _image_to_base64(self, image: Image.Image) -> str:
        """Resizes image if too large and converts into compressed base64 JPEG."""
        img = image.copy()
        if max(img.size) > self.max_image_dim:
            img.thumbnail((self.max_image_dim, self.max_image_dim), Image.Resampling.LANCZOS)

        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=85, optimize=True)
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def extract_markdown(
        self,
        image: Image.Image,
        custom_prompt: Optional[str] = None,
    ) -> str:
        """
        Extracts structured text from document images.
        Uses fast local OCR with fallback to Ollama vision.
        """
        # 1. Fast local OCR (< 1s on CPU)
        easyocr_text = self._extract_via_easyocr(image)
        if easyocr_text and len(easyocr_text.strip()) > 10:
            return easyocr_text

        # 2. Fallback to Ollama Vision Model
        prompt = (
            custom_prompt
            or "Extract all text, numbers, and tables from this document image as clean Markdown."
        )
        image_b64 = self._image_to_base64(image)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "options": {
                "temperature": 0.0,
            },
        }

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()

        except Exception as e:
            if easyocr_text:
                return easyocr_text
            raise RuntimeError(f"OCR extraction failed: {e}")
