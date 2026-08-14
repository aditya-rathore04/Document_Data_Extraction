import os
from pathlib import Path
from typing import List, Optional, Union
from PIL import Image
import pymupdf


class LoadedDocument:
    """Represents a loaded document ready for perception / OCR or direct text structuring."""

    def __init__(
        self,
        file_path: Path,
        is_text: bool = False,
        text_content: Optional[str] = None,
        images: Optional[List[Image.Image]] = None,
    ):
        self.file_path = file_path
        self.is_text = is_text
        self.text_content = text_content
        self.images = images or []

    @property
    def page_count(self) -> int:
        if self.is_text:
            return 1
        return len(self.images)

    def __repr__(self) -> str:
        return (
            f"LoadedDocument(path='{self.file_path.name}', is_text={self.is_text}, "
            f"pages={self.page_count})"
        )


def load_document(file_path: Union[str, Path], dpi: int = 120) -> LoadedDocument:
    """
    Loads a PDF, image, or text file and converts it into standard format:
    - PDF: Renders pages into PIL Images at specified DPI (default 120).
    - Image: Opens as PIL Image (converted to RGB).
    - Text/CSV: Reads raw text directly.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found at path: {path}")

    ext = path.suffix.lower()

    # 1. Text or CSV file
    if ext in [".txt", ".csv", ".tsv"]:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return LoadedDocument(file_path=path, is_text=True, text_content=content)

    # 2. PDF Document
    if ext == ".pdf":
        doc = pymupdf.open(path)
        extracted_text_pages: List[str] = []
        images: List[Image.Image] = []
        zoom = dpi / 72.0
        mat = pymupdf.Matrix(zoom, zoom)

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text().strip()
            if text:
                extracted_text_pages.append(f"--- Page {page_num + 1} ---\n{text}")

            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)

        doc.close()

        # If PDF has native selectable text, use it directly (super fast & accurate)
        full_pdf_text = "\n\n".join(extracted_text_pages).strip()
        if len(full_pdf_text) > 30:
            return LoadedDocument(
                file_path=path,
                is_text=True,
                text_content=full_pdf_text,
                images=images,
            )

        # Scanned PDF without text layer: return rendered images for OCR
        return LoadedDocument(file_path=path, is_text=False, images=images)

    # 3. Image file
    if ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"]:
        img = Image.open(path).convert("RGB")
        return LoadedDocument(file_path=path, is_text=False, images=[img])

    raise ValueError(f"Unsupported file format '{ext}' for document: {path.name}")
