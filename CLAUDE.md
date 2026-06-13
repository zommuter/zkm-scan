# zkm-scan — OCR plugin for zkm

OCR-extracts text from scanned-only PDFs and images (tesseract via pytesseract;
poppler via pdf2image for PDF rasterization) and writes one markdown file per
document into the knowledge store. Division of labor: **zkm-pdf takes PDFs with
a text layer, zkm-scan takes scanned-only ones** — see ARCHITECTURE.md §Routing
contract (and the known v0.3.0 asymmetry documented there).

This is one repo of the zkm polyrepo. It normally lives at
`~/src/zkm/plugins/zkm-scan/` inside the core checkout (gitignored by core);
the relative editable dep `zkm = { path = "../.." }` in `pyproject.toml`
REQUIRES that placement — `uv sync` fails if the repo is checked out elsewhere
without a zkm core two levels up.

## Commands

```bash
uv sync                  # dev env (Python 3.11+); resolves zkm core from ../..
uv run pytest            # full suite (unit tests mock tesseract/poppler)
uv run pytest -k 6913    # one roadmap item's done-check (see ROADMAP.md)
uv run ruff check src tests convert.py   # lint (line-length 100, py311)
```

State-modifying manual runs against a real store go through core:
`zkm convert scan` (subject to core's dirty-tree guard — set
`ZKM_BYPASS_DIRTY_CHECK=1` for dev runs, and note the concurrent-run guard
exits 75 if another convert/scrub/index is running).

## System requirements (runtime + integration tests)

- `tesseract` + language packs (default config wants `deu` and `eng`)
- poppler (`pdftoppm`) for PDF input via pdf2image
- Manjaro install: `pamac install tesseract tesseract-data-deu tesseract-data-eng poppler`

Unit tests do NOT need these (everything mocked). Integration tests
(`tests/test_integration_ocr.py`) skip themselves with a clear marker when the
binaries are missing.

## Layout & the dual-copy gotchas

```
convert.py               # SHIM ONLY — re-exports zkm_scan.convert.convert for
                         # filesystem discovery (core injects src/ on sys.path)
src/zkm_scan/
├── __init__.py
├── convert.py           # THE implementation — edit here, never in the shim
└── plugin.yaml          # copy #2 (packaged into the wheel)
plugin.yaml              # copy #1 (filesystem discovery reads this one)
tests/
```

- **Two `plugin.yaml` copies must stay byte-identical** (root = filesystem
  discovery; `src/zkm_scan/` = wheel). A sync-guard test enforces this; when
  you change one, change both.
- **Never put logic in root `convert.py`** — it exists only so core's
  filesystem scan (`plugins/*/plugin.yaml` + `convert.py`) finds the plugin in
  the dev workflow. Wheel installs use the `zkm.plugins` entry point
  (`scan = "zkm_scan"` → core imports `zkm_scan.convert`).
- Tests import `from zkm_scan.convert import ...` and patch
  `zkm_scan.convert.pytesseract` / `zkm_scan.convert._pdf_to_pil_images`.
  Patching the `convert` shim module does nothing.

## Config (bare snake_case keys — M2 convention)

Read from the `scan:` section of `<store>/zkm-config.yaml`; `convert()` receives
the merged dict. Keys are bare snake_case (`source_dir`, `lang`,
`min_text_chars`) — the pre-M2 `SCAN_*` env-style names are dead; do not
reintroduce them. Defaults live both in `plugin.yaml` (documentation/validation)
and as `config.get(..., default)` fallbacks in `convert()` — keep them in sync.

## Behavioral contract (v0.3.0)

- Two input paths: (1) owned `inbox/` symlinks — CAS sidecar must list a known
  upstream producer (`eml`, `photo`, `scan`), else no-op (plugin-spec
  no-op-on-unowned rule); (2) optional `source_dir` walk → CAS object under
  `originals/scans/` + `inbox/scans/` symlink.
- Output: `scans/YYYY/MM/<date>_<slug>.md`, frontmatter per core schema
  (`zkm.conformance.FRONTMATTER_REQUIRED`) plus `original`, `ocr_chars`.
- Date precedence: EXIF `DateTimeOriginal` (JPEG/TIFF) → file mtime.
- Dedup: SHA-256 of the source file vs `sha256:` frontmatter of existing
  `scans/**/*.md`. Re-runs emit nothing for known content.
- Below `min_text_chars` OCR output → silently skipped (no md). NOTE: skipped
  files are re-OCR'd on every run in v0.3.0 — fix is roadmap id:8810.
- `progress(current, total, message)` callback may raise to cancel
  (core's PluginInterrupt); partial results before the raise are kept.

## Testing conventions

- Hermetic: `tmp_path` stores built by `tests/conftest.py:make_store()`; no
  network, no real store, no system OCR in unit tests.
- Mock seams: `zkm_scan.convert.pytesseract.image_to_string`,
  `zkm_scan.convert.pytesseract.image_to_data`,
  `zkm_scan.convert._pdf_to_pil_images`, `zkm_scan.convert.pytesseract.get_languages`.
- Red tests in `tests/test_roadmap.py` are the executable spec for ROADMAP.md
  items (each carries a `# roadmap:XXXX` comment). They are SUPPOSED to fail
  until their item is implemented — do not delete or skip them to get green.

## Versioning

Global bump-and-tag + loose-0.x rule (see core CLAUDE.md / `~/.claude/CLAUDE.md`):
every `pyproject.toml` version change is tagged `vX.Y.Z` in the same commit.
Keep `PLUGIN_VERSION` in `src/zkm_scan/convert.py` and `version:` in BOTH
plugin.yaml copies equal to the pyproject version.

## Relay contract <!-- fables-executor contract v2 -->

This repo is managed by a reviewer/executor relay. Load the `fables-executor` skill
(`/fables-executor`) before working on any item, then follow its rules exactly.
