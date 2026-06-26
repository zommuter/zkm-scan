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

- [x] Honor the zkm-pdf routing contract: skip text-layer PDFs [ROUTINE] <!-- id:6913 -->
  - **Acceptance**: A PDF whose CAS sidecar already lists a `pdf` producer is not
    OCR'd and produces no md. A PDF with an extractable text layer of ≥
    `pdf_text_threshold` chars (new config key, default 100 — mirrors zkm-pdf's
    `min_text_chars`) is not OCR'd; instead one line is appended to
    `<store>/.zkm-state/zkm-scan-skipped.jsonl` with `reason: "text-layer"` and
    the probed char count (`text_chars`). Scanned-only PDFs (no/short text
    layer) keep being OCR'd exactly as before. Probe uses `pypdf` (add to
    dependencies; also add the `pdf_text_threshold` entry to BOTH plugin.yaml
    copies). Probe failures (corrupt PDF) fall through to OCR — when in doubt,
    scan.
  - **Tests**: `tests/test_roadmap.py::test_6913_pdf_producer_sidecar_skipped`,
    `::test_6913_text_layer_pdf_skipped_and_logged` (`# roadmap:6913`)
    (currently RED); `::test_6913_scanned_pdf_still_processed` is a
    green-by-design guard — it must STAY green (do not over-skip)
  - **Done-check**: `uv run pytest tests/test_roadmap.py -k 6913`
  - **Context**: ARCHITECTURE.md §Routing contract (chosen policy + rejected
    alternatives; judgment call in REVIEW_ME.md). zkm-pdf reference:
    `~/src/zkm/plugins/zkm-pdf/src/zkm_pdf/convert.py` (`_extract_text`,
    `_log_skipped`). Applies to both input paths (inbox + source_dir).

- [x] Skip-ledger for below-threshold OCR output (stop re-OCR every run) [ROUTINE] <!-- id:8810 -->
  - **Acceptance**: When OCR output falls below `min_text_chars`, the file's
    sha256 is recorded in `.zkm-state/zkm-scan-skipped.jsonl` with
    `reason: "below-min-chars"`, the observed `ocr_chars`, and the `threshold`
    in effect. Subsequent runs consult the ledger and do NOT re-OCR a sha whose
    recorded `threshold` equals the current `min_text_chars`; if the configured
    threshold changed, the file is re-OCR'd (entry superseded by appending a new
    line — the ledger is append-only, last entry per sha wins). Ledger read
    failures (missing/corrupt lines) degrade to re-OCR, never crash.
  - **Tests**: `tests/test_roadmap.py::test_8810_below_threshold_not_reocred`,
    `::test_8810_skip_logged_with_reason` (`# roadmap:8810`) (currently RED)
  - **Done-check**: `uv run pytest tests/test_roadmap.py -k 8810`
  - **Context**: ARCHITECTURE.md §Dedup & idempotency. Shares the ledger
    format/helper with 6913 (see header note).

- [x] Graceful error for missing tesseract language packs [ROUTINE] <!-- id:5c02 -->
  - **Acceptance**: Before any OCR work, the configured `lang` string is split
    on `+` and checked against `pytesseract.get_languages()`; if any requested
    pack is missing, `convert()` raises `ValueError` whose message names the
    missing pack(s), the full configured `lang`, and a generic install hint
    ("install the tesseract language data for ..." — no distro-specific
    command; published-generic rule). If `get_languages()` itself raises
    (tesseract absent/old), the pre-check is skipped silently and behavior is
    unchanged — the pre-check must never introduce a new failure mode for
    environments that worked before.
  - **Tests**: `tests/test_roadmap.py::test_5c02_missing_language_pack_clear_error`,
    `::test_5c02_get_languages_unavailable_falls_through` (`# roadmap:5c02`)
    (first RED; second is a green-by-design guard for the fall-through clause)
  - **Done-check**: `uv run pytest tests/test_roadmap.py -k 5c02`
  - **Context**: mock seam `zkm_scan.convert.pytesseract.get_languages`.

