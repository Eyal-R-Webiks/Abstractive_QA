"""Chunk the Keith Taynton Medium HTML article for RAG."""
import json, re
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'beautifulsoup4', '-q'])
    from bs4 import BeautifulSoup

import glob as _glob
_matches = _glob.glob("Bloom_taxonomy/further_resources/*.html")
if not _matches:
    raise FileNotFoundError("HTML file not found")
html_path = Path(_matches[0])
out_path = Path("Bloom_taxonomy/further_resources/chunks/taynton_medium_llm_bloom.jsonl")

MAX = 2000; OVERLAP = 200

html = html_path.read_text(encoding='utf-8', errors='ignore')
soup = BeautifulSoup(html, 'html.parser')

# Extract article body paragraphs/headings in order
article = soup.find('article') or soup.find('main') or soup.body
elements = article.find_all(['h1','h2','h3','h4','p','li','blockquote']) if article else []

# Build sections: split at headings
sections = []
current_title = "Introduction"
current_buf = []

def flush(title, buf):
    text = ' '.join(buf).strip()
    text = re.sub(r'\s+', ' ', text)
    if len(text) > 80:
        sections.append({'section': title, 'text': text})

for el in elements:
    tag = el.name
    text = el.get_text(' ', strip=True)
    if not text or len(text) < 3:
        continue
    if tag in ('h1','h2','h3','h4'):
        flush(current_title, current_buf)
        current_title = text
        current_buf = []
    else:
        current_buf.append(text)

flush(current_title, current_buf)

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
    for ci, chunk in enumerate(sub_chunk(sec['text'])):
        records.append({
            'source': 'taynton_medium_llm_bloom.html',
            'section': sec['section'],
            'chunk_index': ci,
            'pages': [],
            'text': chunk
        })

out_path.parent.mkdir(parents=True, exist_ok=True)
with out_path.open('w', encoding='utf-8') as f:
    for rec in records:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')

lengths = [len(rec['text']) for rec in records]
print(f'{len(records)} chunks -> {out_path}')
if lengths:
    print(f'char stats: min={min(lengths)} avg={int(sum(lengths)/len(lengths))} max={max(lengths)}')
