@echo off
echo ==============================================
echo   Document Data Extractor Agent Runner
echo ==============================================

echo Checking / pulling Ollama models...
ollama pull glm-ocr:q8_0
ollama pull qwen2.5:3b

echo Installing dependencies...
pip install -r requirements.txt --quiet

echo Running extraction on all sample documents...
python main.py extract-all

echo.
echo ==============================================
echo Extraction Complete!
echo Outputs saved to: output\
echo Documentation: docs\validation_and_failures.md
echo ==============================================
pause
