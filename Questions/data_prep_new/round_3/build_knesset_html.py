"""
Build a JSON file with doc_id + text_html for all 80 knesset docs.

For valid .docx files: extracts structure-aware HTML preserving speaker/heading styles.
  - Metadata header block (Knesset #, session, committee, date, attendees) is preserved
    line-by-line with <br>, no sentence numbering.
  - Speaker/chair paragraphs contain only a << TAG >> name: << TAG >> marker — the name
    is extracted and rendered styled; following Normal paragraphs are their speech.
  - Topic/subject lines (נושא style) rendered as italic headers.
  - Vote/procedural lines rendered muted.

For binary OLE files: falls back to the clean plain text from the .jsonl files.
  - Lines starting with "Name:" are parsed as speaker turns.
  - Single \n within a paragraph → <br>.

Output: data_prep_new/round_3/aux/knesset_html.json
"""

import json
import re
import html as html_lib
from pathlib import Path
from docx import Document

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
AUX_DIR  = Path("data_prep_new/round_3/aux/knesset_docs")
DOCS_DIR = Path("data_prep_new/round_3/docs")
OUT_FILE = Path("data_prep_new/round_3/aux/knesset_html.json")

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
CSS = (
    "<style>"
    ".sn{color:#bbb;font-size:11px;vertical-align:super;margin-left:4px;user-select:none;}"
    "p{margin:0 0 0.5em 0;line-height:1.75;font-size:15px;direction:rtl;}"
    ".meta{color:#6b7280;font-size:13px;margin:0;line-height:1.6;}"
    ".topic{font-weight:700;color:#374151;border-right:3px solid #d1d5db;"
           "padding-right:8px;margin:1em 0 0.5em;}"
    ".spk{font-weight:600;color:#1e40af;margin-top:0.8em;display:block;}"
    ".chair{font-weight:700;color:#1d4ed8;margin-top:0.8em;display:block;}"
    ".vote{color:#9ca3af;font-size:13px;font-style:italic;}"
    "</style>"
)

# ---------------------------------------------------------------------------
# Sentence-numbering helpers
# ---------------------------------------------------------------------------
_SENT_END = re.compile(r'([.?!\u05F4][\u201c\u201d\u2018\u2019\)\]]?)\s+(?=\S)')
_SENTINEL = "\x01"   # use SOH (non-printing, safe) instead of null


def split_sentences(line: str) -> list:
    marked = _SENT_END.sub(lambda m: m.group(1) + _SENTINEL, line)
    parts = [s.strip() for s in marked.split(_SENTINEL)]
    return [p for p in parts if p]


def number_text(text: str, counter: list) -> str:
    """Wrap each sentence with a superscript sentence-number span."""
    sentences = split_sentences(text)
    parts = []
    for s in sentences:
        escaped = html_lib.escape(s)
        if len(s) >= 8:
            counter[0] += 1
            parts.append(f'<span class="sn">{counter[0]}</span>{escaped}')
        else:
            parts.append(escaped)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Helpers for docx marker stripping
# ---------------------------------------------------------------------------
# Matches: << TAG >> some text << TAG >>  or  << TAG >> some text: << TAG >>
_MARKER = re.compile(r'^<<\s*\S+\s*>>\s*(.*?)\s*<<\s*\S+\s*>>$', re.DOTALL)


def strip_marker(text: str) -> str:
    """Strip << TAG >> ... << TAG >> wrapper and return inner content."""
    m = _MARKER.match(text)
    return m.group(1).strip() if m else text.strip()


def extract_speaker_name(text: str) -> str:
    """From '<<יור>> היו"ר פלוני: <<יור>>' return 'היו"ר פלוני'."""
    inner = strip_marker(text)
    # Remove trailing colon
    return inner.rstrip(":").strip()


# Style sets
SPEAKER_STYLES = {"דובר", "דובר-המשך", "אורח"}
CHAIR_STYLES   = {"יור"}
TOPIC_STYLES   = {"נושא", "Head HatzaotHok", "KeepWithNext"}
VOTE_STYLES    = {"הצבעה_בעד-נגד-נמנעים", "הצבעה_מספר", "הצבעה_תוצאות",
                  "הפסקת_הישיבה", "סיום_הישיבה", "קריאות"}
SPEAKER_ALL    = SPEAKER_STYLES | CHAIR_STYLES


# ---------------------------------------------------------------------------
# Detect where the metadata header ends and dialogue begins
# ---------------------------------------------------------------------------
def _is_dialogue_style(style: str) -> bool:
    return style in (SPEAKER_ALL | TOPIC_STYLES | VOTE_STYLES)


