# PRD: Continuous Conversation Preference Tagging

**Version:** 0.3
**Date:** April 9, 2026
**Status:** Draft

---

## Terminology

- **Task** — A single Label Studio record. In this project, each task asks the annotator to judge **one turn** of a conversation.
- **Annotation** — The labels an annotator submits for a single task (one preference judgment + conversation context).
- **Sub-annotation** — Not used in the iterative approach. Each annotation round is a standalone annotation on one turn, but sub-annotations within a round could refer to individual fields (preference label, optional edit, etc.).
- **Turn** — One round of the conversation: a user prompt followed by two competing model responses (A and B).
- **Round** — One full cycle of the iterative pipeline: generate data for turn N → import into Label Studio → annotators complete annotations → export results. Each round produces the input needed for the next round.
- **Conversation** — The full multi-turn thread built up across rounds. A conversation designated for 4 turns participates in rounds 1–4.

---

## 1. Overview

Extend the RLHF annotation campaign with a **multi-turn conversation preference task** using an **iterative, round-by-round approach**. Instead of pre-generating entire conversations upfront, each turn is generated, annotated by humans, and then the **human-selected preferred answer** is used as context to generate the next turn's follow-up question and model responses.

This creates a human-in-the-loop conversation pipeline:

1. **Turn 1** is already annotated — sourced from 5,000 existing records in the single-turn preference project.
2. **Round 1** generates turn 2 for all 5,000 conversations → annotators annotate turn 2 only → 2,000 conversations (2-turn) are complete.
3. **Round 2** generates turn 3 for the remaining 3,000 → annotators annotate turn 3 only → 1,500 conversations (3-turn) are complete.
4. **Round 3** generates turn 4 for the remaining 1,500 → annotators annotate turn 4 only → 1,000 conversations (4-turn) are complete.
5. **Round 4** generates turn 5 for the remaining 500 → annotators annotate turn 5 only → all conversations are complete.

Each round is imported into a **new, dedicated Label Studio project** (or as a new batch in the same project). Annotators only see and annotate the **current turn** — previous turns are displayed as read-only context.

---

## 2. Volume & Turn Distribution

**Total conversations:** 5,000 (randomly sampled from the existing ~115K preference corpus, already annotated for turn 1)

- **2 turns** — 40% → 2,000 conversations (done after round 1)
- **3 turns** — 30% → 1,500 conversations (done after round 2)
- **4 turns** — 20% → 1,000 conversations (done after round 3)
- **5 turns** — 10% → 500 conversations (done after round 4)

**Annotations per round:**

- **Round 1 (turn 2):** 5,000 annotations
- **Round 2 (turn 3):** 3,000 annotations
- **Round 3 (turn 4):** 1,500 annotations
- **Round 4 (turn 5):** 500 annotations
- **Total:** 10,000 annotations across all rounds

---

## 3. Conversation Generation Architecture

### 3.1 Iterative Per-Round Flow

```
── Turn 1 (already annotated) ──────────────────────────────────

  Existing single-turn preference project provides:
    - seed_prompt
    - response_a_1, response_b_1
    - preference_label_1 (human annotation)

── Round 1: Generate turn 2 ────────────────────────────────────

  For each of the 5,000 conversations:

  1. Determine preferred answer from turn 1 annotation:
     - strong_a / slight_a  →  use response_a_1
     - strong_b / slight_b  →  use response_b_1
     - both_good / both_bad →  use BOTH responses as context

  2. Follow-up LLM sees [seed_prompt, preferred_answer(s)]
     → generates follow_up_1

  3. Pick 2 new distinct models from the full pool (including DictaLM)
     Model C responds to [seed_prompt, follow_up_1]  → response_a_2
     Model D responds to [seed_prompt, follow_up_1]  → response_b_2

  4. Package as Label Studio task (turn 2 only, with turn 1 as context)
     → annotators provide preference_label_2

  After annotation: 2,000 conversations (2-turn) are complete.

── Round 2: Generate turn 3 ────────────────────────────────────

  For the remaining 3,000 conversations:

  1. Determine preferred answer from turn 2 annotation
  2. Follow-up LLM sees [seed_prompt, ..., preferred_answer_2]
     → generates follow_up_2
  3. Pick 2 new distinct models
     → response_a_3, response_b_3
  4. Annotators provide preference_label_3

  After annotation: 1,500 conversations (3-turn) are complete.

── Rounds 3–4: same pattern for turns 4 and 5 ─────────────────
```

