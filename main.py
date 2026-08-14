import argparse
import sys
import time
import warnings
from pathlib import Path
import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from src.agent import DocumentExtractorAgent
from src.schemas import DocumentExtraction

# Suppress third-party library warnings for a clean CLI experience
warnings.filterwarnings("ignore")

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console()

SUPPORTED_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff",
    ".xlsx", ".xls", ".xlsm", ".txt", ".csv", ".tsv", ".md", ".json"
}


def print_full_banner():
    """Prints a clean, auto-sizing branding panel for help / startup."""
    banner_content = (
        "[bold cyan][AGENT] DOCUMENT DATA EXTRACTOR[/bold cyan]\n"
        "[dim]Local, privacy-first Perceive -> OCR -> Structure -> Validate pipeline[/dim]\n\n"
        "  [cyan]*[/cyan] [bold white]Perception:[/bold white]  GLM-OCR (glm-ocr:q8_0) + Vector PyMuPDF\n"
        "  [cyan]*[/cyan] [bold white]Structuring:[/bold white] Qwen 2.5 (qwen2.5:3b) + Pydantic v2 Schema\n"
        "  [cyan]*[/cyan] [bold white]Validation:[/bold white]  Deterministic Financial & Date Integrity Engine\n"
        "  [cyan]*[/cyan] [bold white]Runtime:[/bold white]     100% Local Inference via Ollama (Zero Cloud API Costs)"
    )
    console.print(Panel(banner_content, border_style="cyan", padding=(1, 2), expand=False))


def check_environment(
    ollama_url: str = "http://localhost:11434",
    ocr_model: str = "glm-ocr:q8_0",
    structure_model: str = "qwen2.5:3b",
    silent: bool = True,
) -> bool:
    """
    Verifies that Ollama is reachable and required models are installed.
    Stops immediately with an actionable 1-line command on failure.
    """
    try:
        resp = requests.get(f"{ollama_url.rstrip('/')}/api/tags", timeout=5)
        resp.raise_for_status()
    except Exception:
        console.print(
            f"[bold red]Error:[/bold red] Ollama is not running at {ollama_url}. "
            "Please start Ollama (`ollama serve` or desktop app) and retry."
        )
        return False

    models = [m.get("name", "") for m in resp.json().get("models", [])]
    ocr_present = any(ocr_model in m for m in models)
    struct_present = any(structure_model in m for m in models)

    if not silent:
        table = Table(title="[STATUS] Ollama Model Readiness", show_header=True, header_style="bold green")
        table.add_column("Required Role", style="cyan")
        table.add_column("Target Model", style="white")
        table.add_column("Status", style="bold")
        table.add_row(
            "Perception (OCR)",
            ocr_model,
            "[green]Ready[/green]" if ocr_present else f"[red]Missing (run: ollama pull {ocr_model})[/red]",
        )
        table.add_row(
            "Structuring (JSON)",
            structure_model,
            "[green]Ready[/green]" if struct_present else f"[red]Missing (run: ollama pull {structure_model})[/red]",
        )
        console.print(table)

    if not ocr_present:
        console.print(
            f"[bold red]Error:[/bold red] OCR model '{ocr_model}' not found in Ollama. "
            f"Run: [cyan]ollama pull {ocr_model}[/cyan]"
        )
        return False

    if not struct_present:
        console.print(
            f"[bold red]Error:[/bold red] Structuring model '{structure_model}' not found in Ollama. "
            f"Run: [cyan]ollama pull {structure_model}[/cyan]"
        )
        return False

    return True


