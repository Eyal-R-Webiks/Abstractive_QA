#!/usr/bin/env python3
"""Chunk a PDF into overlapping text segments for RAG.

Strategy:
1. Extract text page-by-page via pypdf.
2. Split into sections using numbered/named section headers.
3. Sub-chunk any section that exceeds MAX_CHARS, with OVERLAP_CHARS overlap.
4. Write one JSON object per chunk to chunks_for_RAG/<stem>.jsonl.

Each chunk record:
{
  "source": "LLMs_Bloom.pdf",
  "section": "3 Methodology",
  "chunk_index": 0,
  "pages": [3, 4],
  "text": "..."
}

Usage (from resources/):
    python chunk_pdf_for_rag.py LLMs_Bloom.pdf
    python chunk_pdf_for_rag.py LLMs_Bloom.pdf --max-chars 1500 --overlap 200
"""

import argparse
import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------
DEFAULT_MAX_CHARS = 2000   # target max chars per chunk
DEFAULT_OVERLAP = 200      # overlap between consecutive sub-chunks

# Section-header patterns (numbered or named), e.g.:
#   "1 Introduction", "3 Methodology", "Abstract", "References", "A Appendix Title"
SECTION_HEADER_RE = re.compile(
    r"^(?:"
    r"\d+(?:\.\d+)*\s+[A-Z][A-Za-z\s\-]{3,}"    # "1 Introduction" / "3.1 Data"
    r"|[A-Z][a-z]+(?:\s+[A-Za-z]+){0,4}"          # "Abstract" / "Related Work"
    r"|[A-Z]\s+[A-Z][A-Za-z\s\-]{3,}"             # "A Individual Task Results"
    r")$"
)

# Lines that look like table rows / figure captions — don't treat as headers
NOISE_RE = re.compile(
    r"(?:Table|Figure|Appendix|©|\d{4}|http|www|\bpp\b|\betal\b)", re.IGNORECASE
)

# Sections to skip entirely (not useful for RAG)
SKIP_SECTIONS_RE = re.compile(
    r"^(References|Model Benchmark Subtask Score Source|Preamble)$"
)


def is_section_header(line: str) -> bool:
    s = line.strip()
    if len(s) < 4 or len(s) > 80:
        return False
    if NOISE_RE.search(s):
        return False
    return bool(SECTION_HEADER_RE.match(s))


def extract_pages(pdf_path: Path) -> list[tuple[int, str]]:
    """Return [(page_no_1based, text), ...]"""
    reader = PdfReader(str(pdf_path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append((i, text))
    return pages


def pages_to_sections(pages: list[tuple[int, str]]) -> list[dict]:
    """Split page text into sections, returning list of section dicts."""
    # Walk line by line, tagging with page number
    tagged: list[tuple[int, str]] = []  # (page_no, line)
    for page_no, text in pages:
        for line in text.split("\n"):
            tagged.append((page_no, line))

    sections: list[dict] = []
    current_title = "Preamble"
    current_lines: list[str] = []
    current_pages: set[int] = set()

    def flush():
        nonlocal current_title, current_lines, current_pages
        body = "\n".join(current_lines).strip()
        # Collapse runs of blank lines
        body = re.sub(r"\n{3,}", "\n\n", body)
        if body:
            sections.append(
                {
                    "section": current_title,
                    "pages": sorted(current_pages),
                    "text": body,
                }
            )
        current_lines = []
        current_pages = set()

    for page_no, line in tagged:
        current_pages.add(page_no)
        if is_section_header(line):
            flush()
            current_title = line.strip()
        else:
            current_lines.append(line)

    flush()
    return sections


def _sentences(text: str) -> list[str]:
    """Split text into sentences on '. ', '? ', '! ' and single newlines."""
    # Normalise newlines to spaces (PDF extraction uses single \n within paragraphs)
    flat = re.sub(r"\n+", " ", text).strip()
    # Split on sentence-ending punctuation followed by space + capital letter
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\u05D0-\u05EA\"\'])", flat)
    return [p.strip() for p in parts if p.strip()]


def _hard_split(text: str, max_chars: int, overlap: int) -> list[str]:
    """Fallback: hard character split with overlap when no sentence boundaries work."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunks.append(text[start:end].strip())
        start = end - overlap
    return [c for c in chunks if c]


def sub_chunk(text: str, max_chars: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks of at most max_chars characters."""
    if len(text) <= max_chars:
        return [text]

    sentences = _sentences(text)
    if not sentences:
        return _hard_split(text, max_chars, overlap)

    chunks: list[str] = []
    buf: list[str] = []
    buf_len = 0

    for sent in sentences:
        sent_len = len(sent)
        if buf_len + sent_len + 1 > max_chars and buf:
            chunks.append(" ".join(buf))
            # Overlap: keep trailing sentences up to overlap chars
            overlap_buf: list[str] = []
            overlap_len = 0
            for s in reversed(buf):
                if overlap_len + len(s) <= overlap:
                    overlap_buf.insert(0, s)
                    overlap_len += len(s)
                else:
                    break
            buf = overlap_buf
            buf_len = sum(len(s) for s in buf)

        buf.append(sent)
        buf_len += sent_len + 1  # +1 for space

    if buf:
        chunks.append(" ".join(buf))

    if not chunks:
        return _hard_split(text, max_chars, overlap)

    # If any chunk is still too big (e.g. no sentence breaks in a table),
    # recursively hard-split it.
    result: list[str] = []
    for c in chunks:
        if len(c) > max_chars:
            result.extend(_hard_split(c, max_chars, overlap))
        else:
            result.append(c)
    # Drop empty/whitespace-only artifacts from hard splits
    return [c for c in result if len(c.strip()) > 5]


def build_chunks(
    sections: list[dict], max_chars: int, overlap: int
) -> list[dict]:
    all_chunks: list[dict] = []
    for sec in sections:
        if SKIP_SECTIONS_RE.match(sec["section"]):
            continue
        # Also skip tiny noise sections (pure figure/table text or author lines)
        if len(sec["text"]) < 80:
            continue
        sub = sub_chunk(sec["text"], max_chars, overlap)
        for i, text in enumerate(sub):
            all_chunks.append(
                {
                    "section": sec["section"],
                    "chunk_index": i,
                    "pages": sec["pages"],
                    "text": text,
                }
            )
    return all_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Chunk a PDF for RAG")
    parser.add_argument("pdf", type=Path, help="Path to PDF file")
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    parser.add_argument("--overlap", type=int, default=DEFAULT_OVERLAP)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).parent / "chunks_for_RAG",
    )
    args = parser.parse_args()

    pdf_path = args.pdf if args.pdf.is_absolute() else Path.cwd() / args.pdf
    if not pdf_path.exists():
        sys.exit(f"File not found: {pdf_path}")

    print(f"Reading {pdf_path.name} …")
    pages = extract_pages(pdf_path)
    print(f"  {len(pages)} pages extracted")

    sections = pages_to_sections(pages)
    print(f"  {len(sections)} sections detected")

    chunks = build_chunks(sections, args.max_chars, args.overlap)
    print(f"  {len(chunks)} chunks produced")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / (pdf_path.stem + ".jsonl")

    with out_path.open("w", encoding="utf-8") as fh:
        for chunk in chunks:
            record = {"source": pdf_path.name, **chunk}
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"  → {out_path}")

    # Quick stats
    lengths = [len(c["text"]) for c in chunks]
    print(
        f"  char stats: min={min(lengths)} avg={int(sum(lengths)/len(lengths))} max={max(lengths)}"
    )


if __name__ == "__main__":
    main()
