import json
import logging
import time
from pathlib import Path
from typing import Callable, Optional, Union
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
        ocr_model: str = "glm-ocr:q8_0",
        structure_model: str = "qwen2.5:3b",
        ocr_timeout: int = 180,
        structure_timeout: int = 120,
    ):
        self.ollama_url = ollama_url
        self.ocr_model = ocr_model
        self.structure_model = structure_model
        self.ocr_client = OCRClient(
            ollama_url=ollama_url, model=ocr_model, timeout=ocr_timeout
        )
        self.structure_client = StructureClient(
            ollama_url=ollama_url, model=structure_model, timeout=structure_timeout
        )

    def process_file(
        self,
        file_path: Union[str, Path],
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> DocumentExtraction:
        """
        Executes end-to-end extraction and validation on a single document file.
        Notifies progress_callback(stage, description) as each phase runs.
        """
        path = Path(file_path)

        def report(stage: str, msg: str):
            if progress_callback:
                progress_callback(stage, msg)

        # 1. PERCEIVE: Load document pages
        report("load", f"[Stage 1/4] Loading document & inspecting text layers: {path.name}")
        loaded_doc = load_document(path)

        # 2. OCR: Convert document pages to Markdown / text
        if loaded_doc.is_text:
            report("ocr", "[Stage 2/4] Direct native text layer found (bypassing visual OCR)...")
            markdown_content = loaded_doc.text_content or ""
        else:
            page_markdowns = []
            for i, page_img in enumerate(loaded_doc.images, start=1):
                report(
                    "ocr",
                    f"[Stage 2/4] Running GLM-OCR perception on page {i}/{loaded_doc.page_count} ({self.ocr_model})...",
                )
                page_md = self.ocr_client.extract_markdown(page_img)
                page_markdowns.append(f"--- Page {i} ---\n{page_md}")
            markdown_content = "\n\n".join(page_markdowns)

        # 3. STRUCTURE: Parse Markdown into Pydantic schema using text LLM
        report(
            "structure",
            f"[Stage 3/4] Reasoning & structuring JSON fields ({self.structure_model})...",
        )
        extraction = self.structure_client.structure_document(markdown_content)

        # 4. VALIDATE: Run rule-based business logic and sanity checks
        report("validate", "[Stage 4/4] Executing mathematical sanity checks & date rules...")
        validation_result = validate_document(extraction)
        extraction.validation = validation_result

        return extraction

    def process_and_save(
        self,
        file_path: Union[str, Path],
        output_dir: Optional[Union[str, Path]] = None,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> tuple[DocumentExtraction, Path]:
        """
        Processes a document and writes the resulting JSON to the output directory.
        """
        path = Path(file_path)
        out_dir = Path(output_dir) if output_dir else Path("output")
        out_dir.mkdir(parents=True, exist_ok=True)

        extraction = self.process_file(path, progress_callback=progress_callback)

        output_file = out_dir / f"{path.stem}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(extraction.model_dump(), f, indent=2, ensure_ascii=False)

        return extraction, output_file
