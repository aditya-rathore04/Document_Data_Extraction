import argparse
import sys
import warnings
from pathlib import Path
import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from src.agent import DocumentExtractorAgent
from src.schemas import DocumentExtraction

# Suppress third-party PyTorch and deprecation library warnings
warnings.filterwarnings("ignore")

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console()


def display_extraction_result(doc: DocumentExtraction, output_path: Path):
    """Renders a formatted rich terminal summary of the extraction and validation."""
    # Main Document Information Table
    info_table = Table(title="[DOC] Extracted Document Information", show_header=True, header_style="bold magenta")
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
    info_table.add_row("Subtotal", f"{doc.subtotal:.2f}" if doc.subtotal is not None else "[italic dim]None[/italic dim]")
    info_table.add_row("Tax", f"{doc.tax:.2f}" if doc.tax is not None else "[italic dim]None[/italic dim]")
    info_table.add_row("Shipping", f"{doc.shipping:.2f}" if doc.shipping is not None else "[italic dim]None[/italic dim]")
    info_table.add_row("Discount", f"{doc.discount:.2f}" if doc.discount is not None else "[italic dim]None[/italic dim]")
    info_table.add_row("Grand Total", f"[bold green]{doc.total:.2f}[/bold green]" if doc.total is not None else "[bold red]None[/bold red]")
    info_table.add_row("Saved JSON", f"[green]{output_path}[/green]")

    console.print(info_table)

    # Line Items Table
    if doc.line_items:
        items_table = Table(title="[ITEMS] Extracted Line Items", show_header=True, header_style="bold blue")
        items_table.add_column("#", justify="right", width=4)
        items_table.add_column("Description", style="white")
        items_table.add_column("Qty", justify="right", style="cyan")
        items_table.add_column("Unit Price", justify="right", style="cyan")
        items_table.add_column("Total", justify="right", style="bold green")

        for idx, item in enumerate(doc.line_items, start=1):
            qty_str = f"{item.quantity}" if item.quantity is not None else "-"
            price_str = f"{item.unit_price:.2f}" if item.unit_price is not None else "-"
            items_table.add_row(str(idx), item.description, qty_str, price_str, f"{item.total:.2f}")

        console.print(items_table)

    # Validation Results
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
            )
            console.print(status_panel)


