"""Sprint 3 — chunking is deterministic, boundary-aware, and idempotent."""

from __future__ import annotations

from app.services.chunking import chunk_text


def test_empty_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n  \n  ") == []


def test_short_text_single_chunk():
    chunks = chunk_text("Hello world.")
    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert chunks[0].text == "Hello world."


def test_idempotent_same_input_yields_same_chunks():
    text = "First paragraph.\n\nSecond paragraph here.\n\nThird and final."
    a = chunk_text(text)
    b = chunk_text(text)
    assert [c.text for c in a] == [c.text for c in b]
    assert [c.index for c in a] == [c.index for c in b]


def test_long_text_splits_with_overlap():
    para = " ".join(f"word{i}" for i in range(500))
    chunks = chunk_text(para, target_tokens=80, overlap_tokens=10, max_tokens=120)
    assert len(chunks) >= 5
    # Indices are sequential and start at 0.
    assert [c.index for c in chunks] == list(range(len(chunks)))
    # Each chunk except the first should carry the overlap tail of its predecessor.
    for i in range(1, len(chunks)):
        prev_tail = " ".join(chunks[i - 1].text.split()[-10:])
        # The overlap appears at the start of chunk i (modulo small slack).
        assert any(
            tok in chunks[i].text.split()[:15] for tok in prev_tail.split()
        )


def test_paragraph_breaks_preferred_over_word_breaks():
    text = (
        "Paragraph one is short.\n\n"
        + "Paragraph two has a few more words but still well under the cap.\n\n"
        + "Paragraph three closes the document."
    )
    chunks = chunk_text(text, target_tokens=12, overlap_tokens=0)
    # Each non-trivial paragraph should land in its own chunk.
    assert len(chunks) >= 3


def test_token_count_present_and_positive():
    text = "Mission Starline-1 has entered active state."
    chunks = chunk_text(text)
    assert chunks
    assert all(c.token_count > 0 for c in chunks)
