# Human review queue <!-- budget: 15 min -->

Judgment calls encoded in red tests — confirm or correct the interpretation.
Max ~10 open boxes; the reviewer prunes resolved ones each review turn.

- [x] tests/test_roadmap.py::test_6913_text_layer_pdf_skipped_and_logged (roadmap:6913) —
  Text-layer PDFs are skipped (logged, no md) even when zkm-pdf is NOT installed;
  OCR-as-fallback was rejected (worse text would mask the missing plugin). Probe
  threshold is a NEW scan-side key `pdf_text_threshold` (default 100, mirroring
  zkm-pdf) rather than reusing scan's `min_text_chars` (=10, different meaning).
  — confirmed by user 2026-06-13 (batch triage)
- [x] tests/test_roadmap.py::test_c199_default_dpi_300 (roadmap:c199) —
  Default PDF rasterization DPI changes from pdf2image's implicit 200 to 300
  (slower per page, better OCR). Affects only newly processed docs — sha dedup
  prevents re-emission of existing ones.
  — confirmed by user 2026-06-13 (batch triage)
- [x] tests/test_roadmap.py::test_f7d3_heic_without_pillow_heif_logs_notice (roadmap:f7d3) —
  Missing pillow-heif demotes .heic files to a skip-log notice
  (reason "heic-unsupported") instead of an error or silent invisibility;
  the dep stays an optional `heic` extra.
  — confirmed by user 2026-06-13 (batch triage)
- [x] id:02bd — the executor's 02bd close (commit 4e259e8) was tagged at its OWN
  checkpoint (relay-ckpt-20260624-1733), so the normal "review-follows-execute" window
  excluded it (boundary blind-spot). Verified GREEN this review (2026-06-26): genuine
  surgical impl (imports `zkm.pdftext.resolve_threshold`, switches `_probe_pdf_text` to
  `.strip()` semantics), test file untouched, `pytest -k 02bd` passes, gaming-scan clean.
  No human action needed — recorded for audit completeness.
- [x] ROADMAP is genuinely DRAINED (all 10 ROUTINE done). The TODO summary line id:390f — ✅ ack 2026-06-30 /relay human: confirmed: all 10 ROUTINE done; id:390f is the standing relay-status summary-line convention, not real backlog.
  is the standing relay-status checkbox (the tactical ledger lives in central
  `~/src/zkm/TODO.md`), so `unpromoted-scan.sh` will keep surfacing it as "1 un-promoted
  item / needs HANDOFF" — that is the summary-line convention, NOT real backlog. Next pool
  pass is idle/handoff, not execute (routine_open=0).