### 3.2 Key Design Decisions

**Iterative human-in-the-loop** → Each turn builds on real human preference judgments from the previous turn, not synthetic or pre-generated paths. This produces higher-quality, more natural conversations.

**Follow-up context** → Generated from the **human-annotated preferred answer**. When the annotation is `both_good` or `both_bad`, both responses are provided as context to the follow-up LLM. This eliminates the A-path bias problem entirely — the follow-up is always grounded in the human's actual choice.

**Fresh model pair per turn** → 2 new distinct models are randomly selected at each round from the **full model pool** (all 9 models including DictaLM). This maximizes model diversity across the dataset.

**DictaLM via API for turns 2–5** → The pre-computed DictaLM completions only cover the original single-turn prompts (turn 1, which is already annotated). For turns 2–5, DictaLM is called via API like any other model. No special handling needed.

**Single-turn annotation per round** → Annotators only annotate the new turn in each round. Previous turns are shown as read-only conversation history for context. This keeps annotation effort per task low and consistent.

### 3.3 Follow-Up Context Rules

How the follow-up LLM receives context from the previous turn's annotation:

- **`strong_a` or `slight_a`** → Follow-up LLM sees the conversation history ending with response A only.
- **`strong_b` or `slight_b`** → Follow-up LLM sees the conversation history ending with response B only.
- **`both_good` or `both_bad`** → Follow-up LLM sees the conversation history ending with both responses (formatted as "Response 1: ... / Response 2: ..."). The follow-up should be a natural continuation that works regardless of which answer was given.

---

## 4. Data Models

### 4.1 Round Input Record

Each round's generation pipeline reads from:
- The original seed prompts (for conversation history)
- The exported annotations from the previous round

### 4.2 Label Studio Record (Per-Round Task)

Each task in a round contains the full conversation history (read-only) plus the new turn to annotate:

```json
{
  "data": {
    "task_type": "conversation_preference",
    "conversation_id": "conv_00001",
    "original_prompt_id": "12345",
    "current_turn": 2,
    "total_designated_turns": 3,

    "turn_1_user_prompt": "<seed prompt>",
    "turn_1_response_a": "<Model A turn 1>",
    "turn_1_response_b": "<Model B turn 1>",
    "turn_1_preference": "strong_a",
    "turn_1_model_id_a": "<model name>",
    "turn_1_model_id_b": "<model name>",

    "turn_2_user_prompt": "<generated follow-up>",
    "turn_2_response_a": "<Model C turn 2>",
    "turn_2_reasoning_a": "<...>",
    "turn_2_response_b": "<Model D turn 2>",
    "turn_2_reasoning_b": "<...>",
    "turn_2_model_id_a": "<model name>",
    "turn_2_model_id_b": "<model name>",

    "followup_model_id": "<follow-up LLM>"
  }
}
```

For round 3, the record would include `turn_1_*`, `turn_2_*` (both read-only with their preferences), and `turn_3_*` (to annotate). The pattern extends the same way for rounds 3 and 4.

**Note:** Fields are flattened to `turn_N_*` because Label Studio works best with flat `data.*` fields.

---

## 5. Label Studio Project Setup

### 5.1 Project Structure

Each annotation round is imported into a **new Label Studio project** (or as a distinct batch in a shared project):

