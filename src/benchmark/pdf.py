from __future__ import annotations

import textwrap
from pathlib import Path


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_simple_pdf(path: Path, lines: list[str]) -> None:
    wrapped_lines: list[str] = []
    for line in lines:
        normalized = line.rstrip()
        if not normalized:
            wrapped_lines.append("")
            continue
        wrapped_lines.extend(textwrap.wrap(normalized, width=92) or [""])

    lines_per_page = 46
    pages = [
        wrapped_lines[index : index + lines_per_page]
        for index in range(0, len(wrapped_lines), lines_per_page)
    ]
    if not pages:
        pages = [["Empty report."]]

    objects: list[bytes] = []

    def add_object(data: bytes) -> int:
        objects.append(data)
        return len(objects)

    font_object_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_object_ids: list[int] = []
    content_object_ids: list[int] = []

    for page_lines in pages:
        text_lines = ["BT", "/F1 11 Tf", "50 760 Td", "14 TL"]
        for index, line in enumerate(page_lines):
            escaped = _escape_pdf_text(line)
            if index == 0:
                text_lines.append(f"({escaped}) Tj")
            else:
                text_lines.append("T*")
                text_lines.append(f"({escaped}) Tj")
        text_lines.append("ET")
        stream = "\n".join(text_lines).encode("latin-1", errors="replace")
        content_object_id = add_object(
            f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream"
        )
        content_object_ids.append(content_object_id)
        page_object_ids.append(0)

    pages_kids_placeholder = " ".join(f"{index} 0 R" for index in range(1, len(pages) + 1))
    pages_object_id = add_object(
        f"<< /Type /Pages /Count {len(pages)} /Kids [ {pages_kids_placeholder} ] >>".encode("latin-1")
    )

    page_object_ids.clear()
    for content_object_id in content_object_ids:
        page_object_id = add_object(
            f"<< /Type /Page /Parent {pages_object_id} 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_object_id} 0 R >> >> /Contents {content_object_id} 0 R >>".encode(
                "latin-1"
            )
        )
        page_object_ids.append(page_object_id)

    objects[pages_object_id - 1] = (
        f"<< /Type /Pages /Count {len(page_object_ids)} /Kids [ {' '.join(f'{page_id} 0 R' for page_id in page_object_ids)} ] >>".encode(
            "latin-1"
        )
    )
    catalog_object_id = add_object(f"<< /Type /Catalog /Pages {pages_object_id} 0 R >>".encode("latin-1"))

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

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pdf)
