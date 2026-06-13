"""zkm-scan — OCR images and scanned PDFs into the knowledge store.

Two input paths:
  1. inbox/ items owned by a known upstream plugin (eml, photo, scan) — primary.
     Reuses the existing CAS object; merges a 'scan' producer into its sidecar.
  2. Optional SCAN_SOURCE_DIR — walks an external directory, writes new CAS
     objects under originals/scans/, creates inbox/scans/ symlinks.

Silently skips files whose OCR output has fewer than SCAN_MIN_TEXT_CHARS chars.

System requirements: tesseract-ocr + language packs; poppler (for PDF input).
Python requirements: pytesseract, pdf2image, Pillow.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import frontmatter
import pytesseract
from pdf2image import convert_from_path as _pdf_to_pil_images
from PIL import Image

from zkm.atomic import write_atomic
from zkm.cas import write_object
from zkm.hashing import sha256_file
from zkm.inbox import build_canonical_index, symlink_with_sidecar
from zkm.sidecar import merge_producer, read_sidecar

PLUGIN_NAME = "scan"
PLUGIN_VERSION = "0.3.0"

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".gif", ".webp"}
_HEIC_EXTS = {".heic", ".heif"}
_SCAN_EXTS = _IMAGE_EXTS | {".pdf"} | _HEIC_EXTS
_KNOWN_UPSTREAM_PLUGINS = {"eml", "photo", "scan"}

_heif_registered = False


def _ensure_heif() -> bool:
    """Lazy import pillow_heif; register opener once. Returns True if available."""
    global _heif_registered
    try:
        import pillow_heif  # type: ignore[import]
        if pillow_heif is None:
            raise ImportError("pillow_heif is None")
        if not _heif_registered:
            pillow_heif.register_heif_opener()
            _heif_registered = True
        return True
    except ImportError:
        return False


def _write_skip_log(store_path: Path, entry: dict) -> None:
    """Append one JSON entry to <store>/.zkm-state/zkm-scan-skipped.jsonl."""
    state_dir = store_path / ".zkm-state"
    state_dir.mkdir(parents=True, exist_ok=True)
    log_path = state_dir / "zkm-scan-skipped.jsonl"
    with log_path.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")


def _read_skip_log(store_path: Path) -> list[dict]:
    """Read all entries from the skip ledger (empty list if absent/corrupt)."""
    log_path = store_path / ".zkm-state" / "zkm-scan-skipped.jsonl"
    if not log_path.exists():
        return []
    entries = []
    for line in log_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # degrade gracefully on corrupt lines
    return entries


def _last_skip_entry(entries: list[dict], sha: str) -> dict | None:
    """Return the last ledger entry for a given sha256 (last wins semantics)."""
    result = None
    for e in entries:
        if e.get("sha256") == sha:
            result = e
    return result


def convert(store_path: Path, config: dict, *, progress=None) -> list[Path]:
    """OCR images and scanned PDFs from inbox/ and optional SCAN_SOURCE_DIR.

    Returns a list of paths to newly created .md files.
    progress: optional callback(current, total, message). May raise PluginInterrupt.
    """
    lang = str(config.get("lang", "deu+eng") or "deu+eng")
    min_chars = int(config.get("min_text_chars", 10))
    dpi = int(config.get("dpi", 300))
    src_dir_raw = str(config.get("source_dir", "") or "")
    pdf_text_threshold = int(config.get("pdf_text_threshold", 100))

    # id:5c02 — pre-check lang packs before any OCR work
    _check_lang_packs(lang)

    for subdir in ["scans", "originals/scans", "inbox/scans"]:
        (store_path / subdir).mkdir(parents=True, exist_ok=True)

    existing_shas = _scan_existing_shas(store_path / "scans")
    skip_entries = _read_skip_log(store_path)
    created: list[Path] = []

    # ── Path 1: inbox-sourced items ───────────────────────────────────────────
    inbox_candidates = _find_inbox_candidates(store_path)
    total = len(inbox_candidates)
    for i, (real_path, cas_sidecar) in enumerate(inbox_candidates, 1):
        if progress:
            progress(i, total, real_path.name)  # may raise PluginInterrupt
        sha = sha256_file(real_path)
        if sha in existing_shas:
            continue

        # id:6913 — skip inbox PDFs already claimed by zkm-pdf
        if real_path.suffix.lower() == ".pdf" and _has_pdf_producer(cas_sidecar):
            continue

        md = _emit_md(
            store_path=store_path,
            src_path=real_path,
            sha=sha,
            cas_path=real_path,
            cas_sidecar=cas_sidecar,
            lang=lang,
            min_chars=min_chars,
            dpi=dpi,
            pdf_text_threshold=pdf_text_threshold,
            skip_entries=skip_entries,
        )
        if md:
            created.append(md)
            existing_shas.add(sha)

    # ── Path 2: optional external SCAN_SOURCE_DIR ─────────────────────────────
    if src_dir_raw:
        src = Path(src_dir_raw).expanduser().resolve()
        if not src.exists():
            raise FileNotFoundError(f"source_dir does not exist: {src}")
        src_candidates = sorted(
            f for f in src.rglob("*")
            if f.is_file() and f.suffix.lower() in _SCAN_EXTS
        )
        canonical_index = build_canonical_index(store_path, "inbox/scans")
        inbox_scans_dir = store_path / "inbox" / "scans"
        total2 = len(src_candidates)
        for i, src_file in enumerate(src_candidates, 1):
            if progress:
                progress(i, total2, src_file.name)  # may raise PluginInterrupt

            # id:f7d3 — HEIC/HEIF: skip with log if pillow-heif unavailable
            if src_file.suffix.lower() in _HEIC_EXTS:
                if not _ensure_heif():
                    _write_skip_log(store_path, {
                        "path": str(src_file),
                        "reason": "heic-unsupported",
                    })
                    continue

            sha = sha256_file(src_file)
            if sha in existing_shas:
                continue

            # id:6913 — skip source_dir PDFs with extractable text layer
            if src_file.suffix.lower() == ".pdf":
                text_chars = _probe_pdf_text(src_file)
                if text_chars is not None and text_chars >= pdf_text_threshold:
                    _write_skip_log(store_path, {
                        "path": str(src_file),
                        "sha256": sha,
                        "reason": "text-layer",
                        "text_chars": text_chars,
                    })
                    continue

            cas_path = write_object(store_path, "originals/scans", src_file)
            cas_sidecar = cas_path.with_name(cas_path.name + ".json")
            symlink_with_sidecar(
                cas_object=cas_path,
                link_dir=inbox_scans_dir,
                link_name=src_file.name.lower(),
                producer={"plugin": PLUGIN_NAME, "message": str(src_file), "sha256": sha},
                canonical_index=canonical_index,
            )
            md = _emit_md(
                store_path=store_path,
                src_path=src_file,
                sha=sha,
                cas_path=cas_path,
                cas_sidecar=cas_sidecar,
                lang=lang,
                min_chars=min_chars,
                dpi=dpi,
                pdf_text_threshold=pdf_text_threshold,
                skip_entries=skip_entries,
                preextracted_text=None,
            )
            if md:
                created.append(md)
                existing_shas.add(sha)

    return created


# ── Core md-emit helper ───────────────────────────────────────────────────────

def _emit_md(
    *,
    store_path: Path,
    src_path: Path,
    sha: str,
    cas_path: Path,
    cas_sidecar: Path,
    lang: str,
    min_chars: int,
    dpi: int = 300,
    pdf_text_threshold: int = 100,
    skip_entries: list[dict] | None = None,
    preextracted_text: str | None = None,
) -> Path | None:
    """OCR src_path, write md, update CAS sidecar. Returns md path or None on skip."""
    if skip_entries is None:
        skip_entries = []

    # id:8810 — consult skip ledger before OCR
    last = _last_skip_entry(skip_entries, sha)
    if last and last.get("reason") == "below-min-chars" and last.get("threshold") == min_chars:
        return None

    text = preextracted_text if preextracted_text is not None else _ocr_file(src_path, lang, dpi=dpi)

    if len(text) < min_chars:
        # id:8810 — record this sha as below-threshold
        entry = {
            "sha256": sha,
            "reason": "below-min-chars",
            "ocr_chars": len(text),
            "threshold": min_chars,
        }
        _write_skip_log(store_path, entry)
        return None

    date_str = _exif_datetime(src_path) or _mtime_iso(src_path)
    date_prefix = date_str[:10]
    year, month = date_prefix[:4], date_prefix[5:7]

    scans_dir = store_path / "scans" / year / month
    scans_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(src_path.stem)
    out = _unique_path(scans_dir, date_prefix, slug)

    original_rel = str(cas_path.relative_to(store_path))
    rel_link = os.path.relpath(cas_path, out.parent)
    ext = src_path.suffix.lower()
    file_type = "PDF" if ext == ".pdf" else "image"

    fm: dict = {
        "source": PLUGIN_NAME,
        "processor": PLUGIN_NAME,
        "processor_version": PLUGIN_VERSION,
        "date": date_str,
        "tags": [],
        "sha256": sha,
        "original": original_rel,
        "ocr_chars": len(text),
    }

    # id:aae8 — pages field for PDF-sourced docs
    if ext == ".pdf":
        fm["pages"] = _count_pdf_pages(src_path, lang, dpi)

    # id:5d7d/id:874c — OCR confidence (observe-only; namespaced key)
    confidence = _ocr_confidence(src_path, lang, dpi)
    if confidence is not None:
        fm["scan_ocr_confidence"] = confidence

    body = f"[original {file_type}]({rel_link})\n\n{text}\n"
    write_atomic(out, frontmatter.dumps(frontmatter.Post(body, **fm)))

    merge_producer(
        cas_sidecar,
        sha256=sha,
        producer={"plugin": PLUGIN_NAME, "message": str(out.relative_to(store_path)), "sha256": sha},
    )

    return out


# ── Language pack pre-check ───────────────────────────────────────────────────

def _check_lang_packs(lang: str) -> None:
    """Raise ValueError if any requested lang pack is missing.

    If get_languages() itself raises (tesseract absent/old), skip silently.
    """
    try:
        available = set(pytesseract.get_languages())
    except Exception:  # noqa: BLE001
        return  # fall through — pre-check must not introduce new failure modes
    requested = [p for p in lang.split("+") if p]
    missing = [p for p in requested if p not in available]
    if missing:
        raise ValueError(
            f"Missing tesseract language pack(s): {', '.join(missing)}. "
            f"Configured lang: {lang!r}. "
            f"Install the tesseract language data for: {', '.join(missing)}."
        )


# ── OCR helpers ───────────────────────────────────────────────────────────────

def _ocr_file(path: Path, lang: str, *, dpi: int = 300) -> str:
    """OCR a file (image or PDF) and return the combined text."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _ocr_pdf(path, lang, dpi=dpi)
    return _ocr_image(Image.open(path), lang)


