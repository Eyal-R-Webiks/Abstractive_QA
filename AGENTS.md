# Agent Instructions — Abstractive QA

Hebrew Abstractive QA dataset pipeline for the MAFAT/Dicta leaderboard. See [README.md](README.md) and [PRD.md](PRD.md) for full context.

## Environment

- **Python venv**: `data_prep/.venv/` — activate with `source data_prep/.venv/bin/activate`
- **Dashboard venv**: separate; managed via `human-signal-dashboard/pyproject.toml` (hatchling)
- **API keys**: root `.env` file (not versioned). Key variables: `OPENROUTER_API_KEY`, `LS_REFRESH_TOKEN`, `LS_ALTERNATIVE_TOKEN`
- Scripts load credentials via `python-dotenv`: `load_dotenv(".env")` → `os.environ.get(...)`

## Running Scripts

Most root-level scripts have **no CLI args** — run directly: `python generate_level0_json.py`

The main generation runner uses argparse:
```
python data_prep_3/experiment/run_generation.py --level level0   # level0|level1|level2|level3
```

Dashboard:
```
cd human-signal-dashboard && python start.py        # default project, port default
cd human-signal-dashboard && python start_alt.py    # project 259584, port 8766
```

## Question Level Taxonomy

Critical project-specific knowledge — levels 0–3 based on Bloom's Taxonomy:

| Level | Type | Description |
|-------|------|-------------|
| 0 | Absent information | Answerable only from knowledge *outside* the text |
| 1 | Directly stated | Answer is explicit in a single sentence (`[SN]`) |
| 2 | Multi-sentence synthesis | Requires connecting 2+ sentences |
| 3 | Inference / evaluation | Requires prediction, contradiction-spotting, or evidence-based stance |

See [data_prep_3/Level_definitions_v2_proposal.md](data_prep_3/Level_definitions_v2_proposal.md) for full definitions.

## OpenRouter / Gemini API Conventions

- **Endpoint**: `https://openrouter.ai/api/v1/chat/completions`
- **Primary model**: `google/gemini-3.1-pro-preview`
- **Key params**: `temperature: 0.4`, `max_tokens: 8192` (mandatory — Gemini 3.1 Pro is a thinking model; small `max_tokens` causes hard 400 errors)
- **Do NOT** set `reasoning.exclude=true` — causes 400 errors with this model; use low reasoning effort instead
- Concurrency: `MAX_WORKERS = 4` (ThreadPoolExecutor), `MAX_CONSECUTIVE_ERRORS = 5` circuit breaker
- Retry: 3 attempts with 2-second sleep between them
- JSON extraction: `re.search(r'\[.*\]', text, re.DOTALL)` with per-record error fallback (LLM output can be non-JSON or truncated when `finish_reason=length`)

## Data Formats

- Generation outputs: `.json` arrays of `{ "uuid", "text", "question", "reasoning" }`
- Label Studio inputs: `.json` / `.jsonl` in `annotation/ls_input/`
- Few-shot example files: `level{N}_questions.json` (built by `generate_level{N}_json.py` scripts at root)
- Resume support: generation scripts skip UUIDs already present in the output file

## What Is NOT Versioned

- `data_prep/original_data_sets/` — large local corpora (Wikipedia, Israel HaYom, Knesset)
- `human-signal-dashboard/` — local monitoring tool clone
- All `.venv/` directories
- `.env` — secrets file

## Prompts

LLM prompts are stored as Markdown in `data_prep/prompts/`:
- `01_knesset_summaries.md` — summarization
- `02_question_generation.md` — question generation
- `03_question_assessment.md` — LLM evaluation/scoring
