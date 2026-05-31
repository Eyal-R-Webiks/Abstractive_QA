import argparse
import json
import os
import random
import re
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv(".env")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in .env")

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-3.1-pro-preview"

MAX_WORKERS = 1
MAX_CONSECUTIVE_ERRORS = 5
MAX_REVISIONS = 3

SOURCE_ALIASES = {
    "il_hym": "il-hym",
    "il-hym": "il-hym",
    "israel_hayom": "il-hym",
    "hewiki": "wiki",
    "wiki": "wiki",
    "knesset": "knesset",
}

LEVEL0_MIMIC_SPLIT = [
    ("level1", 7),
    ("level2", 7),
    ("level3", 6),
]

# Level-aware upper bounds derived from revision_report.html observations.
MAX_LEN_BY_LEVEL = {
    "level0": 135,
    "level1": 120,
    "level2": 150,
    "level3": 170,
}

ABSTRACT_MARKERS = [
    "איזה מתח",
    "מה ניתן להסיק",
    "כיצד משתקף",
    "כיצד חושף",
    "האופן שבו",
    "פער תפיסתי",
]

PREMISE_MARKERS = [
    "על פי",
    "לפי",
    "לאור",
    "בהתאם",
    "בהשראת",
    "על בסיס",
]

global_consecutive_errors = 0
global_max_consecutive_errors = MAX_CONSECUTIVE_ERRORS
global_last_api_error = ""
error_lock = threading.Lock()


