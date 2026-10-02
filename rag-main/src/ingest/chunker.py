"""
src/ingest/chunker.py

Smart chunking for Prabhav-AI.
Strategy:
  1. Markdown with # headers  → MarkdownHeaderTextSplitter (LangChain)
  2. No headers               → TF-IDF semantic grouping (sklearn)
  3. Any block still too big  → hard slice fallback
"""

from __future__ import annotations

import re
from typing import List

from langchain_text_splitters import MarkdownHeaderTextSplitter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ── tunables ─────────────────────────────────────────────────────────────────
MAX_CHUNK_CHARS = 1500          # hard ceiling per chunk
MIN_CHUNK_CHARS = 100           # ignore tiny fragments
SEMANTIC_SIMILARITY_THRESHOLD = 0.20   # below this → start a new group
SEMANTIC_MAX_SENTENCES = 12     # max sentences per semantic group
# ─────────────────────────────────────────────────────────────────────────────

HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
    ("####", "h4"),
]


def _has_headers(text: str) -> bool:
    return bool(re.search(r"^#{1,4}\s+\S", text, re.MULTILINE))


def _hard_slice(text: str, max_chars: int = MAX_CHUNK_CHARS) -> List[str]:
    """Last-resort: slice by character count at word boundaries."""
    chunks, start = [], 0
    while start < len(text):
        end = start + max_chars
        if end >= len(text):
            chunks.append(text[start:].strip())
            break
        # walk back to last space
        cut = text.rfind(" ", start, end)
        if cut == -1:
            cut = end
        chunks.append(text[start:cut].strip())
        start = cut + 1
    return [c for c in chunks if len(c) >= MIN_CHUNK_CHARS]


def _chunk_by_headers(text: str) -> List[str]:
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT_ON,
        strip_headers=False,
    )
    docs = splitter.split_text(text)
    chunks = []
    for doc in docs:
        content = doc.page_content.strip()
        if not content or len(content) < MIN_CHUNK_CHARS:
            continue
        if len(content) > MAX_CHUNK_CHARS:
            chunks.extend(_hard_slice(content))
        else:
            chunks.append(content)
    return chunks


def _split_into_sentences(text: str) -> List[str]:
    """Naive sentence splitter — good enough for business docs."""
    raw = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in raw if s.strip()]


def _chunk_by_tfidf(text: str) -> List[str]:
    sentences = _split_into_sentences(text)
    if len(sentences) <= 1:
        return _hard_slice(text)

    try:
        tfidf = TfidfVectorizer().fit_transform(sentences)
    except ValueError:
        # corpus too sparse / all stop words
        return _hard_slice(text)

    groups: List[List[str]] = [[sentences[0]]]

    for i in range(1, len(sentences)):
        sim = cosine_similarity(tfidf[i - 1], tfidf[i])[0][0]
        current_group = groups[-1]
        current_text = " ".join(current_group)

        too_long = len(current_text) + len(sentences[i]) + 1 > MAX_CHUNK_CHARS
        too_many = len(current_group) >= SEMANTIC_MAX_SENTENCES
        low_sim = sim < SEMANTIC_SIMILARITY_THRESHOLD

        if low_sim or too_long or too_many:
            groups.append([sentences[i]])
        else:
            current_group.append(sentences[i])

    chunks = []
    for group in groups:
        content = " ".join(group).strip()
        if len(content) < MIN_CHUNK_CHARS:
            continue
        if len(content) > MAX_CHUNK_CHARS:
            chunks.extend(_hard_slice(content))
        else:
            chunks.append(content)
    return chunks


def chunk(text: str) -> List[str]:
    """
    Main entry point.
    Returns a list of clean text chunks ready for embedding.
    """
    text = text.strip()
    if not text:
        return []

    if _has_headers(text):
        result = _chunk_by_headers(text)
    else:
        result = _chunk_by_tfidf(text)

    # final safety pass
    final = []
    for c in result:
        if len(c) > MAX_CHUNK_CHARS:
            final.extend(_hard_slice(c))
        elif len(c) >= MIN_CHUNK_CHARS:
            final.append(c)

    return final