from pathlib import Path 
from docling.document_converter import DocumentConverter

BASE_DIR = Path(__file__).parent.parent 

INPUT_FILE_PATH = BASE_DIR / "storage" / "documents" / "pdf" / "2312.01232v2.pdf"
OUTPUT_FILE_PATH = BASE_DIR / "storage" / "documents" / "pdf" / "paper_3.md"

converter = DocumentConverter()
result = converter.convert(INPUT_FILE_PATH)
markdown = result.document.export_to_markdown()

with open(OUTPUT_FILE_PATH, "w", encoding="utf-8") as f:
    f.write(markdown)

print("Done!")