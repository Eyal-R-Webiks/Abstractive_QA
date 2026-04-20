# pilot — Completed Pilot

Small-scale pilot for a Hebrew QA dataset creation pipeline.
See [PRD.md](PRD.md) for full project context and goals, and [PIPELINE_STORY_HE.md](PIPELINE_STORY_HE.md) for a narrative description of the implemented pipeline (Hebrew).

## Setup

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
```

Set your API keys in the root-level `.env` file (see `.env` at repository root):
```
OPENROUTER_API_KEY=...
ANTHROPIC_API_KEY=...
```

## Pipeline Stages

### Stage 1 — Collect Wikipedia articles
```bash
python ../data_prep/wiki/wiki_extract.py
# Output: ../data_prep/wiki/hewiki_random_310.jsonl  (Hebrew Wikipedia articles)
```

### Stage 2 — Build RAG assets (run once, reusable)
```bash
python prepare_wiki_rag_assets.py
# Output: output_flashlite/rag_assets/  (articles, chunks, embeddings)
```

### Stage 3 — Generate questions (Gemini Flash Lite, current)
```bash
python generate_questions_gemini3.1pro.py
# Output: output_gemini3.1pro_smoke/  (per-variant CSVs + collated file)
```

### Stage 3 — Generate questions (OpenRouter, earlier runs)
```bash
python generate_questions_openrouter.py
# Output: output_for_q/  (per-variant CSVs + collated file)
```

### Stage 3 — Generate questions (Ollama, local/free prototype)
```bash
ollama serve            # run in a separate terminal
python generate_questions.py
```

### Stage 4 — Evaluate questions with RAG context
```bash
python evaluate_questions_openrouter.py
# Output: output_flashlite_eval_rag/  (evaluation CSVs per model)
```

## Project Structure

```
pilot/
├── input_for_q/                        # 6 input CSVs (text position × length)
├── output_for_q/                       # OpenRouter generation outputs
├── output_flashlite/                   # Gemini Flash Lite generation outputs
│   └── rag_assets/                     # Reusable RAG store (chunks + embeddings)
├── output_flashlite_eval_rag/          # RAG-backed evaluation outputs (full run)
├── output_flashlite_eval_rag_smoke/    # RAG-backed evaluation outputs (smoke test)
├── output_gemini3.1pro_smoke/          # Gemini 3.1 Pro generation outputs (smoke)
├── analysis/                           # Slide/chart generation scripts
├── sandbox/                            # Scratch files and logs
├── generate_questions.py               # Ollama-based generation (prototype)
├── generate_questions_openrouter.py    # OpenRouter-based generation
├── generate_questions_gemini3.1pro.py  # Gemini Flash Lite generation (current)
├── evaluate_questions_openrouter.py    # RAG-backed evaluation via OpenRouter
├── prepare_wiki_rag_assets.py          # Build chunk + embedding retrieval store
├── retrieve_wiki_chunks.py             # Retrieval utility used by evaluation
├── process_conversations.py            # Conversation preprocessing
├── requirements.txt
├── PRD.md
└── PIPELINE_STORY_HE.md
```
