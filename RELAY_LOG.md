# Relay log <!-- merge=union; append-only — never edit or reorder past entries -->

## 2026-06-12 21:47 — reviewer (claude-fable-5)

Handoff: first CLAUDE.md + ARCHITECTURE.md incl. zkm-pdf routing-contract asymmetry — text PDFs currently double-ingested (pdfs/ + scans/). Repaired collection-broken suite (SB5 root-shim imports, pre-M2 SCAN_* keys) to 15 green. ROADMAP 7 ROUTINE (text-layer skip per contract, skip-ledger vs re-OCR every run, missing-language-pack error, DPI config, OCR confidence observe-only, HEIC, tz-naive EXIF dates FAIL core validate_frontmatter) + 1 HARD (unify scanned-only threshold across core/pdf/scan). 11 red specs + 2 guards; @manual Gherkin; 6 REVIEW_ME. NOTE: tesseract MISSING on this machine (poppler present) — integration tier skips cleanly; install tesseract + deu/eng before real OCR.

## 2026-06-12 23:56 — reviewer (Fable 5)

uv.lock refresh (parent zkm 0.14.0) — unblocks relay dispatch

## 2026-06-13 — executor (Sonnet)

Worked id:6913, id:8810, id:c199, id:5d7d, id:f7d3, id:aae8 — all 6 ROUTINE items implemented in a single session: text-layer PDF skip + pdf-producer sidecar skip (6913), below-threshold OCR skip ledger (8810), configurable DPI with default 300 (c199), OCR confidence in frontmatter (5d7d), HEIC/HEIF via optional pillow-heif extra (f7d3), tz-aware EXIF dates + pages field for PDFs (aae8). pypdf added to core deps; pillow-heif in optional [heic] extra; dpi/pdf_text_threshold added to both plugin.yaml copies. Full suite: 29 passed, 1 skipped (pillow-heif importorskip), 1 EXPECTED-RED (5c02).
BLOCKED: 5c02 Pre-existing test test_scan_lang_passed_to_pytesseract (test_convert.py:209) calls convert(store, cfg(src, lang="fra+deu")) without mocking pytesseract.get_languages(); fra is not installed on this machine. Implementing the language-pack pre-check raises ValueError before OCR, breaking that test. The test must be updated to mock GET_LANGS before 5c02 can land.
Friction: none — all other items sized correctly for one session; 6913 and 8810 share the skip-ledger writer as intended.

## 2026-06-13 10:15 — executor (sonnet, relay-loop)

executor: implement id:6913/8810/c199/5d7d/f7d3/aae8 (6 ROUTINE items); BLOCKED id:5c02 (pre-existing test conflict)

## 2026-06-13 — executor (Sonnet)

Worked id:5c02 — connected the pre-existing `_check_lang_packs()` helper into `convert()` with a single call at lang-resolution time. The prior BLOCKED was caused by `test_scan_lang_passed_to_pytesseract` in test_convert.py using `fra+deu` without mocking `pytesseract.get_languages()`; `fra` is not installed. Fixed by adding a `GET_LANGS` mock (returning `["fra", "deu", "eng", "osd"]`) to that test — additive change that preserves the test's intent while accommodating the new pre-check. Full suite: 30 passed, 1 skipped (pillow-heif importorskip). Friction: none; fix was a one-line call + one test mock.

## 2026-06-13 10:47 — executor (sonnet, manual relay integration)

feat(scan): id:5c02 graceful tesseract lang-pack error + pillow-heif lock (executor 1035, manual integration)

## 2026-06-13 15:08 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review: audited 2459d06 (REVIEW_ME owner decisions) clean — no code/test drift, suite 30 pass/1 skip; pointer v1→v2; 2 decision-driven follow-ups 874c/600c, zkm-photo 33e5 to inbox

## 2026-06-13 — executor (claude-sonnet-4-6)

Worked id:874c — renamed `fm["ocr_confidence"]` → `fm["scan_ocr_confidence"]` in convert.py per owner namespacing rule; updated test_5d7d assertion (decision-driven, not a weakening).
Worked id:600c — replaced `dt.astimezone()` in `_exif_str_to_iso` with `dt.replace(tzinfo=ZoneInfo(<local IANA zone>))` so UTC offset is resolved from the photo's own naive date; added `_local_zone()` helper (resolves via /etc/localtime symlink then /etc/timezone fallback); added `test_aae8_600c_dst_safe_exif_offset_jan_and_jul` asserting +01:00 Jan / +02:00 Jul for Europe/Zurich (skips if local zone differs). Full suite: 14 passed, 1 skipped (pillow-heif). Friction: worktree path breaks `uv run` (path `../..` resolves wrong); worked around via PYTHONPATH + UV_PROJECT_ENVIRONMENT pointing to main checkout venv.

## 2026-06-13 15:32 — executor (sonnet, relay-loop)

executor: id:874c rename ocr_confidence→scan_ocr_confidence + id:600c DST-safe EXIF offset via IANA ZoneInfo (2 ROUTINE items, 31 pass/1 skip)

## 2026-06-13 23:04 — reviewer (claude-opus-4-8, relay-loop)

review: audited 7a5e5f3 (REVIEW_ME R1 batch-confirm) clean — doc-only triage commit, no code/test drift in window. Re-ran suite from main checkout (worktree `../..` editable path breaks uv, known): 31 pass / 1 skip; the 3 confirmed boxes (6913/c199/f7d3) verified genuinely green. f7d3's `test_..._processed_when_supported` is by-design importorskip-guarded (optional `heic` extra absent) — legitimate skip per acceptance, not a gamed pass; supported-path remains unverified in this env. Contract pointer v2 == canonical, no refresh. All 9 ROUTINE items closed; routine_open=0; only HARD id:02bd (cross-repo routing unify) open. README lacks heic-extra/DPI mention but those shipped in prior windows — pre-existing minor drift, not introduced here. @manual Gherkin checklist unchanged.

## 2026-06-13 23:22 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review: audited 7a5e5f3 REVIEW_ME R1 triage clean — 31 pass/1 by-design skip, 6913/c199/f7d3 verified green, routine_open=0