def _ocr_image(img: Image.Image, lang: str) -> str:
    """Run tesseract on a single PIL Image."""
    return pytesseract.image_to_string(img, lang=lang).strip()


def _ocr_pdf(path: Path, lang: str, *, dpi: int = 300) -> str:
    """Convert a PDF to images page-by-page and OCR each page.

    id:c199: dpi is forwarded to _pdf_to_pil_images (default 300 per REVIEW_ME.md).
    """
    pages = _pdf_to_pil_images(str(path), dpi=dpi)
    parts: list[str] = []
    for i, page_img in enumerate(pages, 1):
        text = _ocr_image(page_img, lang).strip()
        if text:
            parts.append(f"<!-- page {i} -->\n\n{text}")
    return "\n\n".join(parts)


def _count_pdf_pages(path: Path, lang: str, dpi: int) -> int:
    """Return the total page count for a PDF (used for id:aae8 pages field)."""
    try:
        pages = _pdf_to_pil_images(str(path), dpi=dpi)
        return len(pages)
    except Exception:  # noqa: BLE001
        return 0


def _ocr_confidence(path: Path, lang: str, dpi: int = 300) -> float | None:
    """Compute mean word-level OCR confidence (conf >= 0) for id:5d7d.

    Returns None if image_to_data is unavailable or yields no words.
    Accepts one extra OCR pass per image (see commit message note).
    """
    try:
        ext = path.suffix.lower()
        if ext == ".pdf":
            pages = _pdf_to_pil_images(str(path), dpi=dpi)
        else:
            pages = [Image.open(path)]

        confs: list[float] = []
        for page_img in pages:
            data = pytesseract.image_to_data(page_img, lang=lang, output_type=pytesseract.Output.DICT)
            for c in data.get("conf", []):
                try:
                    cf = float(c)
                    if cf >= 0:
                        confs.append(cf)
                except (ValueError, TypeError):
                    continue

        if not confs:
            return None
        return round(sum(confs) / len(confs), 1)
    except Exception:  # noqa: BLE001
        return None