- **Round 1 project:** `Conversation Preference — Turn 2` (5,000 tasks)
- **Round 2 project:** `Conversation Preference — Turn 3` (3,000 tasks)
- **Round 3 project:** `Conversation Preference — Turn 4` (1,500 tasks)
- **Round 4 project:** `Conversation Preference — Turn 5` (500 tasks)

Using separate projects per round keeps the labeling config simple (each config only needs to handle one new turn) and avoids complex conditional visibility logic.

### 5.2 Labeling Interface Design (Per-Round)

Each round's labeling interface shows:

**Read-only conversation history** (all previous turns):
- Each previous turn displayed as a collapsed or styled block showing: user prompt → preferred response (the one selected by the annotator in the prior round). Model IDs hidden.

**Current turn to annotate:**
1. **Follow-up question** — displayed as the user's message (RTL).
2. **Response A / Response B** — side-by-side columns (RTL). Model IDs hidden.
3. **Preference radio** — 6 options: `Strong A / Slight A / Both Good / Both Bad / Slight B / Strong B`.

### 5.3 Hidden Fields

The following fields are included in the data but **hidden from annotators** (used for traceability/QA):
- All `turn_N_model_id_a`, `turn_N_model_id_b`, `followup_model_id`
- All `turn_N_reasoning_a`, `turn_N_reasoning_b`
- `original_prompt_id`, `conversation_id`

---

## 6. Follow-Up LLM Selection (Quick Eval)

**Constraint:** Must complete within ~2 hours (scripted generation + quick review).

### 6.1 Protocol

- **Candidates:** 3 models — GPT-4.1, Claude Sonnet 4, Qwen 3.5
- **Test set:** 10 seed prompts (hand-picked for diversity: factual, creative, technical, conversational)
- **Templates:** 2 prompt templates per candidate (see §6.2)
- **Total calls:** 10 × 3 × 2 = 60
- **Evaluation:** 1 Hebrew-speaking reviewer rates all 60 follow-ups on naturalness (1–5), relevance (1–5), and diversity (1–5). Takes ~1 hour.
- **Decision:** Pick the best (model, template) combo by average score. Ties broken by cost.

### 6.2 Candidate Prompt Templates

**Template A (role-play):**
```
You are a curious Hebrew-speaking user having a conversation with an AI assistant.
Given the conversation so far, write a natural follow-up question or request in Hebrew.
The follow-up should be a logical continuation — it can ask for clarification, go deeper
into the topic, or pivot to a related aspect. Keep it concise (1–3 sentences).
Write ONLY the user's follow-up message. Do not include any meta-commentary.

Conversation so far:
User: {user_prompt}
Assistant: {assistant_response}
```

**Template B (instruction-based):**
```
Given the following Hebrew conversation between a user and an AI assistant,
generate the user's next message. The message should feel natural and
conversational in Hebrew. It should logically follow from the assistant's
last response.

Rules:
- Write in Hebrew only
- 1–3 sentences
- Be specific, not generic
- Output ONLY the user's message

{conversation_history}
```

---

## 7. Implementation Plan

The implementation is **iterative by design** — each round follows the same pipeline steps, repeated 4 times with decreasing task counts.

### 7.1 One-Time Setup (Day 1)

**Follow-up LLM eval + tooling**

- **Notebook 1 — Follow-up LLM quick-eval:** Script 60 API calls (3 candidates × 2 templates × 10 prompts). 1 Hebrew-speaking reviewer scores them (~1h). Pick the winner.
- **Notebook 2 — Sampling & manifest:** From the existing single-turn preference project, randomly sample 5,000 annotated records. Assign each a designated total turn count per the 40/30/20/10 distribution. Save the manifest (conversation_id, original_prompt_id, turn 1 data + annotation, designated_turns) to a JSON file.
- **Notebook 3 — Round pipeline template:** Build the reusable per-round generation notebook:
  1. Read the manifest + previous round's annotations.
  2. Filter to conversations that need another turn.
  3. Determine preferred answer per the context rules (§3.3).
  4. Generate follow-up questions via the selected follow-up LLM.
  5. Pick 2 fresh models per conversation, dispatch both.
  6. Package into Label Studio import format.
  7. Checkpoint support for resume on failure.
