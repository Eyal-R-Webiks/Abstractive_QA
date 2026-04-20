# data_prep — Corpus Data

Raw and prepared corpora used as source material for the Hebrew QA pipeline.
These files are **not versioned in git** (too large); regenerate them from the scripts listed below.

## Folder Structure

```
data_prep/
├── wiki/                           # Hebrew Wikipedia corpus
│   ├── wiki_extract.py             # Script to fetch and extract articles
│   ├── hewiki_random_310.jsonl     # 310 random Hebrew Wikipedia articles
│   ├── individuals/                # Same articles as individual JSON files
│   │   └── article_{NNN}_{pageid}.json
│   └── test/                       # 10-article test subset
│       ├── article_{NNN}_{pageid}.json
│       ├── hewiki_random_10.jsonl
│       └── hewiki_random_10_summary.json
│
├── il-hym/                         # Israel HaYom newspaper corpus
│   └── animals-{article_id}.txt   # Articles filtered to genre=animals (~275K files)
│
├── knesset/                        # Knesset parliamentary protocols corpus
│   ├── committee_no_morph_sentences_shards_bzip2_files/  # 91 JSONL shards (.bz2)
│   ├── knesset_corpus_RC.csv / .json
│   └── vad_shard_0.csv / .jsonl
│
├── reports/                        # Survey and inventory reports
│   ├── build_il_hym_report.py
│   ├── build_wiki_extract_report.py
│   ├── il-hym_survey.json / _report.html
│   ├── hewiki_random_310_summary.json
│   └── wiki_extract_survey_report.html
│
└── archive/                        # Superseded intermediate outputs (not in git)
```

## Article JSON Schema (wiki)

```json
{
  "id": 1196898,
  "title": "...",
  "url": "https://he.wikipedia.org/wiki/...",
  "category": "...",
  "length_chars": 12345,
  "text": "...",
  "source": "hewiki",
  "retrieved_at": "2026-..."
}
```

## il-hym File Format

Each `.txt` file starts with metadata header lines:
```
# source: israel-hayom
# genre: animals
# url: ...
# doc_id: ...
# title: ...
```
followed by the article body.
