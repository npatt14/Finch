from __future__ import annotations

import re

from pydantic import BaseModel


class Chunk(BaseModel):
    text: str
    index: int
    meta: dict


def _tokens(s: str) -> int:
    return len(s) // 4


def _split_paragraphs(text: str, target_tokens: int) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out: list[str] = []
    for p in paras:
        if _tokens(p) <= target_tokens * 1.4:
            out.append(p)
            continue
        sentences = re.split(r"(?<=[.!?])\s+", p)
        buf = ""
        for s in sentences:
            if buf and _tokens(buf + " " + s) > target_tokens:
                out.append(buf)
                buf = s
            else:
                buf = f"{buf} {s}".strip()
        if buf:
            out.append(buf)
    return out


def chunk_opinion(
    text: str,
    citation: str,
    case_name: str | None,
    target_tokens: int = 1000,
    overlap_tokens: int = 150,
) -> list[Chunk]:
    overlap_tokens = min(overlap_tokens, target_tokens // 4)
    paras = _split_paragraphs(text, target_tokens)
    if not paras:
        return []
    groups: list[list[str]] = []
    buf: list[str] = []
    size = 0
    for p in paras:
        if buf and size + _tokens(p) > target_tokens:
            groups.append(buf)
            overlap: list[str] = []
            osize = 0
            for tail in reversed(buf):
                if osize >= overlap_tokens:
                    break
                overlap.insert(0, tail)
                osize += _tokens(tail)
            buf = overlap[:]
            size = osize
        buf.append(p)
        size += _tokens(p)
    if buf:
        groups.append(buf)
    meta_base = {"citation": citation, "case_name": case_name}
    return [
        Chunk(text="\n\n".join(g), index=i, meta={**meta_base, "position": i})
        for i, g in enumerate(groups)
    ]
