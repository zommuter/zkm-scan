"""Shared fixtures/helpers for the zkm-scan test suite.

All unit tests mock the OCR seams (`zkm_scan.convert.pytesseract.*`,
`zkm_scan.convert._pdf_to_pil_images`) so the suite runs without system
tesseract or poppler. Integration tests (test_integration_ocr.py) use the real
binaries and skip themselves when those are missing.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image


def make_store(tmp_path: Path) -> Path:
    s = tmp_path / "store"
    (s / "scans").mkdir(parents=True)
    (s / "inbox").mkdir()
    (s / "originals" / "scans").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(s)], check=True)
    return s


def cfg(
    src_dir: Path | None = None,
    lang: str = "deu+eng",
    min_chars: int = 10,
    **extra,
) -> dict:
    """Plugin config dict with bare snake_case keys (M2 convention)."""
    config = {
        "source_dir": str(src_dir) if src_dir else "",
        "lang": lang,
        "min_text_chars": str(min_chars),
    }
    config.update(extra)
    return config


def make_jpeg(path: Path, content: bytes | None = None) -> Path:
    """Write a minimal JPEG to path (or raw content bytes if provided)."""
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
    producers: list[dict] | None = None,
    content: bytes | None = None,
) -> tuple[Path, Path]:
    """Create a CAS object + inbox symlink + .json sidecar.

    By default the object is a tiny real JPEG with a single `plugin` producer;
    pass `producers` for a custom producer list and `content` for raw bytes
    (e.g. fake PDF payloads).
    """
    cas_dir = store / "originals" / "scans" / "_objects" / "ab"
    cas_dir.mkdir(parents=True, exist_ok=True)
    cas_obj = cas_dir / filename
    make_jpeg(cas_obj, content=content)

    inbox_dir = store / "inbox" / "emails"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    link = inbox_dir / filename
    link.symlink_to(cas_obj)

    sha = "ab" * 32  # fake sha256
    if producers is None:
        producers = [{"plugin": plugin, "message": "mail/msg.md", "sha256": sha}]
    sidecar = cas_obj.with_name(cas_obj.name + ".json")
    sidecar.write_text(
        json.dumps({"schema": 1, "sha256": sha, "producers": producers})
    )
    return cas_obj, sidecar


def make_text_pdf(path: Path, text: str) -> Path:
    """Write a minimal single-page PDF with a real, pypdf-extractable text layer.

    Used to simulate a *text* PDF (zkm-pdf territory) as opposed to a
    scanned-only one. Offsets are computed at runtime so the xref is valid.
    """
    # Escape PDF string delimiters
    esc = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    stream = f"BT /F1 12 Tf 50 700 Td ({esc}) Tj ET".encode("latin-1", "replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream
        + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode()
    path.write_bytes(bytes(out))
    return path


def read_skip_log(store: Path) -> list[dict]:
    """Parse <store>/.zkm-state/zkm-scan-skipped.jsonl (empty list if absent)."""
    log = store / ".zkm-state" / "zkm-scan-skipped.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
