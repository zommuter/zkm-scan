"""Tests for zkm_scan.convert.

All tests mock pytesseract.image_to_string and pdf2image.convert_from_path
(at the `zkm_scan.convert.*` seams — NOT the root `convert` shim) so the suite
runs without system tesseract or poppler installed.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import frontmatter
import pytest
from PIL import Image

from conftest import cfg, make_inbox_item, make_jpeg, make_png, make_store
from zkm_scan.convert import PLUGIN_NAME, PLUGIN_VERSION, convert

OCR = "zkm_scan.convert.pytesseract.image_to_string"
PDF2IMG = "zkm_scan.convert._pdf_to_pil_images"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def store(tmp_path: Path) -> Path:
    return make_store(tmp_path)


@pytest.fixture
def src(tmp_path: Path) -> Path:
    d = tmp_path / "scan_src"
    d.mkdir()
    return d


# ── 1. Happy path ─────────────────────────────────────────────────────────────

def test_convert_creates_md_with_correct_frontmatter(store, src):
    make_jpeg(src / "receipt.jpg")
    with patch(OCR, return_value="Invoice total 42 EUR"):
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
    with patch(OCR, return_value="Some scanned text here"):
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
    with patch(OCR, return_value="Duplicate scan content"):
        created = convert(store, cfg(src))
    assert len(created) == 1


# ── 4. Progress callback ──────────────────────────────────────────────────────

def test_progress_called_for_each_item(store, src):
    make_jpeg(src / "a.jpg")
    make_jpeg(src / "b.jpg")
    make_png(src / "c.png")
    calls: list[tuple] = []
    with patch(OCR, return_value="text content here"):
        convert(store, cfg(src), progress=lambda c, t, m: calls.append((c, t, m)))
    assert len(calls) == 3
    totals = {t for _, t, _ in calls}
    assert totals == {3}


# ── 5. Unowned inbox items skipped ───────────────────────────────────────────

def test_unowned_inbox_items_noop(store):
    """Inbox item with an unknown producer plugin → [] (no-op contract)."""
    make_inbox_item(store, "foreign.jpg", plugin="unknown-plugin")
    with patch(OCR, return_value="some text"):
        created = convert(store, cfg())
    assert created == []


# ── 6. Below-min-chars threshold → skip ──────────────────────────────────────

def test_below_min_chars_skipped(store, src):
    make_jpeg(src / "blank.jpg")
    with patch(OCR, return_value=""):
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
        patch(PDF2IMG, return_value=page_imgs),
        patch(OCR, side_effect=["Page one text", "Page two text"]),
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

    with patch(OCR, return_value="Some scanned text here"):
        with pytest.raises(KeyboardInterrupt):
            convert(store, cfg(src), progress=progress_interrupt)

    # First item was processed before interrupt fired on item 2
    md_files = list((store / "scans").rglob("*.md"))
    assert len(md_files) == 1


# ── 9. source_dir: CAS + inbox symlink created ───────────────────────────────

def test_scan_source_dir_creates_cas_and_inbox_symlink(store, src):
    make_jpeg(src / "doc.jpg")
    with patch(OCR, return_value="Scanned document text"):
        convert(store, cfg(src))

    cas_files = list((store / "originals" / "scans" / "_objects").rglob("*"))
    assert any(f.is_file() and not f.name.endswith(".json") for f in cas_files)

    inbox_links = list((store / "inbox" / "scans").rglob("*"))
    assert any(lnk.is_symlink() for lnk in inbox_links)


# ── 10. Nonexistent source_dir raises ────────────────────────────────────────

def test_scan_source_dir_nonexistent_raises(store):
    with pytest.raises(FileNotFoundError):
        convert(store, cfg(src_dir=Path("/nonexistent/path/zkm-scan-test")))


# ── 11. Owned inbox image is processed ───────────────────────────────────────

def test_owned_inbox_image_processed(store):
    """An eml-owned JPEG in inbox/ is OCR'd and produces a scans/ md."""
    make_inbox_item(store, "attachment.jpg", plugin="eml")
    with patch(OCR, return_value="Invoice for services rendered"):
        created = convert(store, cfg())
    assert len(created) == 1
    post = frontmatter.load(created[0])
    assert post.metadata["source"] == PLUGIN_NAME
    assert "Invoice for services rendered" in post.content


# ── 12. photo-owned inbox image is processed ─────────────────────────────────

def test_photo_owned_inbox_image_processed(store):
    """A photo-owned JPEG in inbox/ is OCR'd (whiteboard photo, receipt photo, etc.)."""
    make_inbox_item(store, "photo_receipt.jpg", plugin="photo")
    with patch(OCR, return_value="Total: CHF 18.50"):
        created = convert(store, cfg())
    assert len(created) == 1


# ── 13. lang config forwarded to pytesseract ─────────────────────────────────

def test_scan_lang_passed_to_pytesseract(store, src):
    make_jpeg(src / "doc.jpg")
    calls: list[dict] = []

    def capture(_img, lang):
        calls.append({"lang": lang})
        return "Captured lang test text"

    GET_LANGS = "zkm_scan.convert.pytesseract.get_languages"
    with (
        patch(GET_LANGS, return_value=["fra", "deu", "eng", "osd"]),
        patch(OCR, side_effect=capture),
    ):
        convert(store, cfg(src, lang="fra+deu"))

    assert calls
    assert all(c["lang"] == "fra+deu" for c in calls)


# ── 14. Root shim re-exports the package implementation ──────────────────────

def test_root_shim_reexports_package_convert():
    """Filesystem discovery loads root convert.py — it must be the same function."""
    import importlib.util

    shim_path = Path(__file__).parent.parent / "convert.py"
    spec = importlib.util.spec_from_file_location("zkm_scan_root_shim", shim_path)
    shim = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shim)
    assert shim.convert is convert


# ── 15. plugin.yaml copies stay in sync ──────────────────────────────────────

def test_plugin_yaml_copies_identical():
    """Root plugin.yaml (filesystem discovery) == src/zkm_scan/plugin.yaml (wheel)."""
    repo = Path(__file__).parent.parent
    root_copy = (repo / "plugin.yaml").read_bytes()
    pkg_copy = (repo / "src" / "zkm_scan" / "plugin.yaml").read_bytes()
    assert root_copy == pkg_copy
