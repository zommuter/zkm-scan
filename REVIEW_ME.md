# Human review queue <!-- budget: 15 min -->

Judgment calls encoded in red tests — confirm or correct the interpretation.
Max ~10 open boxes; the reviewer prunes resolved ones each review turn.

- [ ] tests/test_roadmap.py::test_6913_text_layer_pdf_skipped_and_logged (roadmap:6913) —
  Text-layer PDFs are skipped (logged, no md) even when zkm-pdf is NOT installed;
  OCR-as-fallback was rejected (worse text would mask the missing plugin). Probe
  threshold is a NEW scan-side key `pdf_text_threshold` (default 100, mirroring
  zkm-pdf) rather than reusing scan's `min_text_chars` (=10, different meaning).
- [ ] tests/test_roadmap.py::test_c199_default_dpi_300 (roadmap:c199) —
  Default PDF rasterization DPI changes from pdf2image's implicit 200 to 300
  (slower per page, better OCR). Affects only newly processed docs — sha dedup
  prevents re-emission of existing ones.
- [ ] tests/test_roadmap.py::test_f7d3_heic_without_pillow_heif_logs_notice (roadmap:f7d3) —
  Missing pillow-heif demotes .heic files to a skip-log notice
  (reason "heic-unsupported") instead of an error or silent invisibility;
  the dep stays an optional `heic` extra.
