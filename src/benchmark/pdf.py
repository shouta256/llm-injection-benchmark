from __future__ import annotations

import textwrap
from pathlib import Path


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_simple_pdf(path: Path, lines: list[str]) -> None:
    pages = _paginate_lines(lines)
    font_object_id = 1
    content_object_ids = [font_object_id + index + 1 for index in range(len(pages))]
    page_object_ids = [
        content_object_ids[-1] + index + 1
        for index in range(len(pages))
    ]
    pages_object_id = page_object_ids[-1] + 1 if page_object_ids else 2
    catalog_object_id = pages_object_id + 1

    objects = [b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    objects.extend(_content_stream_object(page_lines) for page_lines in pages)
    objects.extend(
        _page_object(content_object_id, pages_object_id, font_object_id)
        for content_object_id in content_object_ids
    )
    objects.append(_pages_object(page_object_ids))
    objects.append(f"<< /Type /Catalog /Pages {pages_object_id} 0 R >>".encode("latin-1"))

    pdf = _assemble_pdf(objects, catalog_object_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pdf)


def _paginate_lines(lines: list[str]) -> list[list[str]]:
    wrapped_lines: list[str] = []
    for line in lines:
        normalized = line.rstrip()
        if not normalized:
            wrapped_lines.append("")
            continue
        wrapped_lines.extend(textwrap.wrap(normalized, width=92) or [""])

    if not wrapped_lines:
        wrapped_lines = ["Empty report."]

    lines_per_page = 46
    return [
        wrapped_lines[index : index + lines_per_page]
        for index in range(0, len(wrapped_lines), lines_per_page)
    ]


def _content_stream_object(page_lines: list[str]) -> bytes:
    text_lines = ["BT", "/F1 11 Tf", "50 760 Td", "14 TL"]
    for index, line in enumerate(page_lines):
        if index:
            text_lines.append("T*")
        text_lines.append(f"({_escape_pdf_text(line)}) Tj")
    text_lines.append("ET")
    stream = "\n".join(text_lines).encode("latin-1", errors="replace")
    return f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream"


def _page_object(content_object_id: int, pages_object_id: int, font_object_id: int) -> bytes:
    return (
        f"<< /Type /Page /Parent {pages_object_id} 0 R /MediaBox [0 0 612 792] "
        f"/Resources << /Font << /F1 {font_object_id} 0 R >> >> "
        f"/Contents {content_object_id} 0 R >>"
    ).encode("latin-1")


def _pages_object(page_object_ids: list[int]) -> bytes:
    kids = " ".join(f"{page_object_id} 0 R" for page_object_id in page_object_ids)
    return f"<< /Type /Pages /Count {len(page_object_ids)} /Kids [ {kids} ] >>".encode("latin-1")


def _assemble_pdf(objects: list[bytes], catalog_object_id: int) -> bytes:
    xref_offsets = [0]
    pdf = bytearray(b"%PDF-1.4\n")
    for object_number, payload in enumerate(objects, start=1):
        xref_offsets.append(len(pdf))
        pdf.extend(f"{object_number} 0 obj\n".encode("latin-1"))
        pdf.extend(payload)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in xref_offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_object_id} 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "latin-1"
        )
    )
    return bytes(pdf)