def docx_to_html(doc_path: Path) -> str:
    """Convert a valid .docx file to structured HTML with sentence numbers."""
    doc = Document(doc_path)
    counter = [0]

    # Split into header block (before first dialogue paragraph) and body
    paras = list(doc.paragraphs)
    header_end = 0
    for i, p in enumerate(paras):
        if p.text.strip() and _is_dialogue_style(p.style.name):
            header_end = i
            break
    else:
        header_end = len(paras)  # no dialogue found — all header

    parts = [CSS]

    # --- Metadata header block ---
    header_lines = []
    for p in paras[:header_end]:
        t = p.text.strip()
        if t:
            header_lines.append(html_lib.escape(t))
    if header_lines:
        parts.append('<p class="meta">' + "<br>".join(header_lines) + "</p>")

    # --- Dialogue body ---
    for p in paras[header_end:]:
        text = p.text.strip()
        if not text:
            continue
        style = p.style.name

        if style in TOPIC_STYLES:
            topic = html_lib.escape(strip_marker(text))
            parts.append(f'<p class="topic">{topic}</p>')

        elif style in CHAIR_STYLES:
            name = html_lib.escape(extract_speaker_name(text))
            parts.append(f'<span class="chair">{name}:</span>')

        elif style in SPEAKER_STYLES:
            name = html_lib.escape(extract_speaker_name(text))
            parts.append(f'<span class="spk">{name}:</span>')

        elif style in VOTE_STYLES:
            parts.append(f'<p class="vote">{html_lib.escape(text)}</p>')

        else:
            # Normal / Body Text — speech content
            parts.append(f'<p>{number_text(text, counter)}</p>')

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Plain-text fallback for binary OLE docs
# Speaker format: "Name: speech text" per line
# ---------------------------------------------------------------------------
# Matches lines that start with a speaker name before the first colon,
# where the name part has no sentence-ending punctuation (heuristic)
_SPEAKER_LINE = re.compile(r'^([^:\n]{2,50}):\s+(.+)$', re.DOTALL)
_SECTION_HDR  = re.compile(r'^\s*={2,}(.+?)={2,}\s*$')


def _is_name_like(s: str) -> bool:
    """Rough heuristic: a speaker name contains Hebrew letters, is short, no sentence punctuation."""
    return bool(re.search(r'[\u05d0-\u05ea]', s)) and not re.search(r'[.?!]', s)


def knesset_text_to_html(text: str) -> str:
    """
    Convert plain knesset transcript text to structured HTML.
    Lines formatted as 'Name: speech' are rendered with a styled speaker label.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    counter = [0]
    parts = [CSS]

    # Split on double newlines into paragraphs; single newlines stay as <br>
    raw_paragraphs = re.split(r'\n{2,}', text)

    for para in raw_paragraphs:
        para = para.strip()
        if not para:
            continue

        lines = para.split("\n")
        para_html_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Section header: == text ==
            m_hdr = _SECTION_HDR.match(line)
            if m_hdr:
                para_html_lines.append(
                    f'<span class="topic">{html_lib.escape(m_hdr.group(1).strip())}</span>'
                )
                continue

            # Speaker turn: "Name: speech"
            m_spk = _SPEAKER_LINE.match(line)
            if m_spk and _is_name_like(m_spk.group(1)):
                name    = html_lib.escape(m_spk.group(1).strip())
                speech  = m_spk.group(2).strip()
                numbered = number_text(speech, counter)
                para_html_lines.append(
                    f'<span class="spk">{name}:</span> {numbered}'
                )
                continue

            # Plain line
            para_html_lines.append(number_text(line, counter))

        if para_html_lines:
            parts.append(f'<p>{"<br>".join(para_html_lines)}</p>')

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Build the output
# ---------------------------------------------------------------------------
def find_jsonl(doc_id: str):
    matches = list(DOCS_DIR.rglob(f"{doc_id}.jsonl"))
    return matches[0] if matches else None


def main():
    results = []
    valid_docx = binary_fallback = 0

    for docx_path in sorted(AUX_DIR.glob("*.docx")):
        doc_id = docx_path.stem

        try:
            Document(docx_path)  # raises for binary OLE
            text_html = docx_to_html(docx_path)
            valid_docx += 1
        except Exception:
            jsonl = find_jsonl(doc_id)
            if jsonl is None:
                print(f"[SKIP] {doc_id} — no jsonl found")
                continue
            d = json.loads(jsonl.read_text(encoding="utf-8"))
            text_html = knesset_text_to_html(d.get("text", ""))
            binary_fallback += 1

        results.append({"doc_id": doc_id, "text_html": text_html})

    OUT_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Done. {len(results)} docs written to {OUT_FILE}")
    print(f"  valid docx: {valid_docx}, binary fallback: {binary_fallback}")


if __name__ == "__main__":
    main()
