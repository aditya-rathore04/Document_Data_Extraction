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
        progress_callback: Optional[Callable[[str, str, str, float], None]] = None,
    ) -> tuple[DocumentExtraction, dict]:
        """
        Executes end-to-end extraction and validation on a single document file.
        Notifies progress_callback(stage, event, message, elapsed) as each stage starts and finishes.
        """
        path = Path(file_path)
        timings = {}
        t_total_start = time.time()

        def report(stage: str, event: str, msg: str, elapsed: float = 0.0):
            if progress_callback:
                progress_callback(stage, event, msg, elapsed)

        # 1. PERCEIVE: Load document pages
        t0 = time.time()
        report("load", "start", f"[1/4] Loading document & inspecting text layers: {path.name}")
        loaded_doc = load_document(path)
        t_load = time.time() - t0
        timings["load"] = t_load
        report("load", "done", f"[1/4] Document loaded ({loaded_doc.page_count} page{'s' if loaded_doc.page_count != 1 else ''})", t_load)

        # 2. OCR: Convert document pages to Markdown / text
        t0 = time.time()
        if loaded_doc.is_text:
            report("ocr", "start", "[2/4] Extracting native vector text layer...")
            markdown_content = loaded_doc.text_content or ""
            t_ocr = time.time() - t0
            report("ocr", "done", "[2/4] Native text layer extracted", t_ocr)
        else:
            report("ocr", "start", f"[2/4] Running GLM-OCR perception ({self.ocr_model})...")
            page_markdowns = []
            for i, page_img in enumerate(loaded_doc.images, start=1):
                page_md = self.ocr_client.extract_markdown(page_img)
                page_markdowns.append(f"--- Page {i} ---\n{page_md}")
            markdown_content = "\n\n".join(page_markdowns)
            t_ocr = time.time() - t0
            report("ocr", "done", f"[2/4] GLM-OCR perception completed ({loaded_doc.page_count} page{'s' if loaded_doc.page_count != 1 else ''})", t_ocr)
        timings["ocr"] = t_ocr

        # 3. STRUCTURE: Parse Markdown into Pydantic schema using text LLM
        t0 = time.time()
        report("structure", "start", f"[3/4] Reasoning & structuring JSON fields ({self.structure_model})...")
        extraction = self.structure_client.structure_document(markdown_content)
        t_struct = time.time() - t0
        timings["structure"] = t_struct
        report("structure", "done", f"[3/4] JSON fields structured ({len(extraction.line_items)} line items)", t_struct)

        # 4. VALIDATE: Run rule-based business logic and sanity checks
        t0 = time.time()
        report("validate", "start", "[4/4] Executing mathematical sanity checks & date rules...")
        validation_result = validate_document(extraction)
        extraction.validation = validation_result
        t_val = time.time() - t0
        timings["validate"] = t_val
        val_status = "passed" if validation_result.is_valid else f"{len(validation_result.issues)} issue(s) detected"
        report("validate", "done", f"[4/4] Validation finished ({val_status})", t_val)

        timings["total"] = time.time() - t_total_start
        return extraction, timings

    def process_and_save(
        self,
        file_path: Union[str, Path],
        output_dir: Optional[Union[str, Path]] = None,
        progress_callback: Optional[Callable[[str, str, str, float], None]] = None,
    ) -> tuple[DocumentExtraction, Path, dict]:
        """
        Processes a document, writes resulting JSON to disk, and returns extraction, output path, and stage timings.
        """
        path = Path(file_path)
        out_dir = Path(output_dir) if output_dir else Path("output")
        out_dir.mkdir(parents=True, exist_ok=True)

        extraction, timings = self.process_file(path, progress_callback=progress_callback)

        output_file = out_dir / f"{path.stem}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(extraction.model_dump(), f, indent=2, ensure_ascii=False)

        return extraction, output_file, timings
