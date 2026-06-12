"""Integration tests: real tesseract + poppler, no mocks.

Skipped with a clear marker when the system binaries (or the `eng` language
pack) are missing. Assertions are deliberately loose (substring on large-font
rendered text) — exact OCR output is environment-sensitive.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from conftest import cfg, make_store

requires_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None,
    reason="system tesseract not installed",
)
requires_poppler = pytest.mark.skipif(
    shutil.which("pdftoppm") is None,
    reason="system poppler (pdftoppm) not installed",
)


def _require_eng_pack() -> None:
    import pytesseract

    try:
        langs = pytesseract.get_languages()
    except Exception:  # noqa: BLE001
        pytest.skip("tesseract language list unavailable")
    if "eng" not in langs:
        pytest.skip("tesseract 'eng' language pack not installed")


def _text_image(size=(800, 200), text="HELLO WORLD 12345") -> Image.Image:
    img = Image.new("RGB", size, color="white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=64)
    except TypeError:  # Pillow < 10.1
        font = ImageFont.load_default()
    draw.text((40, 60), text, fill="black", font=font)
    return img


@pytest.fixture
def store(tmp_path: Path) -> Path:
    return make_store(tmp_path)


@pytest.fixture
def src(tmp_path: Path) -> Path:
    d = tmp_path / "scan_src"
    d.mkdir()
    return d


@requires_tesseract
def test_real_ocr_image_end_to_end(store, src):
    from zkm_scan.convert import convert

    _require_eng_pack()
    _text_image().save(src / "hello.png")
    created = convert(store, cfg(src, lang="eng"))
    assert len(created) == 1
    body = created[0].read_text()
    assert "HELLO" in body.upper()


@requires_tesseract
@requires_poppler
def test_real_ocr_scanned_pdf_end_to_end(store, src):
    """Image-only PDF (no text layer) → rasterized by poppler, OCR'd by tesseract."""
    from zkm_scan.convert import convert

    _require_eng_pack()
    _text_image(text="SCANNED PAGE 99").save(src / "scan.pdf", format="PDF")
    created = convert(store, cfg(src, lang="eng"))
    assert len(created) == 1
    body = created[0].read_text()
    assert "SCANNED" in body.upper()
