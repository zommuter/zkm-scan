# Roadmap <!-- relay roadmap v1 -->

Executor-facing task spec. Each item is sized for ONE Sonnet session. Items are
the single source of truth — TODO.md carries only a summary line. Executors tick
checkboxes; only the reviewer adds, removes, or re-scopes items.

All implementation goes into `src/zkm_scan/convert.py` (NEVER the root shim).
Items 6913 and 8810 share the `.zkm-state/zkm-scan-skipped.jsonl` ledger format —
whichever lands first defines the writer helper; the other reuses it. Entry shape
(one JSON object per line, mirroring zkm-pdf's `zkm-pdf-skipped.jsonl`):
`{"path", "sha256", "reason", ...reason-specific fields}`.

## Items

- [ ] [ROUTINE] Namespace frontmatter key `ocr_chars` → `scan_ocr_chars` (frontmatter emission only; id:874c flat-namespacing precedent; existing scan stores already carry the key, migration accepted). Decision-gate resolved 2026-07-11 (human). <!-- id:1686 -->
  - **Why**: zkm core id:e2c4 added a warn-level conformance rule (`zkm.conformance.validate_frontmatter`) — a plugin-emitted bare scalar frontmatter key must be core-owned or `<plugin>_`-prefixed. id:874c namespaced the sibling `ocr_confidence` → `scan_ocr_confidence` per the owner's 2026-06-13 flat-namespacing ruling, but left the `ocr_chars` frontmatter key bare. Core now flags it, which fails the aae8 conformance assertion. Regression surfaced 2026-07-04 (empty zkm-scan window; drift entered via the `zkm==0.16.0` editable dep, not a zkm-scan commit).
  - **Scope precision**: rename ONLY the FRONTMATTER emission at `src/zkm_scan/convert.py:282` (`fm["ocr_chars"]`/the `fm` dict literal). The `ocr_chars` at `src/zkm_scan/convert.py:254` is a `.zkm-state/*-skipped.jsonl` skip-log JSON field (id:8810), NOT md frontmatter — the conformance rule does not apply to it; leave it (and its consumer `tests/test_roadmap.py:126` `entries[0]["ocr_chars"] == 1`) UNCHANGED.
  - **Acceptance**: Emitted md frontmatter uses `scan_ocr_chars:` (not bare `ocr_chars:`); same value semantics (`len(text)`). Update the frontmatter-key consumers: `tests/test_convert.py:55` (`post.metadata["scan_ocr_chars"] > 0`) and `ARCHITECTURE.md:74`. Decision-driven rename per the same owner ruling as id:874c — NOT a weakening.
  - **Tests**: `tests/test_roadmap.py::test_aae8_exif_date_is_tz_aware_and_conformant` (`# roadmap:aae8`) is the RED spec — it asserts `validate_frontmatter(...) == []` and currently fails on the `ocr_chars` warn. No new red test needed.
  - **Done-check**: `uv run pytest tests/test_roadmap.py -k aae8` (green) AND `uv run pytest -q` (full suite green).
  - **Context**: `src/zkm_scan/convert.py:282`; mirrors closed id:874c (`ocr_confidence`); core rule in `zkm/src/zkm/conformance.py:174-189` (id:e2c4).

- [ ] [HARD — meeting] 🚧 GATED: the `original` frontmatter key needs a cross-repo core-registry ruling (shared by zkm-pdf/zkm-eml/zkm-photo, not core-owned) — needs a /meeting decision. Split from id:1686 (2026-07-14). <!-- id:df3e -->
## Done (relay-verified)

- id:6913 — zkm-pdf routing contract (text-layer probe + pdf-producer sidecar skip)
- id:8810 — below-threshold skip ledger (no re-OCR on unchanged threshold)
- id:c199 — configurable DPI for PDF rasterization (default 300)
- id:5d7d — OCR confidence in frontmatter (observe-only)
- id:f7d3 — HEIC/HEIF support via optional pillow-heif extra
- id:aae8 — tz-aware EXIF dates + pages field for PDF-sourced docs
- id:5c02 — graceful ValueError for missing tesseract language packs
- id:874c — namespace OCR confidence key `ocr_confidence` → `scan_ocr_confidence`
- id:600c — DST-safe EXIF timezone offset (IANA zone on the photo's own date)
- id:02bd — adopt shared `zkm.pdftext` helper for scanned-only routing (stripped char count + `resolve_threshold`; verified green 2026-06-26)