# ── PDF text-layer probe (id:6913) ────────────────────────────────────────────

def _probe_pdf_text(path: Path) -> int | None:
    """Return char count of extractable text in PDF, or None on failure.

    Uses pypdf. Failure (corrupt PDF, import error) returns None so the file
    falls through to OCR (when in doubt, scan).
    """
    try:
        import pypdf  # type: ignore[import]
        reader = pypdf.PdfReader(str(path))
        total = sum(len(page.extract_text() or "") for page in reader.pages)
        return total
    except Exception:  # noqa: BLE001
        return None


def _has_pdf_producer(cas_sidecar: Path) -> bool:
    """Return True if sidecar lists a 'pdf' producer (zkm-pdf has claimed it)."""
    data = read_sidecar(cas_sidecar)
    if not data:
        return False
    return any(p.get("plugin") == "pdf" for p in data.get("producers", []))


# ── Inbox discovery helpers ───────────────────────────────────────────────────

def _find_inbox_candidates(store_path: Path) -> list[tuple[Path, Path]]:
    """Return (real_path, cas_sidecar_path) for owned inbox files.

    'Owned' means the CAS sidecar lists at least one known upstream plugin
    (eml, photo, scan), satisfying the plugin-spec no-op-on-unowned contract.
    """
    inbox = store_path / "inbox"
    if not inbox.exists():
        return []
    results: list[tuple[Path, Path]] = []
    seen_real: set[str] = set()
    for link in sorted(inbox.rglob("*")):
        if not link.is_symlink():
            continue
        if link.suffix.lower() not in _SCAN_EXTS:
            continue
        try:
            real = link.resolve()
        except OSError:
            continue
        if not real.is_file():
            continue
        key = str(real)
        if key in seen_real:
            continue
        seen_real.add(key)
        cas_sidecar = real.with_name(real.name + ".json")
        if not _is_owned(cas_sidecar):
            continue
        results.append((real, cas_sidecar))
    return results


