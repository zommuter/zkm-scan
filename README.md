# zkm-scan

[zkm](https://github.com/zommuter/zkm) plugin that OCR-extracts text from scanned-only PDFs and images and imports the result into the knowledge store.

## What it does

- Picks up scanned images and PDFs from `inbox/` (e.g. PDF attachments deposited by `zkm-eml` that `zkm-pdf` skipped due to no text layer)
- Optionally walks an external `source_dir` for direct import
- Uses `tesseract` for OCR (via `pytesseract`) and `poppler` for PDF-to-image conversion
- Writes `scans/YYYY/MM/<date>_<slug>.md` per document with OCR text in the body
- SHA-256 dedup: re-running produces no new files for already-processed content
- Honors the zkm-pdf routing contract: a PDF with a real text layer (≥ `pdf_text_threshold` chars) or an existing `pdf`-producer sidecar is left for zkm-pdf, not OCR'd (logged to `.zkm-state/zkm-scan-skipped.jsonl`); see [ARCHITECTURE.md](ARCHITECTURE.md) §Routing contract
- Skips documents whose OCR output is below `min_text_chars`, and records them in the skip-ledger so they are not re-OCR'd every run (unless the threshold changes)
- Optional HEIC/HEIF input when the `heic` extra (`pillow-heif`) is installed; missing → logged as a skip notice, never a silent drop
- Records `scan_ocr_confidence` (mean word-level confidence, observe-only) in frontmatter

## System requirements

- `tesseract` + language packs (default config wants `deu` and `eng`)
- `poppler` (`pdftoppm`) for PDF input via `pdf2image`
- Manjaro: `pamac install tesseract tesseract-data-deu tesseract-data-eng poppler`

A missing language pack raises a clear `ValueError` naming the pack before any OCR runs.

## Install

Clone this repo inside your zkm `plugins/` directory:

```bash
git clone https://github.com/zommuter/zkm-scan.git plugins/zkm-scan
# optional HEIC/HEIF support:
uv sync --extra heic
```

## Configuration (in the `scan:` section of `<store>/zkm-config.yaml`)

Bare snake_case keys (the pre-M2 `SCAN_*` env-var names are dead):

| Key | Default | Description |
|---|---|---|
| `source_dir` | *(empty)* | Optional external directory to scan recursively |
| `lang` | `deu+eng` | Tesseract language code(s), e.g. `deu+eng` or `eng` |
| `min_text_chars` | `10` | Min OCR chars to emit md; below this → skip (and ledger) |
| `pdf_text_threshold` | `100` | Text-layer chars at/above which a PDF is left for zkm-pdf |
| `dpi` | `300` | DPI for PDF rasterization before OCR |

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