- **Label Studio config:** Build the labeling XML config for each round type. Test import with a small sample.

**Day 1 deliverable:** Follow-up model selected. 5K manifest ready. Pipeline notebook + Label Studio configs built and tested.

### 7.2 Per-Round Cycle (Repeats 4 times)

Each round follows the same sequence:

1. **Generate** — Run the pipeline notebook for the current round. Generate follow-up questions + model responses for all conversations in scope.
2. **QA** — Spot-check 20–30 tasks. Verify follow-up coherence, response quality, Hebrew correctness.
3. **Import** — Import the round's tasks into the Label Studio project.
4. **Annotate** — Annotators complete the round (timeline depends on annotator availability).
5. **Export** — Export annotations from Label Studio. Feed into the next round.

**Estimated generation + QA + import time per round:** ~half a day (the annotation step depends on annotator bandwidth and is outside this module's scope).

### 7.3 Round Schedule Summary

- **Round 1 (turn 2):** 5,000 tasks. ~5,000 follow-up calls + ~10,000 model response calls.
- **Round 2 (turn 3):** 3,000 tasks. ~3,000 follow-up calls + ~6,000 model response calls.
- **Round 3 (turn 4):** 1,500 tasks. ~1,500 follow-up calls + ~3,000 model response calls.
- **Round 4 (turn 5):** 500 tasks. ~500 follow-up calls + ~1,000 model response calls.
- **Total API calls:** ~10,000 follow-up + ~20,000 model response = ~30,000 calls.

---

## 8. Open Questions for Review

### 8.1 Label Studio Project Structure

Should each round be a **separate Label Studio project**, or should all rounds be imported into the **same project** with different task batches? Separate projects keep configs simple; a single project keeps everything in one place.

### 8.2 Conversation History Display

How much of the previous conversation should annotators see? Options:
- **Only the preferred response** from each prior turn (clean, simple).
- **Both responses + the preference label** from each prior turn (more context, but cluttered).

**Recommendation:** Show only the preferred response — it matches the "real" conversation the user would have had.

### 8.3 Model Pool

DictaLM is included in the model pool for turns 2–5 and called via API (the pre-computed completions only cover turn 1). Need to confirm DictaLM API access is available and supports multi-turn chat format.

### 8.4 Both-Good / Both-Bad Follow-Up Format

When the previous turn's annotation is `both_good` or `both_bad`, both responses are passed to the follow-up LLM. Exact formatting TBD — e.g., "The assistant gave two responses: [Response 1] ... [Response 2] ..." vs. picking one at random. Need to test which produces better follow-ups during the quick-eval.

---

## 9. Risks & Mitigations

**Follow-up questions feel unnatural** (medium likelihood, high impact)
→ Quick-eval on Day 1; QA at each round; prompt iteration if needed.

**Annotation bottleneck between rounds** (medium likelihood, high impact)
→ Rounds are blocked on annotator throughput. Prioritize round 1 (largest batch). Later rounds are smaller and faster.

**Conversation coherence degrades at turns 4–5** (medium likelihood, medium impact)
→ QA specifically targets later-round conversations (4–5 turns). Can regenerate if systematic.

**Label Studio export format issues between rounds** (low likelihood, medium impact)
→ Validate export → ingest pipeline on a small batch before each round.

**Both-good/both-bad context confuses follow-up LLM** (low likelihood, low impact)
→ Test formatting during quick-eval; fallback to picking one response at random.

---

## 10. Out of Scope

- The annotation UI platform itself (Label Studio is pre-existing).
- Annotator recruitment and management.
- Annotation timelines (depends on annotator availability).
- Reward model training on conversation data.
- Translation — all prompts are already in Hebrew.
- Modifications to the existing single-turn preference pipeline.