def display_detailed_document(doc: DocumentExtraction, output_path: Path):
    """Renders the detailed document fields table, line items table, and validation panel."""
    # 1. Main Document Info Table
    info_table = Table(
        title="[DOC] Extracted Document Information",
        show_header=True,
        header_style="bold magenta",
    )
    info_table.add_column("Field", style="cyan", width=20)
    info_table.add_column("Extracted Value", style="white")

    info_table.add_row("Document Type", doc.document_type.upper())
    info_table.add_row("Document ID", doc.document_id or "[italic dim]None[/italic dim]")
    info_table.add_row("Vendor Name", doc.vendor_name or "[italic dim]None[/italic dim]")
    info_table.add_row("Vendor Address", doc.vendor_address or "[italic dim]None[/italic dim]")
    info_table.add_row("Customer Name", doc.customer_name or "[italic dim]None[/italic dim]")
    info_table.add_row("Date", doc.date or "[italic dim]None[/italic dim]")
    info_table.add_row("Due Date", doc.due_date or "[italic dim]None[/italic dim]")
    info_table.add_row("Currency", doc.currency or "[italic dim]None[/italic dim]")
    info_table.add_row(
        "Subtotal",
        f"{doc.subtotal:.2f}" if doc.subtotal is not None else "[italic dim]None[/italic dim]",
    )
    info_table.add_row(
        "Tax",
        f"{doc.tax:.2f}" if doc.tax is not None else "[italic dim]None[/italic dim]",
    )
    info_table.add_row(
        "Shipping",
        f"{doc.shipping:.2f}" if doc.shipping is not None else "[italic dim]None[/italic dim]",
    )
    info_table.add_row(
        "Discount",
        f"{doc.discount:.2f}" if doc.discount is not None else "[italic dim]None[/italic dim]",
    )
    info_table.add_row(
        "Grand Total",
        f"[bold green]{doc.total:.2f}[/bold green]" if doc.total is not None else "[bold red]None[/bold red]",
    )
    info_table.add_row("Saved JSON", f"[green]{output_path}[/green]")

    console.print(info_table)

    # 2. Line Items Table
    if doc.line_items:
        items_table = Table(
            title="[ITEMS] Extracted Line Items",
            show_header=True,
            header_style="bold blue",
        )
        items_table.add_column("#", justify="right", width=4)
        items_table.add_column("Description", style="white")
        items_table.add_column("Qty", justify="right", style="cyan")
        items_table.add_column("Unit Price", justify="right", style="cyan")
        items_table.add_column("Total", justify="right", style="bold green")

        for idx, item in enumerate(doc.line_items, start=1):
            qty_str = f"{item.quantity}" if item.quantity is not None else "-"
            price_str = f"{item.unit_price:.2f}" if item.unit_price is not None else "-"
            items_table.add_row(
                str(idx), item.description, qty_str, price_str, f"{item.total:.2f}"
            )

        console.print(items_table)

    # 3. Validation Status Panel
    if doc.validation:
        val = doc.validation
        if val.is_valid:
            status_panel = Panel(
                "[bold green][PASS] ALL SANITY CHECKS PASSED[/bold green]\n"
                "* Line items math verified\n"
                "* Subtotal & total consistency verified\n"
                "* Date logic verified",
                title="[VALIDATION] Status",
                border_style="green",
                expand=False,
            )
            console.print(status_panel)
        else:
            issues_text = "\n".join(
                f"[bold red]* [{issue.severity.upper()}] {issue.field}:[/bold red] {issue.message}"
                for issue in val.issues
            )
            status_panel = Panel(
                f"[bold red][FAIL] VALIDATION ISSUES DETECTED[/bold red]\n\n{issues_text}",
                title="[VALIDATION] Status",
                border_style="red",
                expand=False,
            )
            console.print(status_panel)


