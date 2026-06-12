"""Executable spec for ROADMAP.md items — each test carries a `# roadmap:XXXX`
comment mapping it to its item.

These tests are SUPPOSED to be RED until their item is implemented; do not
delete, skip, or weaken them to get a green suite. Two tests are green-by-design
guards and are marked as such (they pin behavior that must NOT change while the
item is implemented).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import frontmatter
import pytest
from PIL import Image

from conftest import (
    cfg,
    make_inbox_item,
    make_jpeg,
    make_store,
    make_text_pdf,
    read_skip_log,
)
from zkm_scan.convert import convert

OCR = "zkm_scan.convert.pytesseract.image_to_string"
OCR_DATA = "zkm_scan.convert.pytesseract.image_to_data"
GET_LANGS = "zkm_scan.convert.pytesseract.get_languages"
PDF2IMG = "zkm_scan.convert._pdf_to_pil_images"

LONG_TEXT = "This is a regular text PDF with a real extractable text layer. " * 4


@pytest.fixture
def store(tmp_path: Path) -> Path:
    return make_store(tmp_path)


@pytest.fixture
def src(tmp_path: Path) -> Path:
    d = tmp_path / "scan_src"
    d.mkdir()
    return d


# ═══ id:6913 — honor the zkm-pdf routing contract ═════════════════════════════

def test_6913_pdf_producer_sidecar_skipped(store):  # roadmap:6913
    """Inbox PDF already claimed by zkm-pdf (sidecar `pdf` producer) → no OCR md."""
    sha = "ab" * 32
    make_inbox_item(
        store,
        "letter.pdf",
        producers=[
            {"plugin": "eml", "message": "mail/msg.md", "sha256": sha},
            {"plugin": "pdf", "message": "pdfs/2026/06/letter.md", "sha256": sha},
        ],
        content=b"%PDF-1.4 fake scanned payload",
    )
    with (
        patch(PDF2IMG, return_value=[Image.new("RGB", (64, 64))]),
        patch(OCR, return_value="OCR text that is long enough to pass the floor"),
    ):
        created = convert(store, cfg())
    assert created == []


def test_6913_text_layer_pdf_skipped_and_logged(store, src):  # roadmap:6913
    """source_dir PDF with a real text layer (≥ pdf_text_threshold chars) is
    left for zkm-pdf: no md, no CAS object, one skip-log entry reason=text-layer."""
    make_text_pdf(src / "report.pdf", LONG_TEXT)
    with (
        patch(PDF2IMG, return_value=[Image.new("RGB", (64, 64))]),
        patch(OCR, return_value="OCR text that is long enough to pass the floor"),
    ):
        created = convert(store, cfg(src))
    assert created == []
    # skips leave no traces in the store (mirrors zkm-pdf's probe-before-write)
    cas_files = [
        f for f in (store / "originals" / "scans" / "_objects").rglob("*")
        if f.is_file() and not f.name.endswith(".json")
    ]
    assert cas_files == []
    entries = [e for e in read_skip_log(store) if e.get("reason") == "text-layer"]
    assert len(entries) == 1
    assert entries[0]["text_chars"] >= 100
    assert entries[0]["sha256"]


def test_6913_scanned_pdf_still_processed(store, src):  # roadmap:6913
    """GUARD (green by design): a PDF without an extractable text layer must
    keep being OCR'd — do not over-skip while implementing the probe."""
    (src / "scan.pdf").write_bytes(b"%PDF-1.4 fake scanned payload, no text layer")
    with (
        patch(PDF2IMG, return_value=[Image.new("RGB", (64, 64))]),
        patch(OCR, return_value="Scanned page text from tesseract"),
    ):
        created = convert(store, cfg(src))
    assert len(created) == 1


# ═══ id:8810 — below-threshold skip ledger (no re-OCR) ════════════════════════

def test_8810_below_threshold_not_reocred(store, src):  # roadmap:8810
    """Second run with unchanged threshold must not re-OCR a known-blank file."""
    make_jpeg(src / "blank.jpg")
    with patch(OCR, return_value="") as first_ocr:
        assert convert(store, cfg(src)) == []
    assert first_ocr.called  # first run did the (expensive) OCR

    with patch(OCR, return_value="") as second_ocr:
        assert convert(store, cfg(src)) == []
    assert not second_ocr.called  # ledger hit — no re-OCR


def test_8810_skip_logged_with_reason(store, src):  # roadmap:8810
    make_jpeg(src / "blank.jpg")
    with patch(OCR, return_value="x"):  # 1 char < min_text_chars=10
        convert(store, cfg(src))
    entries = [e for e in read_skip_log(store) if e.get("reason") == "below-min-chars"]
    assert len(entries) == 1
    assert entries[0]["ocr_chars"] == 1
    assert entries[0]["threshold"] == 10
    assert entries[0]["sha256"]


# ═══ id:5c02 — graceful missing-language-pack error ═══════════════════════════

def test_5c02_missing_language_pack_clear_error(store, src):  # roadmap:5c02
    """Configured lang pack not installed → ValueError naming the missing pack."""
    make_jpeg(src / "doc.jpg")
    with (
        patch(GET_LANGS, return_value=["eng", "osd"]),
        patch(OCR, return_value="text that would otherwise be emitted"),
    ):
        with pytest.raises(ValueError, match="deu"):
            convert(store, cfg(src, lang="deu+eng"))


