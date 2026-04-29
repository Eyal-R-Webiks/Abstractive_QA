# data_prep

Data preparation, question generation, LLM evaluation, and annotation-prep workspace for the Hebrew Abstractive QA pipeline.

## Structure

```
data_prep/
├── README.md
├── summarize_knesset_gemini-3.1-pro-preview.py
├── generate_questions_gemini-3.1-pro-preview.py
├── evaluation_4_models.py
├── prepare_label_studio_part1.py
├── generate_iaa_report.py
├── prompts/
│   ├── 01_knesset_summaries.md       # Summarization prompt
│   ├── 02_question_generation.md     # Question generation prompt
│   └── 03_question_assessment.md     # LLM evaluation / scoring prompt
├── questions/
│   ├── docs_sampled/                 # Sampled source documents per corpus
│   ├── generation/                   # Raw question generation outputs
│   └── eval/
│       ├── all_questions_eval._input.jsonl   # Input to evaluation pipeline
│       ├── all_questions_eval_scored.json    # Consolidated scored output
│       └── output_per_model/                # Per-model JSONL outputs
│           ├── all_questions_for_eval_eval_claude_3_7_sonnet_eval.jsonl
│           ├── all_questions_for_eval_eval_gemini_3_1_pro_eval.jsonl
│           ├── all_questions_for_eval_eval_gpt_5_4_mini_eval.jsonl
│           ├── all_questions_for_eval_eval_gpt_5_5_pro_eval.jsonl
│           ├── all_questions_for_eval_eval_mistral_large_2407_eval.jsonl
│           └── run_log.txt
├── original_data_sets/               # Local corpora (large; not in git)
│   ├── il-hym/
│   ├── knesset/
│   └── wiki/
└── reports/
    └── question_llm_eval_iaa_report.html
```

## Script Roles

### `summarize_knesset_gemini-3.1-pro-preview.py`
Produces concise summaries from Knesset source material for downstream question generation.

### `generate_questions_gemini-3.1-pro-preview.py`
Generates Hebrew questions from document excerpts using the prompt in `prompts/02_question_generation.md`.

### `evaluation_4_models.py`
Evaluates each question with four OpenRouter LLMs in parallel.
- **System prompt:** `prompts/03_question_assessment.md`
- **Input:** `questions/eval/all_questions_eval._input.jsonl`
- **Per-model output:** `questions/eval/output_per_model/*.jsonl`
- **Consolidated output:** `questions/eval/all_questions_eval_scored.json`
- **Run log:** `questions/eval/output_per_model/run_log.txt`

### `prepare_label_studio_part1.py`
Joins scored question data with source document text and outputs a Label Studio–ready JSON task file to `../annotation/ls_input/`.

### `generate_iaa_report.py`
Computes inter-annotator agreement (IAA) metrics across all model evaluations and renders an HTML report to `reports/question_llm_eval_iaa_report.html`.

## Notes

- `original_data_sets/` is not versioned (large local corpora).
- API credentials go in the root `.env` file.
- Smoke or ad-hoc run artifacts go under the repository-root `smoke_tests/` folder.
