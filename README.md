# Abstractive QA — Hebrew QA Pipeline

Research project for building a Hebrew abstractive question-answering dataset.
The pipeline takes raw Hebrew text from multiple corpora, generates questions using LLMs, and evaluates them with RAG-backed automated scoring.

## Repository Structure

```
Abstractive_QA/
├── pilot/                  # Completed pilot (scripts, runs, evaluation)
├── data_prep/              # Corpus data and preparation scripts (large files not versioned)
└── info_sheets/            # Reference paper chunks for RAG-backed methodology Q&A
```

See each folder's `README.md` for details:
- [pilot/README.md](pilot/README.md) — setup, pipeline stages, script reference
- [data_prep/README.md](data_prep/README.md) — corpus descriptions and file formats

## Quick Start

```bash
cd pilot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Set API keys in the root-level .env file
```

## Corpora

| Corpus | Source | Size | Status |
|--------|--------|------|--------|
| Hebrew Wikipedia | `data_prep/wiki/` | 310 articles | Versioned |
| Israel HaYom | `data_prep/il-hym/` | ~275K articles | Not versioned (2 GB) |
| Knesset protocols | `data_prep/knesset/` | 91 shards | Not versioned (4.5 GB) |