def render_summary_table(results: list[dict]):
    """Renders the executive summary table across all processed documents."""
    if not results:
        return

    table = Table(
        title="\n[SUMMARY] Document Extraction & Validation Overview",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Filename", style="cyan", no_wrap=True)
    table.add_column("Type", style="white")
    table.add_column("Vendor", style="white")
    table.add_column("Total", justify="right", style="green")
    table.add_column("Status", justify="center", style="bold")
    table.add_column("Issues", justify="right", style="yellow")
    table.add_column("Duration", justify="right", style="cyan")
    table.add_column("Saved Output", style="dim")

    for r in results:
        doc: DocumentExtraction = r["doc"]
        timings = r.get("timings", {})
        is_valid = doc.validation.is_valid if doc.validation else False
        issue_count = len(doc.validation.issues) if doc.validation else 0

        status_str = "[green][PASS][/green]" if is_valid else "[red][ISSUES][/red]"
        total_str = f"{doc.total:.2f}" if doc.total is not None else "-"
        if doc.currency and doc.total is not None:
            total_str = f"{doc.currency} {total_str}"

        dur_str = f"{timings.get('total', 0):.1f}s" if timings else "-"

        table.add_row(
            r["filename"],
            doc.document_type.upper(),
            doc.vendor_name or "-",
            total_str,
            status_str,
            str(issue_count) if issue_count > 0 else "[dim]0[/dim]",
            dur_str,
            str(r["output_path"]),
        )

    console.print(table)


def process_single_file(
    agent: DocumentExtractorAgent,
    file_path: Path,
    output_dir: str = "output",
) -> dict:
    """Processes a single document file with a live multi-stage checklist and displays detailed tables."""
    if not file_path.exists():
        console.print(f"[bold red]Skipping:[/bold red] File not found: {file_path}")
        return None

    if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        console.print(
            f"[bold yellow]Skipping:[/bold yellow] Unsupported format '{file_path.suffix}' for {file_path.name}"
        )
        return None

    file_start = time.time()
    with console.status(
        f"[bold cyan]Starting pipeline for {file_path.name}...",
        spinner="dots",
    ) as status:
        def on_progress(stage: str, event: str, msg: str, elapsed: float):
            if event == "start":
                status.update(f"[bold cyan]{msg} [dim]({int(time.time() - file_start)}s)[/dim]")
            elif event == "done":
                # Print a clean, permanent checklist line for the completed stage
                console.print(f"  [bold green][PASS][/bold green] {msg} [dim]({elapsed:.2f}s)[/dim]")

        extraction, out_file, timings = agent.process_and_save(
            file_path, output_dir=output_dir, progress_callback=on_progress
        )

    # Print clean timing summary line
    timing_summary = (
        f"\n[bold green][DONE][/bold green] {file_path.name} processed in {timings['total']:.1f}s "
        f"[dim](Load: {timings['load']:.2f}s | OCR: {timings['ocr']:.1f}s | "
        f"Structure: {timings['structure']:.1f}s | Validate: {timings['validate']:.2f}s)[/dim]"
    )
    console.print(timing_summary)
    display_detailed_document(extraction, out_file)

    return {
        "filename": file_path.name,
        "doc": extraction,
        "output_path": out_file,
        "timings": timings,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Document Data Extractor -- Perceive -> OCR -> Structure -> Validate",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: extract <path>
    extract_parser = subparsers.add_parser(
        "extract", help="Extract and validate data from a single document file"
    )
    extract_parser.add_argument("file_path", type=str, help="Path to PDF, image, Excel, or text document")
    extract_parser.add_argument("--output-dir", default="output", help="Directory to save JSON output (default: output)")

    # Command: extract-all
    extract_all_parser = subparsers.add_parser(
        "extract-all", help="Process all documents in sample_documents/"
    )
    extract_all_parser.add_argument("--samples-dir", default="sample_documents", help="Folder with sample documents")
    extract_all_parser.add_argument("--output-dir", default="output", help="Directory to save JSON output (default: output)")

    # Command: check-connection
    subparsers.add_parser(
        "check-connection", help="Verify Ollama connection and model readiness"
    )

    args = parser.parse_args()

    if not args.command:
        print_full_banner()
        parser.print_help()
        sys.exit(0)

    try:
        if args.command == "check-connection":
            print_full_banner()
            ok = check_environment(silent=False)
            sys.exit(0 if ok else 1)

        # Automatic pre-flight environment check before any processing
        if not check_environment(silent=True):
            sys.exit(1)

        agent = DocumentExtractorAgent(
            ocr_model="glm-ocr:q8_0",
            structure_model="qwen2.5:3b",
        )

        results = []

        if args.command == "extract":
            file_path = Path(args.file_path)
            console.print(f"[bold cyan][AGENT][/bold cyan] Processing document: [bold]{file_path.name}[/bold]\n")
            res = process_single_file(agent, file_path, output_dir=args.output_dir)
            if res:
                results.append(res)
            render_summary_table(results)

        elif args.command == "extract-all":
            samples_dir = Path(args.samples_dir)
            if not samples_dir.exists():
                console.print(f"[bold red]Error:[/bold red] Sample directory '{samples_dir}' not found.")
                sys.exit(1)

            files = sorted(
                [f for f in samples_dir.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS]
            )

            if not files:
                console.print(f"[yellow]No supported documents found in '{samples_dir}'.[/yellow]")
                sys.exit(0)

            console.print(f"[bold cyan][AGENT][/bold cyan] Batch processing [bold]{len(files)}[/bold] documents from '{samples_dir}'...\n")

            for file_path in files:
                console.rule(f"[bold]Processing {file_path.name}[/bold]")
                res = process_single_file(agent, file_path, output_dir=args.output_dir)
                if res:
                    results.append(res)

            console.rule("[bold magenta]Batch Processing Completed[/bold magenta]")
            render_summary_table(results)

    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user. Exiting cleanly.[/yellow]")
        sys.exit(130)


if __name__ == "__main__":
    main()
