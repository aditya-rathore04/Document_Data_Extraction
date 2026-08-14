import base64
import io
from typing import Optional
from PIL import Image
import requests


class OCRClient:
    """Client for calling GLM-OCR (or other vision OCR models) via Ollama."""

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "glm-ocr",
        timeout: int = 120,
    ):
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _image_to_base64(self, image: Image.Image) -> str:
        """Converts a PIL Image into a base64 encoded PNG/JPEG string."""
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def extract_markdown(
        self,
        image: Image.Image,
        custom_prompt: Optional[str] = None,
    ) -> str:
        """
        Calls GLM-OCR via Ollama to convert an image into structured markdown.
        CRITICAL: Sets num_ctx to 16384 on every request to handle high-res document images.
        """
        prompt = (
            custom_prompt
            or "Extract all text, numbers, key-value pairs, and tables from this document image as clean, well-formatted Markdown. Maintain table column alignments."
        )

        image_b64 = self._image_to_base64(image)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "options": {
                "num_ctx": 16384,  # Hard requirement to avoid context overflow on images
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
            markdown_output = data.get("response", "").strip()
            return markdown_output

        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Could not connect to Ollama at {self.ollama_url}. Is the Ollama server running?"
            )
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                raise ValueError(
                    f"Model '{self.model}' not found in Ollama. Please run: ollama pull {self.model}"
                )
            raise RuntimeError(f"Ollama API HTTP error ({response.status_code}): {e}")
        except requests.exceptions.Timeout:
            raise TimeoutError(
                f"Ollama request timed out after {self.timeout} seconds. Consider checking CPU/GPU load."
            )
        except Exception as e:
            raise RuntimeError(f"Unexpected error during OCR extraction: {e}")