- [x] Configurable DPI for PDF rasterization [ROUTINE] <!-- id:c199 -->
  - **Acceptance**: New config key `dpi` (int, default 300) forwarded as
    `dpi=` kwarg to `pdf2image.convert_from_path` for every PDF. Default 300
    (OCR-quality choice over pdf2image's implicit 200 — judgment call in
    REVIEW_ME.md). Entry added to BOTH plugin.yaml copies. Images are
    unaffected.
  - **Tests**: `tests/test_roadmap.py::test_c199_default_dpi_300`,
    `::test_c199_configured_dpi_forwarded` (`# roadmap:c199`) (currently RED)
  - **Done-check**: `uv run pytest tests/test_roadmap.py -k c199`
  - **Context**: `_ocr_pdf` / `_pdf_to_pil_images` in `src/zkm_scan/convert.py`.

- [x] Record OCR confidence in frontmatter (observe-only) [ROUTINE] <!-- id:5d7d -->
  - **Acceptance**: Each emitted md gains `ocr_confidence`: the mean of all
    word-level confidences ≥ 0 from `pytesseract.image_to_data` (dict output),
    across all pages for PDFs, rounded to 1 decimal. No skipping/flagging based
    on the value — observe before preventing (per global design heuristics);
    junk detection policy comes later with real data. If `image_to_data` is
    unavailable or returns no words, omit the key rather than writing null.
  - **Tests**: `tests/test_roadmap.py::test_5d7d_ocr_confidence_in_frontmatter`
    (`# roadmap:5d7d`) (currently RED)
  - **Done-check**: `uv run pytest tests/test_roadmap.py -k 5d7d`
  - **Context**: REVIEW_ME.md (definition of the mean). Watch cost: do not run
    tesseract twice per image — either derive text from `image_to_data` output
    or accept one extra pass and say so in the commit message.

- [x] HEIC/HEIF input support via optional pillow-heif [ROUTINE] <!-- id:f7d3 -->
  - **Acceptance**: `.heic`/`.heif` join the scannable extensions. Support is
    probed by a LAZY `import pillow_heif` at convert() time (not module import —
    the dep is optional and must not break plain installs):
    available → `pillow_heif.register_heif_opener()` once, files OCR'd like any
    image; unavailable → each `.heic`/`.heif` candidate is logged to
    `.zkm-state/zkm-scan-skipped.jsonl` with `reason: "heic-unsupported"`
    instead of being silently invisible. `pillow-heif` goes into a new
    `[project.optional-dependencies] heic` extra, NOT core dependencies.
  - **Tests**: `tests/test_roadmap.py::test_f7d3_heic_without_pillow_heif_logs_notice`
    (RED), `::test_f7d3_heic_processed_when_supported` (importorskip-guarded)
    (`# roadmap:f7d3`)
  - **Done-check**: `uv run pytest tests/test_roadmap.py -k f7d3`
  - **Context**: extension sets `_IMAGE_EXTS`/`_SCAN_EXTS`; ledger helper from
    6913/8810.

- [x] Frontmatter conformance: tz-aware EXIF dates + pages for PDFs [ROUTINE] <!-- id:aae8 -->
  - **Acceptance**: (1) The EXIF date path produces a tz-aware ISO 8601 string —
    EXIF `DateTimeOriginal` has no timezone, so attach the LOCAL timezone
    (`datetime.astimezone()` on the naive value), matching the mtime path's
    behavior. Emitted docs pass `zkm.conformance.validate_frontmatter` with
    zero findings. (2) PDF-sourced mds gain `pages: <int>` (total page count,
    including blank ones), matching zkm-pdf's field for cross-plugin frontmatter
    parity.
  - **Tests**: `tests/test_roadmap.py::test_aae8_exif_date_is_tz_aware_and_conformant`,
    `::test_aae8_pdf_frontmatter_has_pages` (`# roadmap:aae8`) (currently RED)
  - **Done-check**: `uv run pytest tests/test_roadmap.py -k aae8`
  - **Context**: `_exif_datetime`/`_exif_str_to_iso` in convert.py; core schema
    in `src/zkm/conformance.py` (zkm core, importable from this env).

