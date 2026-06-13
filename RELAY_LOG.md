# Relay log <!-- merge=union; append-only — never edit or reorder past entries -->

## 2026-06-12 21:47 — reviewer (claude-fable-5)

Handoff: first CLAUDE.md + ARCHITECTURE.md incl. zkm-pdf routing-contract asymmetry — text PDFs currently double-ingested (pdfs/ + scans/). Repaired collection-broken suite (SB5 root-shim imports, pre-M2 SCAN_* keys) to 15 green. ROADMAP 7 ROUTINE (text-layer skip per contract, skip-ledger vs re-OCR every run, missing-language-pack error, DPI config, OCR confidence observe-only, HEIC, tz-naive EXIF dates FAIL core validate_frontmatter) + 1 HARD (unify scanned-only threshold across core/pdf/scan). 11 red specs + 2 guards; @manual Gherkin; 6 REVIEW_ME. NOTE: tesseract MISSING on this machine (poppler present) — integration tier skips cleanly; install tesseract + deu/eng before real OCR.

## 2026-06-12 23:56 — reviewer (Fable 5)

uv.lock refresh (parent zkm 0.14.0) — unblocks relay dispatch

## 2026-06-13 — executor (Sonnet)

Worked id:6913, id:8810, id:c199, id:5d7d, id:f7d3, id:aae8 — all 6 ROUTINE items implemented in a single session: text-layer PDF skip + pdf-producer sidecar skip (6913), below-threshold OCR skip ledger (8810), configurable DPI with default 300 (c199), OCR confidence in frontmatter (5d7d), HEIC/HEIF via optional pillow-heif extra (f7d3), tz-aware EXIF dates + pages field for PDFs (aae8). pypdf added to core deps; pillow-heif in optional [heic] extra; dpi/pdf_text_threshold added to both plugin.yaml copies. Full suite: 29 passed, 1 skipped (pillow-heif importorskip), 1 EXPECTED-RED (5c02).
BLOCKED: 5c02 Pre-existing test test_scan_lang_passed_to_pytesseract (test_convert.py:209) calls convert(store, cfg(src, lang="fra+deu")) without mocking pytesseract.get_languages(); fra is not installed on this machine. Implementing the language-pack pre-check raises ValueError before OCR, breaking that test. The test must be updated to mock GET_LANGS before 5c02 can land.
Friction: none — all other items sized correctly for one session; 6913 and 8810 share the skip-ledger writer as intended.
