"""
Build a Label Studio import JSON from the round_3 generation outputs.

Mirrors the format of Sun_0531_1445_no_l3.json.
- Knesset docs: text_html from knesset_html.json
- il-hym / wiki: text_html produced by sentence-numbering the plain text

Output: data_prep_new/round_3/round3_ls_input.json
"""

import json
import re
import html as html_lib
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT       = Path("data_prep_new/round_3")
INPUT_DIR  = ROOT / "input"
OUTPUT_DIR = ROOT / "generation_v2" / "output"
KNESSET_HTML = ROOT / "aux" / "knesset_html.json"
OUT_FILE   = ROOT / "round3_ls_input.json"

LEVELS = ["level0", "level1", "level2", "level3"]

# ---------------------------------------------------------------------------
# Sentence-numbering helpers (identical to build_knesset_html.py)
# ---------------------------------------------------------------------------
STYLE = (
    "<style>"
    ".sn{color:#bbb;font-size:11px;vertical-align:super;margin-left:4px;user-select:none;}"
    "p{margin:0 0 0.9em 0;line-height:1.75;font-size:16px;}"
    ".ls-hdr{font-weight:700;color:#374151;margin:1em 0 0.3em 0;}"
    "</style>"
)

_SENT_END   = re.compile(r'([.?!\u05F4][\u201c\u201d\u2018\u2019\)\]]?)\s+(?=\S)')
_SECTION_HDR = re.compile(r'^\s*={2,}(.+?)={2,}\s*$')
_SENTINEL   = "\u0000"


def split_sentences(line):
    marked = _SENT_END.sub(lambda m: m.group(1) + _SENTINEL, line)
    parts = [s.strip() for s in marked.split(_SENTINEL)]
    return [p.replace(_SENTINEL, '') for p in parts if p]


def text_to_html(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    raw_paragraphs = re.split(r"\n{2,}", text)
    counter = [0]
    parts = [STYLE]

    for para in raw_paragraphs:
        para = para.strip()
        if not para:
            continue
        lines = para.split("\n")
        para_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            m = _SECTION_HDR.match(line)
            if m:
                para_lines.append(
                    f'<span class="ls-hdr">{html_lib.escape(m.group(1).strip())}</span>'
                )
                continue
            sentences = split_sentences(line)
            line_parts = []
            for s in sentences:
                escaped = html_lib.escape(s)
                if len(s) >= 8:
                    counter[0] += 1
                    line_parts.append(f'<span class="sn">{counter[0]}</span>{escaped}')
                else:
                    line_parts.append(escaped)
            para_lines.append(" ".join(line_parts))
        if para_lines:
            parts.append(f'<p>{"<br>".join(para_lines)}</p>')

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Load knesset HTML map
# ---------------------------------------------------------------------------
knesset_html_map = {
    r["doc_id"]: r["text_html"]
    for r in json.load(open(KNESSET_HTML, encoding="utf-8"))
}

# ---------------------------------------------------------------------------
# Load input texts (uuid → {text, source})
# ---------------------------------------------------------------------------
input_map = {}
for level in LEVELS:
    path = INPUT_DIR / f"{level}_input.json"
    if path.exists():
        for r in json.load(open(path, encoding="utf-8")):
            input_map[r["uuid"]] = {"text": r["text"], "source": r["source"]}

# ---------------------------------------------------------------------------
# Build tasks
# ---------------------------------------------------------------------------
tasks = []

for level in LEVELS:
    out_path = OUTPUT_DIR / f"{level}_output.json"
    if not out_path.exists():
        continue
    records = json.load(open(out_path, encoding="utf-8"))
    level_num = int(level.replace("level", ""))

    for rec in records:
        uuid   = rec["uuid"]
        inp    = input_map.get(uuid, {})
        source = inp.get("source", "")
        text   = inp.get("text", "")

        # text_html
        if source == "knesset" and uuid in knesset_html_map:
            text_html = knesset_html_map[uuid]
        else:
            text_html = text_to_html(text)

        # excerpt: first ~120 chars of text (strip leading whitespace/newlines)
        excerpt = text.strip()[:120].replace("\n", " ")

        data = {
            "text":                          text,
            "level":                         level_num,
            "author":                        rec.get("author", "gemini"),
            "doc_id":                        uuid,
            "dataset":                       source,
            "excerpt":                       excerpt,
            "question":                      rec.get("question", ""),
            "reasoning":                     rec.get("reasoning", ""),
            "record_id":                     uuid[:8],
            "text_html":                     text_html,
            "answer_spans":                  rec.get("answer_spans", []),
            "mimic_target":                  rec.get("mimic_target", ""),
            "expected_answer_spans_level0":  rec.get("expected_answer_spans_level0", []),
        }

        task = {
            "annotations":                  [],
            "file_upload":                  "",
            "drafts":                       [],
            "predictions":                  [],
            "state":                        "ANNOTATION_IN_PROGRESS",
            "agreement":                    None,
            "data":                         data,
            "meta":                         {},
            "created_at":                   None,
            "updated_at":                   None,
            "allow_skip":                   True,
            "inner_id":                     None,
            "total_annotations":            0,
            "cancelled_annotations":        0,
            "total_predictions":            0,
            "comment_count":                0,
            "unresolved_comment_count":     0,
            "last_comment_updated_at":      None,
            "project":                      None,
            "updated_by":                   None,
            "comment_authors":              [],
        }
        tasks.append(task)

OUT_FILE.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Done. {len(tasks)} tasks written to {OUT_FILE}")

# Summary by level
from collections import Counter
by_level = Counter(t["data"]["level"] for t in tasks)
by_source = Counter(t["data"]["dataset"] for t in tasks)
for k in sorted(by_level):
    print(f"  level{k}: {by_level[k]}")
print("  sources:", dict(by_source))
knesset_with_html = sum(
    1 for t in tasks
    if t["data"]["dataset"] == "knesset" and "spk" in t["data"]["text_html"]
)
print(f"  knesset with rich HTML: {knesset_with_html}")
