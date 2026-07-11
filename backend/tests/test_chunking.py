from app.chunking import chunk_opinion

PARA = "This paragraph discusses the holding of the court in some detail. " * 10


def test_groups_paragraphs_to_target():
    text = "\n\n".join(f"Paragraph {i}. " + PARA for i in range(12))
    chunks = chunk_opinion(text, "347 U.S. 483", "Brown v. Board", target_tokens=500)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.text) // 4 <= 700
        assert c.meta["citation"] == "347 U.S. 483"
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_overlap_repeats_tail_paragraph():
    paras = [f"Unique paragraph number {i}. " + PARA for i in range(8)]
    chunks = chunk_opinion("\n\n".join(paras), "1 U.S. 1", None, target_tokens=400, overlap_tokens=100)
    assert len(chunks) >= 2
    first_tail = chunks[0].text.split("\n\n")[-1]
    assert first_tail in chunks[1].text


def test_single_giant_paragraph_still_splits():
    text = "One sentence here. " * 800
    chunks = chunk_opinion(text, "1 U.S. 1", None, target_tokens=300)
    assert len(chunks) > 1


def test_empty_returns_nothing():
    assert chunk_opinion("   ", "1 U.S. 1", None) == []
