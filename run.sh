#!/bin/bash
set -e

echo "=== Document Data Extractor Agent ==="
echo "Pulling required Ollama models (if missing)..."
ollama pull glm-ocr 2>/dev/null || true
ollama pull qwen2.5:3b-instruct 2>/dev/null || true

echo "Installing Python dependencies..."
pip install -r requirements.txt --quiet

echo "Running end-to-end extraction on all sample documents..."
python main.py extract-all

echo ""
echo "Extraction completed successfully!"
echo "• See 'output/' for generated JSON files with embedded validation reports."
echo "• See 'docs/validation_and_failures.md' for validation logic and failure case notes."
