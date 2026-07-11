from __future__ import annotations

import io


def _pdf_text(data: bytes) -> str:
    import pdfplumber

    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n\n".join(parts)


def _docx_text(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    return "\n\n".join(p.text for p in doc.paragraphs)


def extract_text(
    filename: str | None,
    data: bytes | None,
    pasted: str | None,
    max_chars: int,
) -> str:
    text = ""
    if pasted and pasted.strip():
        text = pasted
    elif data and filename:
        name = filename.lower()
        if name.endswith(".pdf"):
            text = _pdf_text(data)
        elif name.endswith(".docx"):
            text = _docx_text(data)
        else:
            text = data.decode("utf-8", errors="replace")
    text = text.strip()
    if not text:
        raise ValueError("empty document")
    return text[:max_chars]
