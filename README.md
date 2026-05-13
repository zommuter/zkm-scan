# zkm-scan

[zkm](https://github.com/zommuter/zkm) plugin that OCR-extracts text from scanned-only PDFs and images and imports the result into the knowledge store.

## What it does

- Picks up scanned images and PDFs from `inbox/` (e.g. PDF attachments deposited by `zkm-eml` that `zkm-pdf` skipped due to no text layer)
- Optionally walks an external `SCAN_SOURCE_DIR` for direct import
- Uses `tesseract` for OCR (via `pytesseract`) and `poppler` for PDF-to-image conversion
- Writes `scans/YYYY/MM/<date>_<slug>.md` per document with OCR text in the body
- SHA-256 dedup: re-running produces no new files for already-processed content
- Skips documents whose OCR output is below `SCAN_MIN_TEXT_CHARS`

## System requirements

- `tesseract-ocr` + language packs (e.g. `tesseract-ocr-deu` for German)
- `poppler-utils` (for PDF input via `pdf2image`)

## Install

Clone this repo inside your zkm `plugins/` directory:

```bash
git clone https://github.com/zommuter/zkm-scan.git plugins/zkm-scan
```

## Configuration (in `<store>/.env`)

| Variable | Default | Description |
|---|---|---|
| `SCAN_SOURCE_DIR` | *(empty)* | Optional external directory to scan recursively |
| `SCAN_LANG` | `deu+eng` | Tesseract language code(s), e.g. `deu+eng` or `eng` |
| `SCAN_MIN_TEXT_CHARS` | `10` | Min OCR chars to emit md; below this → silently skip |

## Run

```bash
zkm convert scan
```

## Development

```bash
cd plugins/zkm-scan
uv sync --extra dev
uv run pytest
```

## License

MIT — see [LICENSE](LICENSE)