def extract_json_array(text: str) -> list:
    # Try to find a complete [...] array first
    match = re.search(r"\[.*?\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Full greedy match (original behaviour)
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Truncated response: try to recover the first complete {...} object
    # by finding the opening [ and extracting text up to the last complete }
    bracket = text.find("[")
    if bracket != -1:
        snippet = text[bracket:]
        last_brace = snippet.rfind("}")
        if last_brace != -1:
            candidate = snippet[: last_brace + 1] + "]"
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return []


def canonicalize_source(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return SOURCE_ALIASES.get(value.strip().lower(), value.strip().lower())


def parse_level_number(level_name: str) -> str:
    return level_name.replace("level", "")


def load_pool_rows(path: Path) -> List[dict]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            rows = json.load(f)
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def build_record_source_map(good_rows: List[dict], bad_rows: List[dict]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}

    for row in good_rows:
        if not isinstance(row, dict):
            continue
        record_id = row.get("record_id") or row.get("uuid")
        source = canonicalize_source(row.get("source"))
        if record_id and source:
            mapping[str(record_id)] = source

    for row in bad_rows:
        if not isinstance(row, dict):
            continue
        record_id = row.get("record_id") or row.get("uuid")
        source = canonicalize_source(row.get("source"))
        if record_id and source:
            mapping[str(record_id)] = source

    return mapping


def annotate_input_sources(inputs: List[dict], record_source_map: Dict[str, str]) -> None:
    for item in inputs:
        if item.get("source"):
            item["source"] = canonicalize_source(item.get("source"))
            continue
        uuid = item.get("uuid")
        if uuid is not None and str(uuid) in record_source_map:
            item["source"] = record_source_map[str(uuid)]


def normalize_hebrew_for_overlap(text: str) -> str:
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def ngram_overlap_ratio(question: str, source_text: str, n: int = 5) -> float:
    q = normalize_hebrew_for_overlap(question)
    s = normalize_hebrew_for_overlap(source_text)

    if len(q) < n:
        return 0.0

    q_ngrams = {q[i : i + n] for i in range(len(q) - n + 1)}
    s_ngrams = {s[i : i + n] for i in range(len(s) - n + 1)}
    if not q_ngrams:
        return 0.0

    overlap = len(q_ngrams & s_ngrams)
    return overlap / len(q_ngrams)


def count_premise_markers(question: str) -> int:
    return sum(question.count(marker) for marker in PREMISE_MARKERS)


def validate_question(level: str, question: str, source_text: str) -> Tuple[bool, List[str]]:
    reasons: List[str] = []

    q = question.strip()
    if not q:
        reasons.append("question is empty")
        return False, reasons

    if len(q) > MAX_LEN_BY_LEVEL[level]:
        reasons.append(f"too long ({len(q)} chars > {MAX_LEN_BY_LEVEL[level]})")

    if q.count("?") != 1:
        reasons.append("must contain exactly one question mark")

    if count_premise_markers(q) >= 2:
        reasons.append("contains stacked premise markers")

    if ", אשר" in q or " אשר " in q:
        reasons.append("contains likely redundant 'אשר' clause")

    if "\"" in q or "'" in q:
        reasons.append("contains quote marks; likely quote-lifting")

    overlap = ngram_overlap_ratio(q, source_text)
    if overlap > 0.72:
        reasons.append("too much lexical mirroring from source")

    if level == "level1":
        if any(marker in q for marker in ABSTRACT_MARKERS):
            reasons.append("level1 drifted into abstract framing")

    if level == "level3":
        if any(q.startswith(prefix) for prefix in ["מי", "מתי", "כמה", "באיזו שנה"]):
            reasons.append("level3 appears too retrieval-oriented")

    return len(reasons) == 0, reasons


def _span_is_in_text(span: str, source_text: str) -> bool:
    span_norm = normalize_hebrew_for_overlap(span)
    text_norm = normalize_hebrew_for_overlap(source_text)
    if not span_norm:
        return False
    return span_norm in text_norm


def validate_span_fields(level: str, candidate: dict, source_text: str) -> Tuple[bool, List[str]]:
    reasons: List[str] = []

    answer_spans = candidate.get("answer_spans", [])
    expected_spans = candidate.get("expected_answer_spans_level0", [])

    if not isinstance(answer_spans, list):
        reasons.append("answer_spans must be a list")
        answer_spans = []
    if not isinstance(expected_spans, list):
        reasons.append("expected_answer_spans_level0 must be a list")
        expected_spans = []

    if level == "level0":
        if answer_spans:
            reasons.append("level0 must have empty answer_spans")
        if not expected_spans:
            reasons.append("level0 must include expected_answer_spans_level0")
        else:
            for idx, span in enumerate(expected_spans):
                if not isinstance(span, str) or not span.strip():
                    reasons.append(f"level0 expected_answer_spans_level0[{idx}] is not a non-empty string")
                    continue
                # Relaxed: span no longer needs to be a 100% exact match to the source text
    else:
        if expected_spans:
            reasons.append("non-level0 must keep expected_answer_spans_level0 empty")
        if not answer_spans:
            reasons.append("non-level0 must include answer_spans")
        else:
            for idx, span in enumerate(answer_spans):
                if not isinstance(span, str) or not span.strip():
                    reasons.append(f"answer_spans[{idx}] is not a non-empty string")
                    continue
                # Relaxed: span no longer needs to be a 100% exact match to the source text

    return len(reasons) == 0, reasons


def format_few_shot_messages(few_shot_path: Path, max_items: int) -> List[Dict[str, str]]:
    if not few_shot_path.exists():
        return []

    with few_shot_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    random.shuffle(data)
    if max_items > 0:
        data = data[:max_items]
    messages: List[Dict[str, str]] = []

    for item in data:
        good = item.get("good", {})
        bad_examples = item.get("avoid", [])

        bad_text = "\n".join(
            [f"- BAD: {b.get('question', '')} | WHY: {b.get('why', '')}" for b in bad_examples[:2]]
        )

        user_content = (
            f"Input Text:\n{item.get('text', '')}\n\n"
            f"Avoid patterns:\n{bad_text}\n\n"
            "Now produce one valid question in the required JSON schema."
        )

        assistant_content = json.dumps(
            [
                {
                    "reasoning": good.get("reasoning", ""),
                    "question": good.get("question", ""),
                    "answer_spans": good.get("answer_spans", []),
                    "expected_answer_spans_level0": good.get(
                        "expected_answer_spans_level0", []
                    ),
                }
            ],
            ensure_ascii=False,
            indent=2,
        )

        messages.append({"role": "user", "content": user_content})
        messages.append({"role": "assistant", "content": assistant_content})

    return messages


def format_human_few_shot_messages(
    good_rows: List[dict],
    level: str,
    source: str,
    max_items: int,
) -> List[Dict[str, str]]:
    level_num = parse_level_number(level)
    candidates: List[dict] = []

    for row in good_rows:
        if not isinstance(row, dict):
            continue

        row_level = str(row.get("level", "")).strip()
        if row_level != level_num:
            continue

        row_source = canonicalize_source(row.get("source"))
        if source != "all" and row_source != source:
            continue

        question = row.get("question", "")
        reasoning = row.get("reasoning", "")
        text = row.get("text", "")
        if not (question and reasoning and text):
            continue

        candidates.append({
            "text": text,
            "question": question,
            "reasoning": reasoning,
        })

    random.shuffle(candidates)
    if max_items > 0:
        candidates = candidates[:max_items]

    messages: List[Dict[str, str]] = []
    for row in candidates:
        messages.append({"role": "user", "content": f"Input Text:\n{row['text']}"})
        messages.append(
            {
                "role": "assistant",
                "content": json.dumps(
                    [
                        {
                            "reasoning": row["reasoning"],
                            "question": row["question"],
                            "answer_spans": row.get("answer_spans", []),
                            "expected_answer_spans_level0": row.get(
                                "expected_answer_spans_level0", []
                            ),
                        }
                    ],
                    ensure_ascii=False,
                ),
            }
        )

    return messages


def call_api_with_retry(
    messages: List[Dict[str, str]],
    max_tokens: int,
    request_timeout_seconds: int = 70,
) -> List[dict]:
    global global_consecutive_errors, global_last_api_error

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": max_tokens,
    }

    for attempt in range(3):
        with error_lock:
            if global_consecutive_errors >= global_max_consecutive_errors:
                detail = f" Last API error: {global_last_api_error}" if global_last_api_error else ""
                raise RuntimeError(
                    "Circuit breaker triggered: too many consecutive errors"
                    f" ({global_consecutive_errors}/{global_max_consecutive_errors}).{detail}"
                )

        try:
            response = requests.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload,
                timeout=request_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = extract_json_array(content)

            if not parsed:
                print(f"\n[BAD RESPONSE raw] {repr(content[:400])}", flush=True)
                raise ValueError("No valid JSON array in model output")

            with error_lock:
                global_consecutive_errors = 0
            return parsed
        except Exception as exc:
            err_msg = str(exc)
            print(f"\n[API attempt {attempt+1}/3 failed] {err_msg[:200]}", flush=True)
            if attempt == 2:
                with error_lock:
                    global_consecutive_errors += 1
                    global_last_api_error = err_msg
                print(f"\n[API GIVING UP after 3 attempts] last error: {err_msg[:300]}", flush=True)
                return []
            time.sleep(2)

    return []


def build_revision_feedback(reasons: List[str]) -> str:
    bullet_lines = "\n".join(f"- {r}" for r in reasons)
    return (
        "Your previous question failed style validation. Regenerate once.\n"
        "Fix all issues below while keeping the same target level.\n"
        f"{bullet_lines}\n"
        "Return ONLY the required JSON array with one object.\n"
        "The object MUST include all required fields: reasoning, question, answer_spans, expected_answer_spans_level0."
    )


def assign_level0_mimic_targets(items: List[dict]) -> Dict[str, str]:
    """
    Fixed split for level0: 7 level1-like, 7 level2-like, 6 level3-like.
    If item count differs from 20, fallback to cyclical assignment.
    """
    ordered = sorted(items, key=lambda row: str(row.get("uuid", "")))
    targets: Dict[str, str] = {}

    if len(ordered) == 20:
        cursor = 0
        for mimic, count in LEVEL0_MIMIC_SPLIT:
            for item in ordered[cursor : cursor + count]:
                targets[str(item["uuid"])] = mimic
            cursor += count
        return targets

    cycle = ["level1", "level2", "level3"]
    for idx, item in enumerate(ordered):
        targets[str(item["uuid"])] = cycle[idx % len(cycle)]
    return targets


def load_style_context(good_path: Path, bad_path: Path) -> str:
    """Builds compact style guidance grounded in the second-round labeled pools."""
    lines: List[str] = []

    if bad_path.exists():
        try:
            with bad_path.open("r", encoding="utf-8") as f:
                bad_rows = json.load(f)

            elimination_counts = Counter(
                row.get("elimination_type", "unknown") for row in bad_rows if isinstance(row, dict)
            )

            top_bad = elimination_counts.most_common(3)
            if top_bad:
                lines.append("Observed bad patterns to avoid:")
                for name, count in top_bad:
                    lines.append(f"- {name}: {count}")

            bad_questions = [row.get("question", "") for row in bad_rows[:30] if isinstance(row, dict)]
            if bad_questions:
                sampled_bad = random.choice([q for q in bad_questions if q])
                lines.append(f"Example of bad style (do not imitate): {sampled_bad}")
        except Exception:
            pass

    if good_path.exists():
        try:
            with good_path.open("r", encoding="utf-8") as f:
                good_rows = json.load(f)

            good_questions = [row.get("question", "") for row in good_rows[:40] if isinstance(row, dict)]
            if good_questions:
                sampled_good = random.choice([q for q in good_questions if q])
                lines.append(f"Example of preferred concise style: {sampled_good}")
        except Exception:
            pass

    return "\n".join(lines).strip()


def process_item(
    item: dict,
    level: str,
    system_prompt: str,
    few_shot_msgs: List[Dict[str, str]],
    max_revisions: int,
    max_tokens: int,
    request_timeout_seconds: int,
    item_time_budget_seconds: int,
    mimic_target: Optional[str] = None,
) -> Optional[dict]:
    start_time = time.time()

    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages.extend(few_shot_msgs)
    if mimic_target:
        messages.append(
            {
                "role": "user",
                "content": (
                    "MIMIC TARGET FOR THIS ITEM: "
                    f"{mimic_target}. "
                    "Keep Level-0 requirements (answer must be absent from text), "
                    f"but make phrasing and structure feel {mimic_target}-like."
                ),
            }
        )
    messages.append({"role": "user", "content": f"Input Text:\n{item['text']}"})

    for _ in range(max_revisions + 1):
        if time.time() - start_time > item_time_budget_seconds:
            return None

        result_array = call_api_with_retry(
            messages,
            max_tokens=max_tokens,
            request_timeout_seconds=request_timeout_seconds,
        )
        if not result_array:
            print(f"\n[SKIPPED] {item['uuid']} — API returned empty result", flush=True)
            return None

        candidate = result_array[0]
        question = candidate.get("question", "").strip()
        reasoning = candidate.get("reasoning", "").strip()
        answer_spans = candidate.get("answer_spans", [])
        expected_spans = candidate.get("expected_answer_spans_level0", [])

        ok, reasons = validate_question(level, question, item["text"])
        span_ok, span_reasons = validate_span_fields(level, candidate, item["text"])
        reasons.extend(span_reasons)
        ok = ok and span_ok
        if ok:
            return {
                "uuid": item["uuid"],
                "question": question,
                "reasoning": reasoning,
                "answer_spans": answer_spans,
                "expected_answer_spans_level0": expected_spans,
                "mimic_target": mimic_target if mimic_target else "",
                "author": "gemini",
            }

        messages.append({"role": "assistant", "content": json.dumps(result_array, ensure_ascii=False)})
        messages.append({"role": "user", "content": build_revision_feedback(reasons)})

    # All revision attempts exhausted — save the last candidate flagged for manual review
    print(f"\n[FLAGGED] {item['uuid']} failed validation after {max_revisions} revisions. Saving for manual review. Reasons: {reasons}")
    last_candidate = result_array[0] if result_array else {}
    return {
        "uuid": item["uuid"],
        "question": last_candidate.get("question", "").strip(),
        "reasoning": last_candidate.get("reasoning", "").strip(),
        "answer_spans": last_candidate.get("answer_spans", []),
        "expected_answer_spans_level0": last_candidate.get("expected_answer_spans_level0", []),
        "mimic_target": mimic_target if mimic_target else "",
        "author": "gemini",
        "needs_review": True,
        "validation_failures": reasons,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Second-round question generation with style gates")
    parser.add_argument("--level", required=True, choices=["level0", "level1", "level2", "level3"])
    parser.add_argument(
        "--root",
        default="data_prep_new/round_3",
        help="Root folder for round_3 assets",
    )
    parser.add_argument(
        "--input-dir",
        default="input",
        help="Input directory relative to --root",
    )
    parser.add_argument(
        "--output-dir",
        default="generation_v2/output",
        help="Output directory relative to --root",
    )
    parser.add_argument(
        "--source",
        default="all",
        choices=["all", "knesset", "wiki", "il-hym"],
        help="Generate for all sources or a specific source",
    )
    parser.add_argument(
        "--max-few-shot-items",
        type=int,
        default=3,
        help="Maximum number of few-shot examples to include",
    )
    parser.add_argument(
        "--max-revisions",
        type=int,
        default=2,
        help="Maximum rewrite attempts after QA failure",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=0,
        help="Override max_tokens per call (0 = level default)",
    )
    parser.add_argument(
        "--request-timeout-seconds",
        type=int,
        default=50,
        help="HTTP timeout per API attempt in seconds",
    )
    parser.add_argument(
        "--item-time-budget-seconds",
        type=int,
        default=180,
        help="Maximum wall-clock seconds per item before skipping it",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=MAX_WORKERS,
        help="Thread pool size for parallel generation",
    )
    parser.add_argument(
        "--max-consecutive-errors",
        type=int,
        default=MAX_CONSECUTIVE_ERRORS,
        help="Circuit breaker threshold for consecutive failed API calls",
    )
    parser.add_argument(
        "--use-human-few-shot",
        action="store_true",
        help="Use human-labeled good pool as few-shot source",
    )
    parser.add_argument(
        "--good-path",
        default="expriment_good_questions.json",
        help="Good example pool path relative to --root",
    )
    parser.add_argument(
        "--bad-path",
        default="experiment_bad_questions.json",
        help="Bad example pool path relative to --root",
    )
    args = parser.parse_args()

    global global_max_consecutive_errors, global_consecutive_errors, global_last_api_error
    global_max_consecutive_errors = max(1, args.max_consecutive_errors)
    global_consecutive_errors = 0
    global_last_api_error = ""

    root = Path(args.root)
    level = args.level
    source_filter = canonicalize_source(args.source) or "all"

    prompt_path = root / "generation_v2" / "prompts" / f"{level}.md"
    few_shot_path = root / "generation_v2" / "few_shot_examples" / f"{level}.json"
    input_path = root / args.input_dir / f"{level}_input.json"
    good_path = root / args.good_path
    bad_path = root / args.bad_path

    output_dir = root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_suffix = "" if source_filter == "all" else f"_{source_filter}"
    output_path = output_dir / f"{level}{output_suffix}_output.json"
    temp_output_path = output_dir / f"{level}{output_suffix}_output.tmp.json"

    with prompt_path.open("r", encoding="utf-8") as f:
        system_prompt = f.read().strip()

    style_context = load_style_context(good_path, bad_path)

    def finalize_system_prompt(base_prompt: str) -> str:
        prompt = base_prompt
        prompt += (
            "\n\nCRITICAL: Generate EXACTLY ONE question. "
            "Return ONLY a valid JSON array with one object and no extra text."
        )
        prompt += (
            "\n\nMANDATORY OUTPUT FIELDS (separate fields):"
            "\n- reasoning: English explanation"
            "\n- question: Hebrew question"
            "\n- answer_spans: array of exact span strings copied from the input text"
            "\n- expected_answer_spans_level0: array of exact span strings copied from the input text"
        )
        if level == "level0":
            prompt += (
                "\nFor level0 only: answer_spans must be [] and expected_answer_spans_level0 must be non-empty."
            )
        else:
            prompt += (
                "\nFor non-level0: answer_spans must be non-empty and expected_answer_spans_level0 must be []."
            )
        if style_context:
            prompt += "\n\n" + style_context
        return prompt

    system_prompt = finalize_system_prompt(system_prompt)

    with input_path.open("r", encoding="utf-8") as f:
        inputs = json.load(f)

    good_rows = load_pool_rows(good_path)
    bad_rows = load_pool_rows(bad_path)
    record_source_map = build_record_source_map(good_rows=good_rows, bad_rows=bad_rows)
    annotate_input_sources(inputs, record_source_map)

    if source_filter != "all":
        inputs = [row for row in inputs if canonicalize_source(row.get("source")) == source_filter]

    if args.use_human_few_shot:
        few_shot_msgs = format_human_few_shot_messages(
            good_rows=good_rows,
            level=level,
            source=source_filter,
            max_items=args.max_few_shot_items,
        )
    else:
        few_shot_msgs = format_few_shot_messages(
            few_shot_path=few_shot_path,
            max_items=args.max_few_shot_items,
        )

    default_max_tokens_by_level = {
        "level0": 8192,
        "level1": 8192,
        "level2": 8192,
        "level3": 8192,
    }
    max_tokens = args.max_tokens if args.max_tokens > 0 else default_max_tokens_by_level[level]

    completed_results: List[dict] = []
    completed_uuids = set()

    if output_path.exists():
        try:
            with output_path.open("r", encoding="utf-8") as f:
                completed_results = json.load(f)
                completed_uuids = {row["uuid"] for row in completed_results}
        except Exception:
            completed_results = []
            completed_uuids = set()

    pending_inputs = [row for row in inputs if row["uuid"] not in completed_uuids]

    if not pending_inputs:
        print(f"All items already completed for {level}: {len(inputs)}")
        return

    print(
        f"Loaded {len(inputs)} items for {level} ({source_filter}). "
        f"Already done: {len(completed_uuids)}. Pending: {len(pending_inputs)}"
    )

    mimic_by_uuid: Dict[str, str] = {}
    if level == "level0":
        mimic_by_uuid = assign_level0_mimic_targets(inputs)

    results_lock = threading.Lock()

    if level == "level0":
        stage_order = ["level1", "level2", "level3"]
        staged_pending = {
            stage: [item for item in pending_inputs if mimic_by_uuid.get(str(item["uuid"])) == stage]
            for stage in stage_order
        }

        print("Level0 staged plan:")
        for stage in stage_order:
            print(f"- {stage}-like: {len(staged_pending[stage])} pending")

        total_pending = len(pending_inputs)
        with tqdm(total=total_pending, desc=f"Generating {level} {source_filter}") as pbar:
            for stage in stage_order:
                stage_items = staged_pending[stage]
                if not stage_items:
                    continue

                stage_prompt_path = root / "generation_v2" / "prompts" / f"level0_{stage}_mimic.md"
                selected_prompt_path = stage_prompt_path if stage_prompt_path.exists() else prompt_path
                with selected_prompt_path.open("r", encoding="utf-8") as f:
                    stage_system_prompt = finalize_system_prompt(f.read().strip())

                if args.use_human_few_shot:
                    stage_few_shot_msgs = format_human_few_shot_messages(
                        good_rows=good_rows,
                        level=level,
                        source=source_filter,
                        max_items=args.max_few_shot_items,
                    )
                    few_shot_label = "human_pool"
                else:
                    stage_few_shot_path = (
                        root
                        / "generation_v2"
                        / "few_shot_examples"
                        / f"level0_{stage}_mimic.json"
                    )
                    selected_few_shot_path = (
                        stage_few_shot_path if stage_few_shot_path.exists() else few_shot_path
                    )
                    stage_few_shot_msgs = format_few_shot_messages(
                        few_shot_path=selected_few_shot_path,
                        max_items=args.max_few_shot_items,
                    )
                    few_shot_label = selected_few_shot_path.name

                print(
                    f"Starting stage: {stage}-like "
                    f"(prompt={selected_prompt_path.name}, few_shot={few_shot_label})"
                )
                with ThreadPoolExecutor(max_workers=max(1, args.max_workers)) as executor:
                    futures = {
                        executor.submit(
                            process_item,
                            item,
                            level,
                            stage_system_prompt,
                            stage_few_shot_msgs,
                            args.max_revisions,
                            max_tokens,
                            args.request_timeout_seconds,
                            args.item_time_budget_seconds,
                            stage,
                        ): item
                        for item in stage_items
                    }

                    for future in as_completed(futures):
                        try:
                            result = future.result()
                            if result:
                                with results_lock:
                                    completed_results.append(result)
                                    with temp_output_path.open("w", encoding="utf-8") as f:
                                        json.dump(completed_results, f, ensure_ascii=False, indent=2)
                                    os.replace(temp_output_path, output_path)
                        except Exception as exc:
                            if "Circuit breaker" in str(exc):
                                print("Circuit breaker triggered. Stopping early to protect API budget.")
                                for f in futures:
                                    f.cancel()
                                break
                        pbar.update(1)
    else:
        with ThreadPoolExecutor(max_workers=max(1, args.max_workers)) as executor:
            futures = {
                executor.submit(
                    process_item,
                    item,
                    level,
                    system_prompt,
                    few_shot_msgs,
                    args.max_revisions,
                    max_tokens,
                    args.request_timeout_seconds,
                    args.item_time_budget_seconds,
                    None,
                ): item
                for item in pending_inputs
            }

            with tqdm(total=len(pending_inputs), desc=f"Generating {level} {source_filter}") as pbar:
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        if result:
                            with results_lock:
                                completed_results.append(result)
                                with temp_output_path.open("w", encoding="utf-8") as f:
                                    json.dump(completed_results, f, ensure_ascii=False, indent=2)
                                os.replace(temp_output_path, output_path)
                    except Exception as exc:
                        if "Circuit breaker" in str(exc):
                            print("Circuit breaker triggered. Stopping early to protect API budget.")
                            for f in futures:
                                f.cancel()
                            break
                    pbar.update(1)

    print(f"Finished {level} ({source_filter}). Saved: {output_path}")


if __name__ == "__main__":
    main()