- [x] Namespace the OCR confidence frontmatter key `ocr_confidence` → `scan_ocr_confidence` [ROUTINE] <!-- id:874c -->
  - **Why**: Owner decision 2026-06-13 (REVIEW_ME 5d7d / zkm id:cfd1, frontmatter-schema
    mtg): the field is plugin-private (single OCR producer) and must follow the flat
    `<plugin>_<key>` namespacing rule. Item 5d7d shipped the bare `ocr_confidence` key
    (convert.py ~line 287) — this refines it to the agreed name.
  - **Acceptance**: Emitted md frontmatter uses `scan_ocr_confidence:` (not
    `ocr_confidence:`); same observe-only value semantics as 5d7d (mean word-level
    confidence ≥0, rounded to 1 decimal, omit when unavailable). Update the 5d7d test's
    assertion to the new key name (decision-driven rename, NOT a weakening — the original
    `ocr_confidence` assertion is superseded by owner ruling). Reverts to bare
    `ocr_confidence` ONLY if a second OCR consumer is named at implementation time.
  - **Done-check**: `uv run pytest tests/test_roadmap.py -k 5d7d`
  - **Context**: convert.py ~line 287 (`fm["ocr_confidence"] = confidence`). Supersedes
    the closed 5d7d acceptance on the key name only.

- [x] DST-safe EXIF timezone offset (IANA zone, photo's own date) [ROUTINE] <!-- id:600c -->
  - **Why**: Owner decision 2026-06-13 (REVIEW_ME aae8): item aae8 shipped
    `dt.astimezone()` (convert.py `_exif_str_to_iso`, line 491) which attaches the
    machine's CURRENT UTC offset, mixing up DST — a summer photo processed in winter
    gets the winter offset. Safeguard: resolve the offset from a named IANA zone applied
    to the photo's OWN naive date.
  - **Acceptance**: `_exif_str_to_iso` localizes the naive EXIF datetime via
    `zoneinfo.ZoneInfo(<local IANA zone>)` so the offset reflects the photo's date, not
    "now". A naive Jan EXIF date and a naive Jul EXIF date on a DST zone (Europe/Zurich)
    must yield `+01:00` and `+02:00` respectively. Still passes
    `zkm.conformance.validate_frontmatter`. Add a test asserting the Jan/Jul offsets.
  - **Done-check**: `uv run pytest tests/test_roadmap.py -k aae8`
  - **Context**: convert.py `_exif_str_to_iso` (~line 483-493). Same safeguard applies to
    zkm-photo 33e5 (cross-repo — routed to shared inbox). Supersedes the
    `datetime.astimezone()` instruction in the closed aae8 acceptance.

- [x] Switch zkm-scan to the shared `zkm.pdftext` helper (unify scanned-only routing with zkm-pdf) [ROUTINE] <!-- id:02bd -->
  - **DECIDED** 2026-06-18 (D2, `dotclaude-skills/docs/meeting-notes/2026-06-18-1219-cross-gated-hard-triage.md`) + helper BUILT 2026-06-22 (`zkm/src/zkm/pdftext.py`). No longer a meeting — only the adoption never landed: zkm-scan still uses its OWN local `pdf_text_threshold` (`src/zkm_scan/convert.py:106`, `int(config.get("pdf_text_threshold", 100))`), not the shared helper, so cross-plugin drift (a PDF processed by neither) is still possible.
  - **Acceptance**: zkm-scan resolves the threshold via `zkm.pdftext.resolve_threshold` (the single shared `pdf_text_threshold` key) instead of its local `config.get` (`src/zkm_scan/convert.py:106`, currently `int(config.get("pdf_text_threshold", 100))`); the `min_text_chars=10` OCR floor stays SEPARATE (it's a different concern). Deprecate the local key path as a one-release alias. Coordinated with id:9475 (zkm-pdf side). RED test: zkm-pdf and zkm-scan return the SAME scanned-only verdict for the same PDF + threshold.
  - **Done-check**: `uv run pytest tests/test_roadmap.py -k 02bd`
  - **History**: Originally `[HARD — meeting]`/GATED-for-`/meeting` id:2d20 (the cross-repo
    `zkm.pdftext` helper + shared-key API design). The DESIGN is settled and the HELPER shipped
    2026-06-22 (`zkm/src/zkm/pdftext.py`, providing `resolve_threshold`/`probe`/`is_scanned_only`,
    adopting zkm-pdf's `.strip()`+skip-empty-pages semantics, id:1055-reviewed) — so this is no
    longer a meeting and no longer HARD: only the single-repo ADOPTION (swapping zkm-scan's local
    `config.get` for the shared resolver) remains, which is one Sonnet session. Subsumes zkm-pdf
    id:9475. See `dotclaude-skills/docs/meeting-notes/2026-06-18-1219-cross-gated-hard-triage.md`.

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
