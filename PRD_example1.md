# PRD: Data Generation Module for RLHF Annotation Campaign

**Version:** 0.2 (Draft)
**Date:** March 2, 2026
**Status:** Draft

---

## 1. Overview

A data generation module that takes pre-translated Hebrew seed prompts (with pre-computed DictaLM completions), dispatches them to randomly selected LLMs via OpenRouter, and produces structured `.json` output files ready for import into Label Studio for human annotation in two RLHF tasks: **Refining** and **Preference**.

---

## 2. Key Requirements (Extracted from SOW)

### 2.1 Input: Seed Prompts
- Source: Two JSONL files (one per task type), already translated to Hebrew, with pre-computed DictaLM-3.0 completions.
- **Preference file:** ~115,931 records.
- **Refine file:** ~44,561 records (strict subset of Preference — intentional, use as-is).
- Each record contains: `id`, `prompt` (Hebrew), `original_prompt` (English), `dicta_lm3_completion` (`reasoning` + `text`).
- **No deduplication or filtering** — input files are used as-is. Some records will be skipped later at annotation time.
- 21 duplicate IDs exist in Preference, 2 in Refine — kept as-is.

### 2.2 Two Task Types

| | Task 1 — Refining | Task 2 — Preference |
|---|---|---|
| **Goal** | Annotator edits a single LLM response for spelling, grammar, tone, naturalness | Annotator picks the preferred response out of two |
| **Rating scale task 2** | Free-text edit | 5-point: Strong A / Slight A / Both Good / Both Bad / Slight B / Strong B |
| **Edit on preferred** | — | If preferred answer has minor errors, annotator may also edit it |



### 2.3 LLM Pool & Dispatch Logic
- Pre-defined set of open models served by https://openrouter.ai/. List is **configurable**.
- Current models pool:
    - DictaLM-3.0-24B-Thinking
    - https://openrouter.ai/minimax/minimax-m2.5
    - https://openrouter.ai/deepseek/deepseek-v3.2
    - https://openrouter.ai/moonshotai/kimi-k2-0905
    - https://openrouter.ai/z-ai/glm-5
    - https://openrouter.ai/qwen/qwen3.5-397b-a17b
    - https://openrouter.ai/google/gemma-3-27b-it
    - https://openrouter.ai/openai/gpt-oss-120b
    - https://openrouter.ai/mistralai/mistral-large-2512
- **Model selection:** Random from the pool for each response.
- **DictaLM optimization:** If the randomly selected model is DictaLM, use the pre-computed `dicta_lm3_completion` from the input record instead of calling the API. This saves cost and latency.
- **Preference task:** Two **distinct** models are randomly selected (must not be the same model). Each generates one response.
- Module must record which model produced each response.

### 2.5a Output Record Structure — Refining Task

| Field | Description |
|-------|-------------|
| `task_type` | `"refining"` |
| `original_prompt` | The seed prompt as served |
| `model_id` | Model that generated the response |
| `model_response_original` | Raw model output |
| `model_reasoning` | Model's chain-of-thought / reasoning (for traceability) |
| `edited_response` | Annotator's corrected / refined version of the response |


### 2.5b Output Record Structure — Preference Task

| Field | Description |
|-------|-------------|
| `task_type` | `"preference"` |
| `original_prompt` | The seed prompt as served |
| `corrected_prompt` | Annotator-modified prompt (if changed; `null` otherwise) |
| `model_id_a` | Model that generated Response A |
| `model_id_b` | Model that generated Response B |
| `response_a` | Raw output from Model A |
| `reasoning_a` | Model A's chain-of-thought / reasoning (for traceability) |
| `response_b` | Raw output from Model B |
| `reasoning_b` | Model B's chain-of-thought / reasoning (for traceability) |
| `preference_label` | One of: `strong_a` / `slight_a` / `both_good` / `both_bad` / `slight_b` / `strong_b` |



---

## 3. Module Scope (What This Module Builds)

1. **Prompt ingestion** — load JSONL input files as-is (no dedup/filter).
2. **LLM dispatch** — for each record, randomly select 1 model (Refine) or 2 distinct models (Preference) from the pool. If DictaLM is selected, reuse the pre-computed completion; otherwise call OpenRouter API.
3. **Response packaging** — bundle prompt, response(s), reasoning, metadata into annotation-ready records.
4. **Output file generation** — write structured `.json` files in Label Studio import format (see §4).

### 3.1 CLI & Execution Model

- **Single-task per run.** Each invocation processes exactly one task type (`refine` or `preference`) — never both.
- **Batch processing.** Each run processes a contiguous slice of the input file. The user specifies `--start` (0-based record index) and `--count` (number of records) on every run. There is no default batch size.
- **One output file per run.** Each run produces a single self-contained `.json` file (e.g., `preference_0_5000.json`) that can be imported directly into Label Studio as-is.
- **Cumulative imports.** Successive batch runs produce separate files. Each file is imported independently into the same Label Studio project — no append/merge logic needed.
- **Checkpoint file.** A per-task checkpoint (`checkpoint_preference.json`, `checkpoint_refine.json`) tracks which record ranges have been processed and which output files were produced, enabling easy resume and auditability.

---

## 4. Label Studio Import Schema

The output `.json` files must be directly importable into Label Studio. Each file is a JSON array of objects, where each object represents one annotation task. The `data` block contains all pre-task fields generated by this module. Annotation fields are captured by Label Studio at annotation time.

### 4.1 Refining Task — Label Studio Record

```json
{
  "data": {
    "task_type": "refining",
    "original_prompt": "<Hebrew prompt>",
    "model_id": "<model name>",
    "model_response_original": "<raw model output text>",
    "model_reasoning": "<chain-of-thought reasoning>"
  }
}
```

Label Studio labeling config will capture:
- `edited_response` — free-text area pre-filled with `model_response_original` for the annotator to edit.

### 4.2 Preference Task — Label Studio Record

```json
{
  "data": {
    "task_type": "preference",
    "original_prompt": "<Hebrew prompt>",
    "model_id_a": "<model A name>",
    "response_a": "<raw output from model A>",
    "reasoning_a": "<model A chain-of-thought>",
    "model_id_b": "<model B name>",
    "response_b": "<raw output from model B>",
    "reasoning_b": "<model B chain-of-thought>"
  }
}
```

Label Studio labeling config will capture:
- `preference_label` — 6-choice radio: `strong_a` / `slight_a` / `both_good` / `both_bad` / `slight_b` / `strong_b`.

### 4.3 Label Studio Notes
- All `data.*` fields are **pre-task** (generated by this module).
- Annotation fields (`edited_response`, `preference_label`) are filled at annotation time — NOT part of this module's output.
- `model_id*`, `reasoning*`, `model_reasoning` fields should be **hidden from annotators** in the UI (used for traceability/QA only).
- `annotation_time_sec` is auto-tracked by Label Studio's built-in lead time — no need to include it in the data schema.
- Each CLI run produces one output file. Files are imported individually into a Label Studio project (one import per batch). Batch size is determined per run.

---

## 5. Out of Scope

- The annotation UI / labeling platform itself.
- Annotator recruitment, testing, and management.
- Reward model training.
- RLHF training loop.
- Translation of English prompts (client responsibility).

---

## 6. Timeline

| Milestone | Target | Notes |
|-----------|--------|-------|
| PRD finalized | TBD | |
| Design Review (DR) | T + 7 days from contract | Present: data sources, sample annotations, annotation pace estimate, output format |
| First annotation batch | TBD | |
| Preference checkpoint (5–8K) | TBD | Joint review to validate signal quality |

---
