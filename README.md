# Abstractive_QA

Workspace for building a Hebrew **Abstractive QA** benchmark dataset of 1,000 question–answer pairs, sourced from three native-Hebrew corpora (Wikipedia, Israel HaYom, Knesset protocols). Questions are classified by cognitive difficulty (levels 0–3) based on Bloom's Taxonomy, and are intended for benchmarking LLM answer quality on the MAFAT/Dicta leaderboard.

See [`PRD.md`](PRD.md) for the full project specification.

## Repository Layout

```
Abstractive_QA/
├── PRD.md
├── README.md
├── annotation/                          # Human annotation artifacts
│   ├── all_questions_for_humans.csv     # Flat CSV view for annotators
│   ├── guidelines/                      # Annotation guidelines (docx / pdf / md)
│   ├── ls_input/                        # Label Studio import tasks (JSON)
│   └── ls_scripts/                      # Label Studio config XML
├── data_prep/
│   ├── README.md
│   ├── summarize_knesset_gemini-3.1-pro-preview.py
│   ├── generate_questions_gemini-3.1-pro-preview.py
│   ├── evaluation_4_models.py
│   ├── prepare_label_studio_part1.py    # Builds Label Studio task JSON
│   ├── generate_iaa_report.py           # Generates inter-annotator agreement report
│   ├── prompts/
│   │   ├── 01_knesset_summaries.md
│   │   ├── 02_question_generation.md
│   │   └── 03_question_assessment.md
│   ├── questions/
│   │   ├── docs_sampled/                # Sampled source documents per corpus
│   │   ├── generation/                  # Raw question generation outputs
│   │   └── eval/
│   │       ├── all_questions_eval._input.jsonl   # Evaluation input
│   │       ├── all_questions_eval_scored.json    # Consolidated scored output
│   │       └── output_per_model/                # Per-model JSONL outputs
│   ├── original_data_sets/              # Local corpora (large; not in git)
│   │   ├── il-hym/
│   │   ├── knesset/
│   │   └── wiki/
│   └── reports/
│       └── question_llm_eval_iaa_report.html
├── resources/
│   ├── Bloom_taxonomy/
│   ├── MAFAT_requirements_doc.md
│   ├── llms_bloom_summary.html
│   └── chunks_for_RAG/
└── smoke_tests/                         # Ad-hoc / smoke-run artifacts
```

## Main Scripts

| Script | Purpose |
|--------|---------|
| `data_prep/summarize_knesset_gemini-3.1-pro-preview.py` | Build short summaries from Knesset source materials |
| `data_prep/generate_questions_gemini-3.1-pro-preview.py` | Generate Hebrew questions from excerpts/summaries |
| `data_prep/evaluation_4_models.py` | Evaluate questions with 4 OpenRouter LLMs; write per-model JSONL + consolidated JSON |
| `data_prep/prepare_label_studio_part1.py` | Join question + document data into Label Studio import format |
| `data_prep/generate_iaa_report.py` | Compute IAA metrics across model evaluations and render HTML report |

## Important Notes

- `data_prep/original_data_sets/` is not versioned (large local corpora).
- API credentials go in the root `.env` file.
- Smoke or ad-hoc test artifacts go under `smoke_tests/`.
