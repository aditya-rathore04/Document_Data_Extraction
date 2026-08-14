import json
import logging
from pathlib import Path
from typing import Optional, Union
from src.document_loader import load_document
from src.ocr_client import OCRClient
from src.schemas import DocumentExtraction
from src.structure_client import StructureClient
from src.validator import validate_document

logger = logging.getLogger("document_agent")


class DocumentExtractorAgent:
    """
    Core orchestrator implementing the Perceive → OCR → Structure → Validate pipeline.
    """

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        ocr_model: str = "glm-ocr",
        structure_model: str = "qwen2.5:3b-instruct",
        ocr_timeout: int = 120,
        structure_timeout: int = 60,
    ):
        self.ollama_url = ollama_url
        self.ocr_client = OCRClient(
            ollama_url=ollama_url, model=ocr_model, timeout=ocr_timeout
        )
        self.structure_client = StructureClient(
            ollama_url=ollama_url, model=structure_model, timeout=structure_timeout
        )

    def process_file(self, file_path: Union[str, Path]) -> DocumentExtraction:
        """
        Executes end-to-end extraction and validation on a single document file.
        """
        path = Path(file_path)

        # 1. PERCEIVE: Load document pages
        loaded_doc = load_document(path)

        # 2. OCR: Convert document pages to Markdown
        if loaded_doc.is_text:
            markdown_content = loaded_doc.text_content or ""
        else:
            page_markdowns = []
            for i, page_img in enumerate(loaded_doc.images, start=1):
                page_md = self.ocr_client.extract_markdown(page_img)
                page_markdowns.append(f"--- Page {i} ---\n{page_md}")
            markdown_content = "\n\n".join(page_markdowns)

        # 3. STRUCTURE: Parse Markdown into Pydantic schema using text LLM
        extraction = self.structure_client.structure_document(markdown_content)

        # 4. VALIDATE: Run rule-based business logic and sanity checks
        validation_result = validate_document(extraction)
        extraction.validation = validation_result

        return extraction

    def process_and_save(
        self,
        file_path: Union[str, Path],
        output_dir: Optional[Union[str, Path]] = None,
    ) -> tuple[DocumentExtraction, Path]:
        """
        Processes a document and writes the resulting JSON to the output directory.
        """
        path = Path(file_path)
        out_dir = Path(output_dir) if output_dir else Path("output")
        out_dir.mkdir(parents=True, exist_ok=True)

        extraction = self.process_file(path)

        output_file = out_dir / f"{path.stem}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(extraction.model_dump(), f, indent=2, ensure_ascii=False)

        return extraction, output_file
