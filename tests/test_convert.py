"""Tests for zkm-scan convert.py.

All tests mock pytesseract.image_to_string and pdf2image.convert_from_path
so the test suite runs without system tesseract or poppler installed.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import frontmatter
import pytest
from PIL import Image

from convert import PLUGIN_NAME, PLUGIN_VERSION, convert

from conftest import make_store


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def store(tmp_path: Path) -> Path:
    return make_store(tmp_path)


@pytest.fixture
def src(tmp_path: Path) -> Path:
    d = tmp_path / "scan_src"
    d.mkdir()
    return d


def cfg(src_dir: Path | None = None, lang: str = "deu+eng", min_chars: int = 10) -> dict:
    return {
        "SCAN_SOURCE_DIR": str(src_dir) if src_dir else "",
        "SCAN_LANG": lang,
        "SCAN_MIN_TEXT_CHARS": str(min_chars),
    }


def make_jpeg(path: Path, content: bytes | None = None) -> Path:
    """Write a minimal JPEG to path (or content bytes if provided)."""
    if content is not None:
        path.write_bytes(content)
        return path
    img = Image.new("RGB", (64, 64), color=(128, 128, 128))
    img.save(path, format="JPEG")
    return path


def make_png(path: Path) -> Path:
    img = Image.new("RGB", (32, 32), color=(200, 100, 50))
    img.save(path, format="PNG")
    return path


def make_inbox_item(
    store: Path,
    filename: str,
    plugin: str = "eml",
) -> tuple[Path, Path]:
    """Create a JPEG CAS object + inbox symlink + .origin.json sidecar."""
    cas_dir = store / "originals" / "scans" / "_objects" / "ab"
    cas_dir.mkdir(parents=True, exist_ok=True)
    cas_obj = cas_dir / filename
    make_jpeg(cas_obj)

    inbox_dir = store / "inbox" / "emails"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    link = inbox_dir / filename
    link.symlink_to(cas_obj)

    sha = "ab" * 32  # fake sha256
    sidecar = cas_obj.with_name(cas_obj.name + ".json")
    sidecar.write_text(
        json.dumps({
            "schema": 1,
            "sha256": sha,
            "producers": [{"plugin": plugin, "message": "mail/msg.md", "sha256": sha}],
        })
    )
    return cas_obj, sidecar


# ── 1. Happy path ─────────────────────────────────────────────────────────────

def test_convert_creates_md_with_correct_frontmatter(store, src):
    make_jpeg(src / "receipt.jpg")
    with patch("convert.pytesseract.image_to_string", return_value="Invoice total 42 EUR"):
        created = convert(store, cfg(src))
    assert len(created) == 1
    md = created[0]
    assert md.exists()
    assert md.parts[-4] == "scans"
    post = frontmatter.load(md)
    assert post.metadata["source"] == PLUGIN_NAME
    assert post.metadata["processor"] == PLUGIN_NAME
    assert post.metadata["processor_version"] == PLUGIN_VERSION
    assert post.metadata["tags"] == []
    assert isinstance(post.metadata["sha256"], str) and len(post.metadata["sha256"]) == 64
    assert post.metadata["original"].startswith("originals/scans/_objects/")
    assert post.metadata["ocr_chars"] > 0
    assert "[original image](" in post.content
    assert "Invoice total 42 EUR" in post.content


# ── 2. Idempotency ────────────────────────────────────────────────────────────

def test_convert_idempotent(store, src):
    make_jpeg(src / "receipt.jpg")
    with patch("convert.pytesseract.image_to_string", return_value="Some scanned text here"):
        first = convert(store, cfg(src))
        assert len(first) == 1
        second = convert(store, cfg(src))
        assert second == []


# ── 3. SHA-256 dedup ──────────────────────────────────────────────────────────

def test_convert_dedup_by_sha256(store, src):
    """Two copies of the same file produce only one md."""
    img = Image.new("RGB", (64, 64), color=(10, 20, 30))
    img.save(src / "copy_a.jpg", format="JPEG")
    img.save(src / "copy_b.jpg", format="JPEG")
    with patch("convert.pytesseract.image_to_string", return_value="Duplicate scan content"):
        created = convert(store, cfg(src))
    assert len(created) == 1


# ── 4. Progress callback ──────────────────────────────────────────────────────

def test_progress_called_for_each_item(store, src):
    make_jpeg(src / "a.jpg")
    make_jpeg(src / "b.jpg")
    make_png(src / "c.png")
    calls: list[tuple] = []
    with patch("convert.pytesseract.image_to_string", return_value="text content here"):
        convert(store, cfg(src), progress=lambda c, t, m: calls.append((c, t, m)))
    assert len(calls) == 3
    totals = {t for _, t, _ in calls}
    assert totals == {3}


# ── 5. Unowned inbox items skipped ───────────────────────────────────────────

def test_unowned_inbox_items_noop(store):
    """Inbox item with an unknown producer plugin → [] (no-op contract)."""
    make_inbox_item(store, "foreign.jpg", plugin="unknown-plugin")
    with patch("convert.pytesseract.image_to_string", return_value="some text"):
        created = convert(store, cfg())
    assert created == []


# ── 6. Below-min-chars threshold → skip ──────────────────────────────────────

def test_below_min_chars_skipped(store, src):
    make_jpeg(src / "blank.jpg")
    with patch("convert.pytesseract.image_to_string", return_value=""):
        created = convert(store, cfg(src, min_chars=10))
    assert created == []
    # No scans/ md written
    md_files = list((store / "scans").rglob("*.md"))
    assert md_files == []


# ── 7. PDF input → per-doc md with page markers ───────────────────────────────

def test_pdf_input_creates_per_doc_md(store, src):
    """A 2-page PDF → one md with <!-- page N --> markers."""
    pdf_path = src / "scan.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")  # content doesn't matter; pdf2image is mocked
    page_imgs = [Image.new("RGB", (64, 64)), Image.new("RGB", (64, 64))]
    with (
        patch("convert._pdf_to_pil_images", return_value=page_imgs),
        patch("convert.pytesseract.image_to_string", side_effect=["Page one text", "Page two text"]),
    ):
        created = convert(store, cfg(src))
    assert len(created) == 1
    post = frontmatter.load(created[0])
    assert "<!-- page 1 -->" in post.content
    assert "<!-- page 2 -->" in post.content
    assert "Page one text" in post.content
    assert "Page two text" in post.content
    assert "[original PDF](" in post.content


# ── 8. Cancellation: PluginInterrupt mid-run ─────────────────────────────────

def test_cancellation_interrupt_mid_run(store, src):
    """PluginInterrupt after first item: partial results returned, no crash."""
    make_jpeg(src / "a.jpg")
    make_jpeg(src / "b.jpg")
    call_count = 0

    def progress_interrupt(_c, _t, _m):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise KeyboardInterrupt

    with patch("convert.pytesseract.image_to_string", return_value="Some scanned text here"):
        with pytest.raises(KeyboardInterrupt):
            convert(store, cfg(src), progress=progress_interrupt)

    # First item was processed before interrupt fired on item 2
    md_files = list((store / "scans").rglob("*.md"))
    assert len(md_files) == 1


# ── 9. SCAN_SOURCE_DIR: CAS + inbox symlink created ──────────────────────────

def test_scan_source_dir_creates_cas_and_inbox_symlink(store, src):
    make_jpeg(src / "doc.jpg")
    with patch("convert.pytesseract.image_to_string", return_value="Scanned document text"):
        convert(store, cfg(src))

    cas_files = list((store / "originals" / "scans" / "_objects").rglob("*"))
    assert any(f.is_file() and not f.name.endswith(".json") for f in cas_files)

    inbox_links = list((store / "inbox" / "scans").rglob("*"))
    assert any(lnk.is_symlink() for lnk in inbox_links)


# ── 10. Nonexistent SCAN_SOURCE_DIR raises ───────────────────────────────────

def test_scan_source_dir_nonexistent_raises(store):
    with pytest.raises(FileNotFoundError):
        convert(store, cfg(src_dir=Path("/nonexistent/path/zkm-scan-test")))


# ── 11. Owned inbox image is processed ───────────────────────────────────────

def test_owned_inbox_image_processed(store):
    """An eml-owned JPEG in inbox/ is OCR'd and produces a scans/ md."""
    make_inbox_item(store, "attachment.jpg", plugin="eml")
    with patch("convert.pytesseract.image_to_string", return_value="Invoice for services rendered"):
        created = convert(store, cfg())
    assert len(created) == 1
    post = frontmatter.load(created[0])
    assert post.metadata["source"] == PLUGIN_NAME
    assert "Invoice for services rendered" in post.content


# ── 12. photo-owned inbox image is processed ─────────────────────────────────

def test_photo_owned_inbox_image_processed(store):
    """A photo-owned JPEG in inbox/ is OCR'd (whiteboard photo, receipt photo, etc.)."""
    make_inbox_item(store, "photo_receipt.jpg", plugin="photo")
    with patch("convert.pytesseract.image_to_string", return_value="Total: CHF 18.50"):
        created = convert(store, cfg())
    assert len(created) == 1


# ── 13. SCAN_LANG forwarded to pytesseract ───────────────────────────────────

def test_scan_lang_passed_to_pytesseract(store, src):
    make_jpeg(src / "doc.jpg")
    calls: list[dict] = []

    def capture(_img, lang):
        calls.append({"lang": lang})
        return "Captured lang test text"

    with patch("convert.pytesseract.image_to_string", side_effect=capture):
        convert(store, cfg(src, lang="fra+deu"))

    assert calls
    assert all(c["lang"] == "fra+deu" for c in calls)