def check_connection(ollama_url: str, ocr_model: str, structure_model: str):
    """Checks connection to Ollama server and lists installed models."""
    console.print(f"[bold]Connecting to Ollama at [cyan]{ollama_url}[/cyan]...[/bold]")
    try:
        resp = requests.get(f"{ollama_url.rstrip('/')}/api/tags", timeout=5)
        resp.raise_for_status()
        models = [m.get("name") for m in resp.json().get("models", [])]

        table = Table(title="[STATUS] Ollama Model Status", show_header=True, header_style="bold green")
        table.add_column("Required Role", style="cyan")
        table.add_column("Target Model", style="white")
        table.add_column("Status", style="bold")

        ocr_found = any(ocr_model in m for m in models)
        struct_found = any(structure_model in m for m in models)

        table.add_row(
            "Perception (OCR)",
            ocr_model,
            "[green]Installed[/green]" if ocr_found else f"[red]Missing (run: ollama pull {ocr_model})[/red]",
        )
        table.add_row(
            "Structuring (JSON)",
            structure_model,
            "[green]Installed[/green]" if struct_found else f"[red]Missing (run: ollama pull {structure_model})[/red]",
        )

        console.print(table)
        return ocr_found and struct_found

    except Exception as e:
        console.print(f"[bold red]Failed to connect to Ollama:[/bold red] {e}")
        console.print("[yellow]Make sure Ollama is installed and running (`ollama serve` or desktop app).[/yellow]")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Document Data Extractor Agent -- Perceive -> OCR -> Structure -> Validate"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: extract
    extract_parser = subparsers.add_parser("extract", help="Extract and validate data from a single document")
    extract_parser.add_argument("file_path", type=str, help="Path to PDF, image, or text document")
    extract_parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama server URL")
    extract_parser.add_argument("--ocr-model", default="glm-ocr:q8_0", help="OCR model tag")
    extract_parser.add_argument("--structure-model", default="qwen2.5:3b", help="Structuring model tag")
    extract_parser.add_argument("--output-dir", default="output", help="Directory to save JSON output")

    # Command: extract-all
    extract_all_parser = subparsers.add_parser(
        "extract-all", help="Process all sample documents in sample_documents/"
    )
    extract_all_parser.add_argument("--samples-dir", default="sample_documents", help="Samples folder path")
    extract_all_parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama server URL")
    extract_all_parser.add_argument("--ocr-model", default="glm-ocr:q8_0", help="OCR model tag")
    extract_all_parser.add_argument("--structure-model", default="qwen2.5:3b", help="Structuring model tag")
    extract_all_parser.add_argument("--output-dir", default="output", help="Directory to save JSON output")

    # Command: check-connection
    conn_parser = subparsers.add_parser("check-connection", help="Verify Ollama connection and model readiness")
    conn_parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama server URL")
    conn_parser.add_argument("--ocr-model", default="glm-ocr:q8_0", help="OCR model tag")
    conn_parser.add_argument("--structure-model", default="qwen2.5:3b", help="Structuring model tag")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "check-connection":
        check_connection(args.ollama_url, args.ocr_model, args.structure_model)

    elif args.command == "extract":
        file_path = Path(args.file_path)
        if not file_path.exists():
            console.print(f"[bold red]File not found:[/bold red] {file_path}")
            sys.exit(1)

        console.print(f"[bold]Starting extraction on:[/bold] [cyan]{file_path}[/cyan]")
        agent = DocumentExtractorAgent(
            ollama_url=args.ollama_url,
            ocr_model=args.ocr_model,
            structure_model=args.structure_model,
        )

        import time
        start_time = time.time()
        with console.status(
            f"[bold cyan][Stage 1/4] Loading document {file_path.name}...",
            spinner="dots",
        ) as status:
            def on_progress(stage: str, msg: str):
                elapsed_sec = int(time.time() - start_time)
                status.update(f"[bold cyan]{msg} [dim]({elapsed_sec}s elapsed)[/dim]")

            extraction, out_file = agent.process_and_save(
                file_path, output_dir=args.output_dir, progress_callback=on_progress
            )

        elapsed = time.time() - start_time
        console.print(f"[dim green][DONE] Pipeline completed in {elapsed:.1f}s[/dim green]")
        display_extraction_result(extraction, out_file)

    elif args.command == "extract-all":
        samples_dir = Path(args.samples_dir)
        if not samples_dir.exists():
            console.print(f"[bold red]Sample directory not found:[/bold red] {samples_dir}")
            sys.exit(1)

        files = sorted(
            [
                f
                for f in samples_dir.iterdir()
                if f.suffix.lower()
                in [
                    ".pdf",
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".webp",
                    ".bmp",
                    ".tiff",
                    ".txt",
                    ".csv",
                    ".tsv",
                    ".md",
                    ".xlsx",
                    ".xls",
                ]
            ]
        )

        if not files:
            console.print(f"[bold yellow]No document files found in {samples_dir}[/bold yellow]")
            sys.exit(0)

        console.print(f"[bold cyan]Found {len(files)} sample documents to process.[/bold cyan]\n")
        agent = DocumentExtractorAgent(
            ollama_url=args.ollama_url,
            ocr_model=args.ocr_model,
            structure_model=args.structure_model,
        )

        import time
        for file_path in files:
            console.rule(f"[bold]Processing {file_path.name}[/bold]")
            file_start = time.time()
            try:
                with console.status(
                    f"[bold cyan][Stage 1/4] Loading {file_path.name}...",
                    spinner="dots",
                ) as status:
                    def on_progress(stage: str, msg: str):
                        elapsed_sec = int(time.time() - file_start)
                        status.update(f"[bold cyan]{msg} [dim]({elapsed_sec}s elapsed)[/dim]")

                    extraction, out_file = agent.process_and_save(
                        file_path, output_dir=args.output_dir, progress_callback=on_progress
                    )

                elapsed = time.time() - file_start
                console.print(f"[dim green][DONE] Completed in {elapsed:.1f}s[/dim green]")
                display_extraction_result(extraction, out_file)
            except Exception as e:
                console.print(f"[bold red]Failed to process {file_path.name}:[/bold red] {e}")


if __name__ == "__main__":
    main()