def _is_owned(cas_sidecar: Path) -> bool:
    """Return True if this CAS object was produced by a known upstream plugin."""
    data = read_sidecar(cas_sidecar)
    if not data:
        return False
    return any(p.get("plugin") in _KNOWN_UPSTREAM_PLUGINS for p in data.get("producers", []))


# ── Metadata helpers ──────────────────────────────────────────────────────────

def _exif_datetime(path: Path) -> str | None:
    """Extract DateTimeOriginal from JPEG/TIFF EXIF, return tz-aware ISO 8601 or None.

    id:aae8: attaches local timezone to the naive EXIF datetime.
    """
    if path.suffix.lower() not in {".jpg", ".jpeg", ".tiff", ".tif"}:
        return None
    try:
        from PIL import ExifTags
        img = Image.open(path)
        exif = img._getexif()  # type: ignore[attr-defined]
        if not exif:
            return None
        for tag_id, value in exif.items():
            if ExifTags.TAGS.get(tag_id) == "DateTimeOriginal":
                # Tesseract/EXIF format: "YYYY:MM:DD HH:MM:SS"
                return _exif_str_to_iso(str(value))
    except Exception:  # noqa: BLE001
        pass
    return None


def _local_zone() -> ZoneInfo | None:
    """Return the machine's local IANA timezone, or None if undetectable.

    id:600c: use a named IANA zone so the UTC offset reflects the photo's own
    date (DST-safe), not the machine's current offset at processing time.
    """
    try:
        # Resolve /etc/localtime symlink → …/zoneinfo/Region/City
        ltime = Path("/etc/localtime").resolve()
        parts = ltime.parts
        zi_idx = next(i for i, p in enumerate(parts) if p == "zoneinfo")
        return ZoneInfo("/".join(parts[zi_idx + 1 :]))
    except (StopIteration, ZoneInfoNotFoundError, Exception):
        pass
    try:
        return ZoneInfo(Path("/etc/timezone").read_text().strip())
    except (ZoneInfoNotFoundError, Exception):
        pass
    return None


_LOCAL_ZONE: ZoneInfo | None = _local_zone()


def _exif_str_to_iso(s: str) -> str | None:
    """Convert EXIF datetime string 'YYYY:MM:DD HH:MM:SS' to tz-aware ISO 8601.

    id:aae8/id:600c: localizes via a named IANA zone so the UTC offset is
    resolved from the photo's own date, not the machine's current offset
    (DST-safe). Falls back to astimezone() when the local zone is undetectable.
    """
    try:
        dt = datetime.strptime(s, "%Y:%m:%d %H:%M:%S")
        if _LOCAL_ZONE is not None:
            # replace() with a named zone: offset is derived from photo's date
            return dt.replace(tzinfo=_LOCAL_ZONE).isoformat(timespec="seconds")
        # Fallback: attach current UTC offset (not DST-safe, but always works)
        return dt.astimezone().isoformat(timespec="seconds")
    except ValueError:
        return None


def _mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).astimezone().isoformat(
        timespec="seconds"
    )


# ── Store helpers ─────────────────────────────────────────────────────────────

def _scan_existing_shas(directory: Path) -> set[str]:
    shas: set[str] = set()
    for md in directory.rglob("*.md"):
        try:
            post = frontmatter.load(md)
            sha = post.metadata.get("sha256")
            if isinstance(sha, str):
                shas.add(sha)
        except Exception:  # noqa: BLE001
            continue
    return shas


def _slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s or "scan"


def _unique_path(directory: Path, date_prefix: str, slug: str) -> Path:
    candidate = directory / f"{date_prefix}_{slug}.md"
    i = 1
    while candidate.exists():
        candidate = directory / f"{date_prefix}_{slug}_{i}.md"
        i += 1
    return candidate
