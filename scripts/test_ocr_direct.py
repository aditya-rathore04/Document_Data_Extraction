import argparse
import base64
import json
import sys
from pathlib import Path
from PIL import Image
import io
import requests

def test_image_ocr(image_path: str, model: str = "glm-ocr:q8", num_ctx: int = 10240):
    path = Path(image_path)
    if not path.exists():
        print(f"Error: File '{path}' does not exist.")
        sys.exit(1)

    print(f"--- Testing {model} on {path.name} ---")
    print(f"Server: http://localhost:11434 | Context Window: {num_ctx}")
    print("Reading and encoding image...")

    # Load and scale if large
    img = Image.open(path).convert("RGB")
    if max(img.size) > 1024:
        img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    payload = {
        "model": model,
        "prompt": "Extract all text, prices, and tables from this receipt image as clean Markdown.",
        "images": [img_b64],
        "stream": True,
        "options": {
            "num_ctx": num_ctx,
            "temperature": 0.0,
        }
    }

    print("Sending request to Ollama (streaming output below)...\n" + "="*50)
    try:
        response = requests.post("http://localhost:11434/api/generate", json=payload, stream=True, timeout=180)
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                chunk = json.loads(line.decode("utf-8"))
                token = chunk.get("response", "")
                print(token, end="", flush=True)
                if chunk.get("done", False):
                    break
        print("\n" + "="*50 + "\n--- OCR Test Completed Successfully! ---")
    except requests.exceptions.ConnectionError:
        print("\nError: Could not connect to Ollama. Make sure Ollama is running.")
    except Exception as e:
        print(f"\nError occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Directly test an Ollama OCR model on an image file")
    parser.add_argument("image_path", nargs="?", default="sample_documents/receipt.jpg", help="Path to image file")
    parser.add_argument("--model", default="glm-ocr:q8", help="Ollama model tag to test")
    parser.add_argument("--ctx", type=int, default=10240, help="num_ctx size")
    args = parser.parse_args()
    test_image_ocr(args.image_path, args.model, args.ctx)
