"""
Add sentence numbers to LS tasks as a new `text_html` field.

Input:  annotation/labelstudio_tasks_randomized.json
Output: annotation/labelstudio_tasks_numbered.json

The `text_html` field contains HTML suitable for <HyperText inline="true"/>.
Each sentence is prefixed with a small muted superscript number.
Numbering is global across the whole document.
"""

import json
import re
import html
import os

IN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Snapshot3_0519_1215.json")
OUT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Snapshot3_0519_1215_numbered.json")

# Injected into every text_html value so HyperText renders correctly
STYLE = (
    '<style>'
    '.sn{color:#bbb;font-size:11px;vertical-align:super;'
    'margin-left:4px;user-select:none;}'
    'p{margin:0 0 0.9em 0;line-height:1.75;font-size:16px;}'
    '.ls-hdr{font-weight:700;color:#374151;margin:1em 0 0.3em 0;}'
    '</style>'
)

# Sentence boundary: period / ? / ! optionally followed by a closing quote/paren,
# then one or more whitespace chars that are followed by a non-whitespace char.
# We use a sentinel approach to avoid variable-width lookbehinds.
_SENT_END = re.compile(r'([.?!][\u201c\u201d\u2018\u2019\u05f4\)\]]?)\s+(?=\S)')
_SECTION_HDR = re.compile(r'^\s*={2,}(.+?)={2,}\s*$')
_ONLY_WHITESPACE = re.compile(r'^\s*$')


_SENTINEL = '\u0000'


def split_sentences(line: str) -> list[str]:
    """Split a line of text into sentences."""
    marked = _SENT_END.sub(lambda m: m.group(1) + _SENTINEL, line)
    parts = [s.strip() for s in marked.split(_SENTINEL)]
    return [p for p in parts if p]


def text_to_html(text: str) -> str:
    """
    Convert plain text (with \\n paragraph breaks) to HTML with sentence numbers.
    Returns a full HTML fragment (style + body).
    """
    # Normalise line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Split into paragraphs on two or more consecutive newlines
    raw_paragraphs = re.split(r'\n{2,}', text)

    html_parts = []
    sent_counter = 0

    for para in raw_paragraphs:
        para = para.strip()
        if not para:
            continue

        # Each paragraph may contain sub-lines separated by a single \n
        lines = para.split('\n')
        para_html_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Wiki-style section header: == text ==
            m = _SECTION_HDR.match(line)
            if m:
                heading_text = html.escape(m.group(1).strip())
                para_html_lines.append(
                    f'<span class="ls-hdr">{heading_text}</span>'
                )
                continue

            # Split into sentences and number each one
            sentences = split_sentences(line)
            line_parts = []
            for sent in sentences:
                # Only number sentences that are substantial (≥ 8 chars)
                if len(sent) >= 8:
                    sent_counter += 1
                    num_span = f'<span class="sn">{sent_counter}</span>'
                    line_parts.append(f'{num_span}{html.escape(sent)}')
                else:
                    # Short fragment (e.g. trailing punctuation) — append without number
                    line_parts.append(html.escape(sent))

            if line_parts:
                para_html_lines.append(' '.join(line_parts))

        if para_html_lines:
            inner = '<br>'.join(para_html_lines)
            html_parts.append(f'<p>{inner}</p>')

    return STYLE + '\n'.join(html_parts)


def main():
    with open(IN_FILE, encoding='utf-8') as f:
        tasks = json.load(f)

    for task in tasks:
        raw_text = task['data'].get('text', '')
        task['data']['text_html'] = text_to_html(raw_text)

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

    print(f"Done. {len(tasks)} tasks written to {OUT_FILE}")

    # Print a preview of the first task's HTML (truncated)
    preview = tasks[0]['data']['text_html']
    print("\n--- HTML preview (first 1000 chars) ---")
    print(preview[:1000])


if __name__ == '__main__':
    main()