def test_5c02_get_languages_unavailable_falls_through(store, src):  # roadmap:5c02
    """GUARD (green by design): if get_languages itself fails (tesseract absent
    or too old), the pre-check is skipped — never a new failure mode."""
    make_jpeg(src / "doc.jpg")
    with (
        patch(GET_LANGS, side_effect=RuntimeError("tesseract not found")),
        patch(OCR, return_value="text long enough to emit"),
    ):
        created = convert(store, cfg(src, lang="deu+eng"))
    assert len(created) == 1


# ═══ id:c199 — configurable DPI for PDF rasterization ═════════════════════════

def test_c199_default_dpi_300(store, src):  # roadmap:c199
    (src / "scan.pdf").write_bytes(b"%PDF-1.4 fake scanned payload")
    with (
        patch(PDF2IMG, return_value=[Image.new("RGB", (64, 64))]) as p2i,
        patch(OCR, return_value="Scanned page text from tesseract"),
    ):
        convert(store, cfg(src))
    assert p2i.called
    assert p2i.call_args.kwargs.get("dpi") == 300


def test_c199_configured_dpi_forwarded(store, src):  # roadmap:c199
    (src / "scan.pdf").write_bytes(b"%PDF-1.4 fake scanned payload")
    with (
        patch(PDF2IMG, return_value=[Image.new("RGB", (64, 64))]) as p2i,
        patch(OCR, return_value="Scanned page text from tesseract"),
    ):
        convert(store, cfg(src, dpi="150"))
    assert p2i.called
    assert p2i.call_args.kwargs.get("dpi") == 150


# ═══ id:5d7d — OCR confidence in frontmatter (observe-only) ═══════════════════

def test_5d7d_ocr_confidence_in_frontmatter(store, src):  # roadmap:5d7d
    """ocr_confidence = mean of word confidences ≥ 0, rounded to 1 decimal."""
    make_jpeg(src / "receipt.jpg")
    data = {
        # pytesseract dict output: conf as strings, -1 for non-word boxes
        "conf": ["90", "80", "-1", "70"],
        "text": ["Invoice", "total", "", "42"],
    }
    with (
        patch(OCR, return_value="Invoice total 42 EUR"),
        patch(OCR_DATA, return_value=data),
    ):
        created = convert(store, cfg(src))
    assert len(created) == 1
    post = frontmatter.load(created[0])
    assert post.metadata["ocr_confidence"] == 80.0  # (90+80+70)/3


# ═══ id:f7d3 — HEIC/HEIF support via optional pillow-heif ═════════════════════

def test_f7d3_heic_without_pillow_heif_logs_notice(store, src, monkeypatch):  # roadmap:f7d3
    """pillow-heif unavailable → .heic candidates logged, not silently invisible."""
    monkeypatch.setitem(sys.modules, "pillow_heif", None)  # forces ImportError
    (src / "photo.heic").write_bytes(b"\x00\x00\x00\x18ftypheic fake")
    with patch(OCR, return_value="text long enough to emit"):
        created = convert(store, cfg(src))
    assert created == []
    entries = [e for e in read_skip_log(store) if e.get("reason") == "heic-unsupported"]
    assert len(entries) == 1
    assert entries[0]["path"].endswith("photo.heic")


def test_f7d3_heic_processed_when_supported(store, src):  # roadmap:f7d3
    """With pillow-heif installed, .heic files are OCR'd like any image."""
    pillow_heif = pytest.importorskip("pillow_heif")
    pillow_heif.register_heif_opener()
    img = Image.new("RGB", (64, 64), color=(120, 130, 140))
    img.save(src / "photo.heic", format="HEIF")
    with patch(OCR, return_value="text long enough to emit"):
        created = convert(store, cfg(src))
    assert len(created) == 1


# ═══ id:aae8 — frontmatter conformance: tz-aware EXIF date + pages ════════════

def test_aae8_exif_date_is_tz_aware_and_conformant(store, src):  # roadmap:aae8
    """EXIF-dated docs must carry a tz-aware date and pass core conformance."""
    from zkm.conformance import validate_frontmatter

    img = Image.new("RGB", (64, 64), color=(50, 60, 70))
    exif = Image.Exif()
    exif[36867] = "2024:03:05 14:30:00"  # DateTimeOriginal
    img.save(src / "photo.jpg", format="JPEG", exif=exif)

    with patch(OCR, return_value="Receipt text from a photographed document"):
        created = convert(store, cfg(src))
    assert len(created) == 1
    post = frontmatter.load(created[0])
    date_str = str(post.metadata["date"])
    assert date_str.startswith("2024-03-05T14:30:00")  # EXIF date was used
    findings = validate_frontmatter(dict(post.metadata), "scan")
    assert findings == []  # in particular: no "date has no timezone"


def test_aae8_pdf_frontmatter_has_pages(store, src):  # roadmap:aae8
    """PDF-sourced mds carry pages: <total page count> (parity with zkm-pdf)."""
    (src / "scan.pdf").write_bytes(b"%PDF-1.4 fake scanned payload")
    page_imgs = [Image.new("RGB", (64, 64)), Image.new("RGB", (64, 64))]
    with (
        patch(PDF2IMG, return_value=page_imgs),
        patch(OCR, side_effect=["Page one text", "Page two text"]),
    ):
        created = convert(store, cfg(src))
    assert len(created) == 1
    post = frontmatter.load(created[0])
    assert post.metadata["pages"] == 2
