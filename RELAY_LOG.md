# Relay log <!-- merge=union; append-only — never edit or reorder past entries -->

## 2026-06-12 21:47 — reviewer (claude-fable-5)

Handoff: first CLAUDE.md + ARCHITECTURE.md incl. zkm-pdf routing-contract asymmetry — text PDFs currently double-ingested (pdfs/ + scans/). Repaired collection-broken suite (SB5 root-shim imports, pre-M2 SCAN_* keys) to 15 green. ROADMAP 7 ROUTINE (text-layer skip per contract, skip-ledger vs re-OCR every run, missing-language-pack error, DPI config, OCR confidence observe-only, HEIC, tz-naive EXIF dates FAIL core validate_frontmatter) + 1 HARD (unify scanned-only threshold across core/pdf/scan). 11 red specs + 2 guards; @manual Gherkin; 6 REVIEW_ME. NOTE: tesseract MISSING on this machine (poppler present) — integration tier skips cleanly; install tesseract + deu/eng before real OCR.
