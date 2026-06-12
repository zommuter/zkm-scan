# zkm-scan architecture

Decisions with rationale and rejected alternatives. Code-level conventions live
in CLAUDE.md; executor tasks in ROADMAP.md.

## Routing contract with zkm-pdf ("scanned-only")

**The decision of what counts as scanned-only is made by text-layer probing,
and today it lives entirely in zkm-pdf.**

- **zkm-pdf** extracts the text layer with pypdf. If extracted chars <
  `min_text_chars` (zkm-pdf default **100**), it emits no md, and logs the file
  to `<store>/.zkm-state/zkm-pdf-skipped.jsonl` — explicitly "intended for
  zkm-scan". So: *text PDF → zkm-pdf; scanned-only PDF → falls through.*
- **zkm-scan** OCRs images and PDFs. Its own `min_text_chars` (default **10**)
  is a different knob with different semantics: a junk-OCR floor ("did tesseract
  read anything"), not a routing decision. The defaults differ on purpose —
  100 chars ≈ "has a real text layer", 10 chars ≈ "OCR found more than noise".

### Known asymmetry (v0.3.0) — being fixed via ROADMAP

zkm-scan does NOT reciprocate the contract: it OCRs **every** owned inbox PDF,
including ones with a perfectly good text layer. Consequence: a text PDF
attached to a mail is ingested twice — pypdf-extracted under `pdfs/` by zkm-pdf
AND OCR'd under `scans/` by zkm-scan (worse text, duplicate search hits).

Chosen fix (roadmap id:6913, judgment call logged in REVIEW_ME.md):

1. Skip a PDF whose CAS sidecar already lists a `pdf` producer (zkm-pdf has
   demonstrably claimed it — cheapest, zero-dep signal).
2. Otherwise probe the text layer with pypdf; if extracted chars ≥
   `pdf_text_threshold` (default 100, mirroring zkm-pdf), skip and log to
   `<store>/.zkm-state/zkm-scan-skipped.jsonl` with `reason: "text-layer"`.
   Text PDFs are *left for zkm-pdf even when zkm-pdf is not installed* —
   OCR-as-fallback was rejected because OCR output of a text PDF is strictly
   worse than extraction, and silently producing the worse version would mask
   the missing plugin.

Rejected alternatives:
- *Consume zkm-pdf's skip log as an allowlist* (only OCR what zkm-pdf
  explicitly skipped): breaks single-plugin installs and `source_dir` imports
  that never pass through zkm-pdf.
- *Shared core helper deciding routing for both plugins*: right end-state, but
  cross-repo; tracked separately as roadmap id:02bd [HARD] (single source of
  truth for the threshold + probe in zkm core, both plugins consuming it).

## Why a plugin of its own (vs OCR inside zkm-pdf)

Different system deps (tesseract + language packs + poppler vs pure-python
pypdf), different cost profile (OCR is seconds/page), and images are in scope
here but meaningless for zkm-pdf. Keeping zkm-pdf dependency-light was the
deciding factor.

## Input model: owned inbox + optional source_dir

- **Path 1 — inbox**: walk `inbox/**` symlinks with scan-able extensions,
  resolve to the CAS object, process only if the sidecar lists a known upstream
  producer (`eml`, `photo`, `scan`). Rationale: the plugin-spec
  no-op-on-unowned rule — foreign plugins stage files in `inbox/` too, and
  claiming them would corrupt their pipelines. Rejected: processing everything
  in `inbox/` (breaks plugin isolation), or an explicit handoff queue (more
  moving parts than sidecar inspection, which already exists).
- **Path 2 — `source_dir`**: external read-only walk → `zkm.cas.write_object`
  under `originals/scans/` → `inbox/scans/` symlink with sidecar producer
  `scan`. The symlink makes Path 2 output indistinguishable from Path 1 input
  (`scan` is in its own upstream set), so re-runs flow through one code path.

## Output model

- One md per document, `scans/YYYY/MM/<date>_<slug>.md`. Per-doc (not per-page)
  because a scanned letter is one retrieval unit; pages are preserved as
  `<!-- page N -->` markers in the body (page numbers keep their original
  index even when blank pages in between produce no text).
- Frontmatter: core required set + `original` (CAS-relative path) + `ocr_chars`.
  The body starts with a relative `[original PDF|image](...)` link so the md
  remains useful standalone.
- Date precedence EXIF `DateTimeOriginal` → mtime: scan date of a photographed
  receipt is closer to the document's real date than the file's copy-time.
  Rejected: OCR-extracted document dates (Phase-2 NER territory, not a
  converter's job).

## Dedup & idempotency

SHA-256 of source bytes, compared against `sha256:` frontmatter harvested from
`scans/**/*.md` at startup. The md tree itself is the ledger — no extra state
file to drift (DB-pivot rejected store-wide; see core docs). Two costs accepted:
startup scan is O(corpus), and *skipped* (below-threshold) files have no md, so
they are re-OCR'd every run — that one is real pain (OCR is expensive) and is
fixed by a `.zkm-state/zkm-scan-skipped.jsonl` ledger (roadmap id:8810),
mirroring zkm-pdf's existing pattern rather than inventing a new format.

## Packaging: src layout + shim (SB5)

`src/zkm_scan/` is the real package (wheel, entry point `scan = "zkm_scan"`);
root `convert.py` is a one-line re-export shim so core's filesystem discovery
(dev workflow: repo dropped under `plugins/`) still finds a loadable
`convert.py`. Rejected: root-module-only (cannot build a clean wheel),
package-only (breaks filesystem discovery for un-installed dev checkouts).
Cost: `plugin.yaml` exists twice (root for filesystem scan, in-package for the
wheel) — guarded by a byte-equality test.

## Config (M2)

Bare snake_case keys (`source_dir`, `lang`, `min_text_chars`) from the `scan:`
section of `zkm-config.yaml`. The pre-M2 `SCAN_*` names survived in the test
suite long after the code migrated — which, combined with the SB5 shim, silently
broke the whole suite (tests imported the shim and patched attributes it does
not have; collection error since). Lesson encoded as tests now; do not let
tests target the shim.

## Testing strategy

Two tiers:
1. **Unit (default)**: tesseract/poppler fully mocked at the
   `zkm_scan.convert.*` seams; hermetic tmp stores. Rationale: OCR output is
   environment-sensitive (tesseract version, language packs) — asserting on it
   in unit tests would be flaky and slow.
2. **Integration** (`tests/test_integration_ocr.py`): real tesseract + poppler,
   auto-skip with a clear marker when binaries are missing. Asserts loose
   substring matches on large-font rendered text, never exact OCR output.
