"""One-off chunker for flat-text PDFs where headers are inline (no line breaks)."""
import json, re, warnings
warnings.filterwarnings('ignore')
from pypdf import PdfReader
from pathlib import Path

pdf = 'Bloom_taxonomy/further_resources/2511.01649v1.pdf'
out = Path('Bloom_taxonomy/further_resources/chunks/2511.01649v1.jsonl')
MAX = 2000; OVERLAP = 200

r = PdfReader(pdf)
full_text = ' '.join((p.extract_text() or '') for p in r.pages)

# Split on numbered sections like "1. Introduction", "2. Related Work"
section_re = re.compile(r'(\b\d{1,2}\.\s+[A-Z][A-Za-z ]{3,40})(?=\s)')
parts = section_re.split(full_text)

sections = []
if parts[0].strip():
    sections.append({'section': 'Abstract', 'text': parts[0].strip()})
i = 1
while i + 1 < len(parts):
    sec_title = parts[i].strip()
    sec_text = parts[i+1].strip() if (i+1) < len(parts) else ''
    if sec_text:
        sections.append({'section': sec_title, 'text': sec_text})
    i += 2

def sub_chunk(text):
    if len(text) <= MAX:
        return [text]
    sents = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    chunks, buf, buf_len = [], [], 0
    for s in sents:
        if buf_len + len(s) + 1 > MAX and buf:
            chunks.append(' '.join(buf))
            ob, ol = [], 0
            for x in reversed(buf):
                if ol + len(x) <= OVERLAP:
                    ob.insert(0, x); ol += len(x)
                else:
                    break
            buf, buf_len = ob, sum(len(x) for x in ob)
        buf.append(s); buf_len += len(s) + 1
    if buf:
        chunks.append(' '.join(buf))
    return chunks or [text[:MAX]]

records = []
for sec in sections:
    if len(sec['text']) < 80:
        continue
    for ci, chunk in enumerate(sub_chunk(sec['text'])):
        records.append({
            'source': '2511.01649v1.pdf',
            'section': sec['section'],
            'chunk_index': ci,
            'pages': [],
            'text': chunk
        })

with out.open('w', encoding='utf-8') as f:
    for rec in records:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')

lengths = [len(rec['text']) for rec in records]
print(f'{len(records)} chunks -> {out}')
print(f'char stats: min={min(lengths)} avg={int(sum(lengths)/len(lengths))} max={max(lengths)}')
