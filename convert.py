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

import os
import re
from datetime import UTC, datetime
from pathlib import Path

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
PLUGIN_VERSION = "0.1.0"

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".gif", ".webp"}
_SCAN_EXTS = _IMAGE_EXTS | {".pdf"}
_KNOWN_UPSTREAM_PLUGINS = {"eml", "photo", "scan"}


def convert(store_path: Path, config: dict, *, progress=None) -> list[Path]:
    """OCR images and scanned PDFs from inbox/ and optional SCAN_SOURCE_DIR.

    Returns a list of paths to newly created .md files.
    progress: optional callback(current, total, message). May raise PluginInterrupt.
    """
    lang = str(config.get("lang", "deu+eng") or "deu+eng")
    min_chars = int(config.get("min_text_chars", 10))
    src_dir_raw = str(config.get("source_dir", "") or "")

    for subdir in ["scans", "originals/scans", "inbox/scans"]:
        (store_path / subdir).mkdir(parents=True, exist_ok=True)

    existing_shas = _scan_existing_shas(store_path / "scans")
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
        md = _emit_md(
            store_path=store_path,
            src_path=real_path,
            sha=sha,
            cas_path=real_path,
            cas_sidecar=cas_sidecar,
            lang=lang,
            min_chars=min_chars,
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
            sha = sha256_file(src_file)
            if sha in existing_shas:
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
    preextracted_text: str | None = None,
) -> Path | None:
    """OCR src_path, write md, update CAS sidecar. Returns md path or None on skip."""
    text = preextracted_text if preextracted_text is not None else _ocr_file(src_path, lang)

    if len(text) < min_chars:
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

    body = f"[original {file_type}]({rel_link})\n\n{text}\n"
    write_atomic(out, frontmatter.dumps(frontmatter.Post(body, **fm)))

    merge_producer(
        cas_sidecar,
        sha256=sha,
        producer={"plugin": PLUGIN_NAME, "message": str(out.relative_to(store_path)), "sha256": sha},
    )

    return out


# ── OCR helpers ───────────────────────────────────────────────────────────────

def _ocr_file(path: Path, lang: str) -> str:
    """OCR a file (image or PDF) and return the combined text."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _ocr_pdf(path, lang)
    return _ocr_image(Image.open(path), lang)


def _ocr_image(img: Image.Image, lang: str) -> str:
    """Run tesseract on a single PIL Image."""
    return pytesseract.image_to_string(img, lang=lang).strip()


def _ocr_pdf(path: Path, lang: str) -> str:
    """Convert a PDF to images page-by-page and OCR each page."""
    pages = _pdf_to_pil_images(str(path))
    parts: list[str] = []
    for i, page_img in enumerate(pages, 1):
        text = _ocr_image(page_img, lang).strip()
        if text:
            parts.append(f"<!-- page {i} -->\n\n{text}")
    return "\n\n".join(parts)


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
    """Extract DateTimeOriginal from JPEG/TIFF EXIF, return ISO 8601 or None."""
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


def _exif_str_to_iso(s: str) -> str | None:
    """Convert EXIF datetime string 'YYYY:MM:DD HH:MM:SS' to ISO 8601."""
    try:
        dt = datetime.strptime(s, "%Y:%m:%d %H:%M:%S")
        return dt.isoformat(timespec="seconds")
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
