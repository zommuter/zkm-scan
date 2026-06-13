# Human review queue <!-- budget: 15 min -->

Judgment calls encoded in red tests — confirm or correct the interpretation.
Max ~10 open boxes; the reviewer prunes resolved ones each review turn.

- [ ] tests/test_roadmap.py::test_6913_text_layer_pdf_skipped_and_logged (roadmap:6913) —
  Text-layer PDFs are skipped (logged, no md) even when zkm-pdf is NOT installed;
  OCR-as-fallback was rejected (worse text would mask the missing plugin). Probe
  threshold is a NEW scan-side key `pdf_text_threshold` (default 100, mirroring
  zkm-pdf) rather than reusing scan's `min_text_chars` (=10, different meaning).
- [ ] tests/test_roadmap.py::test_8810_below_threshold_not_reocred (roadmap:8810) —
  Skip-ledger is honored only while the recorded threshold equals the current
  `min_text_chars`; changing the threshold re-OCRs previously skipped files
  (append-only ledger, last entry per sha wins).
  → owner 2026-06-13 CONFIRMED: threshold-keyed skip-ledger is correct (matches
  zkm-pdf 2abf); re-OCR on threshold change is intended.
- [ ] tests/test_roadmap.py::test_c199_default_dpi_300 (roadmap:c199) —
  Default PDF rasterization DPI changes from pdf2image's implicit 200 to 300
  (slower per page, better OCR). Affects only newly processed docs — sha dedup
  prevents re-emission of existing ones.
- [ ] tests/test_roadmap.py::test_5d7d_ocr_confidence_in_frontmatter (roadmap:5d7d) —
  `ocr_confidence` = mean of word-level confidences ≥ 0, rounded to 1 decimal,
  observe-only (never skips/flags) per the observe-before-preventing heuristic.
  → RESOLVED 2026-06-13 (frontmatter-schema mtg, zkm id:cfd1): observe-only
  behaviour CONFIRMED. Field name is plugin-private (single OCR producer) ⇒
  NAMESPACE it: `scan_ocr_confidence:` per the flat `<plugin>_<key>` rule. (Stays
  bare-`ocr_confidence` only if a second OCR consumer is named at implementation.)
- [ ] tests/test_roadmap.py::test_f7d3_heic_without_pillow_heif_logs_notice (roadmap:f7d3) —
  Missing pillow-heif demotes .heic files to a skip-log notice
  (reason "heic-unsupported") instead of an error or silent invisibility;
  the dep stays an optional `heic` extra.
- [ ] tests/test_roadmap.py::test_aae8_exif_date_is_tz_aware_and_conformant (roadmap:aae8) —
  EXIF `DateTimeOriginal` is timezone-naive by spec; the test mandates attaching
  the LOCAL timezone (camera assumed to share the machine's TZ). Alternative
  (store as UTC) would misdate most scans by the local offset.
  → owner 2026-06-13 CONFIRMED with SAFEGUARD: local-TZ default is accepted, but
  the implementation MUST resolve the offset from a named IANA zone
  (zoneinfo.ZoneInfo(localzone)) applied to the photo's own date — NOT a fixed
  "current" UTC offset — so a summer photo gets the summer offset and a winter
  photo the winter offset (no DST mix-ups). Add a test that a Jan and a Jul
  naive EXIF date on a DST zone (e.g. Europe/Zurich) get +01:00 and +02:00
  respectively. (Same safeguard applies to zkm-photo 33e5.)
