## Plan: Completion-Compatible Answer Generation

Goal: make answer generation produce artifacts that can be transformed into the exact flat schema used by /Users/eyalrosenstein/Documents/Abstractive_QA/Answers/annotation/completion_round_ls_input.json, with deterministic post-processing and no manual edits.

**Steps**
1. Define target contract from completion schema (blocking):
   required flat keys per record are: text, level, answer, claims, corpus, doc_id, source, dataset, category, question, _warnings, meta_html, reasoning, record_id, text_html, claims_html, level_label, unanswerable, _generation_seconds, expected_location_hint.
2. Lock generator output contract in /Users/eyalrosenstein/Documents/Abstractive_QA/Answers/generation/round4/generate_answers.py (depends on 1):
   generator must always emit record_id, source, doc_id, question, reasoning, answer, unanswerable, expected_location_hint, claims, _generation_seconds.
3. Make prompt contract strict and minimal (depends on 2):
   input text is already sentence-numbered; the model must emit claims as structured JSON objects with sentence_ids taken directly from those numbers (no post-hoc sentence-id inference); for this pipeline unanswerable=false and expected_location_hint=null unless explicitly running a level-0 mode.
4. Add a deterministic completion-builder stage (depends on 2,3):
   implement or reuse builder logic from /Users/eyalrosenstein/Documents/Abstractive_QA/Answers/generation/round1/build_ls_input.py (and /Users/eyalrosenstein/Documents/Abstractive_QA/Answers/experiment/build_ls_input.py) to construct the missing completion fields:
   corpus/dataset/category/level/text from question input file,
   source as empty string,
   level_label/meta_html,
   text_html from numbered text,
   claims_html from claims.
5. Enforce a consistency rule between claims and claims_html (depends on 4):
   claims_html must be generated only from claims in the same run; do not carry forward stale claims_html. This prevents mismatches like existing entries where claims has sentence_ids but claims_html shows "משפטים: —".
6. Add schema and quality validation gate before writing completion file (depends on 4,5):
   fail record if required key missing, wrong type, empty answer on non-unanswerable, claim without claim text, or sentence_ids not present in text numbering.
7. Run flow per level and write a fresh standalone completion file (depends on 6):
   run generation on input_level1.json and input_level2.json,
   run completion-builder for each output,
   concatenate and dedupe by record_id,
   write to a new round4 completion artifact (do not read/merge existing completion_round_ls_input.json).

**Relevant files**
- /Users/eyalrosenstein/Documents/Abstractive_QA/Answers/annotation/completion_round_ls_input.json — target schema to match exactly.
- /Users/eyalrosenstein/Documents/Abstractive_QA/Answers/generation/round4/generate_answers.py — raw answer generation stage.
- /Users/eyalrosenstein/Documents/Abstractive_QA/Answers/generation/round4/answer_generation_prompt.md — claim/sentence_ids behavior contract.
- /Users/eyalrosenstein/Documents/Abstractive_QA/Answers/generation/round4/input_level1.json — source fields for level/text/doc metadata.
- /Users/eyalrosenstein/Documents/Abstractive_QA/Answers/generation/round4/input_level2.json — source fields for level/text/doc metadata.
- /Users/eyalrosenstein/Documents/Abstractive_QA/Answers/generation/round4/answers_generated_level1.json — generated raw answers level 1.
- /Users/eyalrosenstein/Documents/Abstractive_QA/Answers/generation/round4/answers_generated_level2.json — generated raw answers level 2.
- /Users/eyalrosenstein/Documents/Abstractive_QA/Answers/generation/round1/build_ls_input.py — canonical rendering and field assembly pattern.
- /Users/eyalrosenstein/Documents/Abstractive_QA/Answers/experiment/build_ls_input.py — alternate canonical builder.

**Verification**
1. Schema check: every output record contains all completion keys and correct types.
2. Citation check: each claim sentence_id exists in the numbered text.
3. Rendering check: text_html contains sentence-number spans; claims_html lists sentence ids (not "—") when claims include sentence_ids.
4. Output integrity check: record_id uniqueness in the new file and stable counts per level.
5. Spot QA: sample 5 records and compare answer vs claims vs highlighted text_html.

**Decisions**
- Primary mode: non-level0 only (unanswerable=false, expected_location_hint=null).
- source remains empty string in completion schema; corpus stores actual source.
- Build claims_html exclusively from claims to avoid divergence.
- Output policy: create a new standalone round4 completion file; do not merge into existing completion_round_ls_input.json.

**Further Considerations**
1. Decide output filename convention (for example: completion_round4_ls_input.json) and whether to version by timestamp.
2. If future level-0 returns, decide whether to re-enable unanswerable path in prompt and claims_html rendering.
3. Add one command entrypoint script under round4 to run generate + build + validate in one reproducible step.