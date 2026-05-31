# Abstractive_QA

Workspace for building a Hebrew **Abstractive QA** benchmark dataset of 100 curated question–answer pairs, sourced from three native-Hebrew corpora (Wikipedia, Israel HaYom, Knesset protocols). Questions are classified by cognitive difficulty (levels 0–2) based on Bloom's Taxonomy, and are intended for benchmarking LLM answer quality on the MAFAT/Dicta leaderboard.

See [`PRD.md`](PRD.md) for the full project specification.

## Project Status

**Part 1 — Question filtering in progress.** LLM-generated questions (Levels 0–2) have been produced across all three corpora. Human annotators are currently validating question levels in Label Studio. 100 questions will be selected from the validated pool for the final dataset.

**Part 2 — Pending.** LLM-generated answers to the 100 selected questions will be evaluated and corrected by human annotators.

## Repository Layout

```
Abstractive_QA/
├── PRD.md                              # Full project specification
├── README.md
├── AGENTS.md                           # Copilot agent instructions
├── add_sentence_numbers.py             # Add numbered sentences to task HTML
├── check_openrouter_balance.py         # Check remaining OpenRouter credit
├── ls_auth.py                          # Label Studio auth helper (refresh token)
├── ls_snapshot_structure.md            # Reference: LS export JSON schema
├── prepare_ls_input.py                 # Build Label Studio import task files
├── Questions/
│   ├── annotation/
│   │   ├── guidelines/                 # Annotation guidelines (docx / pdf / md)
│   │   └── ls_input/                   # Label Studio import task JSONs
│   ├── data_prep_new/
│   │   ├── docs_sampled_new/           # Sampled source documents
│   │   │   ├── Il-hym/
│   │   │   ├── knesset_short/
│   │   │   └── wiki/
│   │   ├── experiment/                 # Generation outputs and inputs (round 1)
│   │   ├── human-question-writing/     # Human-written reference questions
│   │   ├── round_2/                    # Second generation round
│   │   └── round_3/                    # Third generation round (current)
│   ├── human-signal-dashboard/         # Annotation monitoring dashboard
│   │   ├── cache/snapshot.json         # Cached Label Studio export
│   │   ├── scripts/                    # Agreement and export utilities
│   │   ├── start.py / start_alt.py     # Dashboard launchers
│   │   └── all_questions_output.jsonl  # Flattened annotation output
│   └── original_data_sets/             # Source corpora (large; not in git)
│       ├── il-hym/
│       ├── knesset/
│       └── wiki/
├── Reports/                            # Analysis and evaluation reports
└── Resources/
    ├── Bloom_taxonomy/                 # Research papers + RAG chunks
    └── project_info/                   # Guidelines, level definitions, MAFAT req doc
```

## Question Levels

| Level | Type | Description |
|-------|------|-------------|
| 0 | Unanswerable | Answer is absent from the document; correct model response is to say so |
| 1 | Retrieval | Answer is explicitly in a single sentence |
| 2 | Integration | Answer requires connecting 2–3 sentences from different parts of the text |

**Final target distribution:** 15 × L0, 40 × L1, 45 × L2 (100 total)

## Key Scripts

| Script | Purpose |
|--------|---------|
| `prepare_ls_input.py` | Build Label Studio import task JSON from generation outputs |
| `add_sentence_numbers.py` | Add numbered `<span>` tags to document HTML in tasks |
| `ls_auth.py` | Exchange LS refresh token for a short-lived access token |
| `check_openrouter_balance.py` | Check remaining OpenRouter credit balance |
| `Questions/data_prep_new/round_3/build_ls_input_round3.py` | Build round-3 LS input |
| `Questions/human-signal-dashboard/start_alt.py` | Launch monitoring dashboard (project 259584, port 8766) |

## Important Notes

- `Questions/original_data_sets/` is not versioned (large local corpora).
- API credentials go in the root `.env` file (`OPENROUTER_API_KEY`, `LS_REFRESH_TOKEN`).
- The human-signal dashboard is a separate git repo cloned into `Questions/human-signal-dashboard/`.
- Generation uses `google/gemini-3.1-pro-preview` via OpenRouter. See `AGENTS.md` for API conventions.
