# Human review queue <!-- budget: 15 min -->

Judgment calls encoded in red tests — confirm or correct the interpretation.
Max ~10 open boxes; the reviewer prunes resolved ones each review turn.

- [x] id:1686 — regression from zkm core e2c4: bare frontmatter key `ocr_chars` now warns
  under `validate_frontmatter` (plugin keys must be `scan_`-prefixed), so
  `test_aae8_exif_date_is_tz_aware_and_conformant` is RED though the zkm-scan window is empty
  (drift arrived via the `zkm==0.16.0` editable dep). Filed [ROUTINE] id:1686 to rename
  `ocr_chars` → `scan_ocr_chars` (frontmatter emission only, not the skip-log field), following
  the same owner flat-namespacing ruling as the closed id:874c. **Confirm** this rename is the
  intended fix (vs. registering `ocr_chars` core-side), given it changes a key already written
  into existing scan stores — same migration posture as 874c, which shipped as [ROUTINE].
  — **human 2026-07-11 (relay human): DECIDED rename in plugin `ocr_chars`→`scan_ocr_chars`
  per id:874c precedent; impl stays open executor work.**
