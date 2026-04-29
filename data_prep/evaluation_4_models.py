#!/usr/bin/env python3
"""Run OpenRouter evaluation for a single JSON/JSONL question file."""

from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple

import requests
from dotenv import load_dotenv

DEFAULT_MODELS = (
    "gemini_3_1_pro_eval=google/gemini-3.1-pro-preview;"
    "gpt_5_4_mini_eval=openai/gpt-5.4-mini;"
    "mistral_large_2407_eval=mistralai/mistral-large-2407;"
    "claude_3_7_sonnet_eval=anthropic/claude-3.7-sonnet"
)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_CREDITS_URL = "https://openrouter.ai/api/v1/credits"
REQUIRED_OUTPUT_FIELDS = ("complexity_score", "linguistic_score")
REASONING_MAX_CHARS = 150


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run OpenRouter question evaluation for one JSON/JSONL input file."
    )
    parser.add_argument(
        "--input-json",
        type=Path,
        default=Path("data_prep/questions/eval/all_questions_for_eval.jsonl"),
        help="Path to a questions JSON array or JSONL file.",
    )
    parser.add_argument(
        "--prompt-file",
        type=Path,
        default=Path("data_prep/prompts/03_question_assessment.md"),
        help="Prompt file passed as system message.",
    )
    parser.add_argument(
        "--output-folder",
        type=Path,
        default=Path("data_prep/questions/eval_openrouter"),
        help="Folder for per-model evaluation JSONL outputs.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("data_prep/questions/eval/all_questions_for_eval_scored.json"),
        help="Consolidated JSON output with one row per (input row, evaluator model).",
    )
    parser.add_argument(
        "--models",
        type=str,
        default=DEFAULT_MODELS,
        help="Model mapping string in label=model_id;label=model_id format.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=8,
        help="Concurrent workers for evaluation.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=1200,
        help="Max output tokens per model response.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=90,
        help="Per-request timeout.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Retries per request for transient failures.",
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=100,
        help="Write intermediate per-model JSONL every N completed rows (0 disables).",
    )
    parser.add_argument(
        "--errors-report",
        type=Path,
        default=None,
        help=(
            "Path to an aggregated JSONL of per-row evaluation errors across all models. "
            "If omitted, defaults to <output-folder>/errors_report.jsonl. The file is appended to."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional row limit for smoke runs (0 = all rows).",
    )
    parser.add_argument(
        "--no-resume-existing",
        action="store_true",
        help="Disable per-model resume mode.",
    )
    return parser.parse_args()


def ensure_openrouter_key(project_root: Path) -> None:
    env_path = project_root / ".env"
    if not env_path.exists():
        raise SystemExit(f"Missing .env in project root: {env_path}")

    load_dotenv(env_path)
    if not os.getenv("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is not set in environment/.env")


def parse_model_map(models_arg: str) -> Dict[str, str]:
    model_map: Dict[str, str] = {}
    pairs = [p.strip() for p in (models_arg or "").split(";") if p.strip()]
    for pair in pairs:
        if "=" not in pair:
            continue
        label, model_id = pair.split("=", 1)
        label = label.strip()
        model_id = model_id.strip()
        if label and model_id:
            model_map[label] = model_id
    return model_map


def read_prompt(prompt_path: Path) -> str:
    return prompt_path.read_text(encoding="utf-8").strip()


def load_question_rows(input_json: Path) -> List[Dict[str, str]]:
    if not input_json.exists():
        raise SystemExit(f"Input JSON/JSONL does not exist: {input_json}")

    raw = input_json.read_text(encoding="utf-8")
    stripped = raw.lstrip()
    if not stripped:
        return []

    if stripped[0] == "[":
        loaded = json.loads(raw)
        if not isinstance(loaded, list):
            raise SystemExit("Expected top-level JSON array")
        source_rows = loaded
    elif stripped[0] == "{":
        source_rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    else:
        raise SystemExit("Expected JSON array (starts with [) or JSONL (starts with {)")

    rows: List[Dict[str, str]] = []
    for row in source_rows:
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                "uuid": str(row.get("uuid") or row.get("UUID") or ""),
                "excerpt": str(
                    row.get("excerpt")
                    or row.get("extracted_text")
                    or row.get("text")
                    or ""
                ),
                "question": str(row.get("question") or ""),
            }
        )
    return rows


def build_eval_user_message(row: Dict[str, str]) -> str:
    payload = {
        "uuid": str(row.get("uuid") or ""),
        "excerpt": str(row.get("excerpt") or ""),
        "question": str(row.get("question") or ""),
    }
    return json.dumps(payload, ensure_ascii=False)


def parse_single_eval_json(response_text: str) -> Tuple[Dict[str, str], str]:
    normalized = (response_text or "").strip()
    if not normalized:
        return {}, "Empty response content"

    start_idx = normalized.find("{")
    if start_idx == -1:
        return {}, "Could not find JSON object in model response"

    depth = 0
    in_string = False
    escape_next = False
    end_idx = -1

    for pos in range(start_idx, len(normalized)):
        char = normalized[pos]
        if escape_next:
            escape_next = False
            continue
        if char == "\\":
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if not in_string:
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end_idx = pos + 1
                    break

    if end_idx == -1:
        return {}, "Could not find matching closing brace in JSON"

    json_str = normalized[start_idx:end_idx]
    try:
        parsed_obj = json.loads(json_str)
    except json.JSONDecodeError as exc:
        return {}, f"Invalid JSON: {str(exc)}"

    out: Dict[str, str] = {}
    # Only `uuid` may be echoed; `excerpt`/`question` are intentionally not
    # required in the model output anymore (they are known locally) to save
    # output tokens. We still accept them if present for backward compatibility.
    for field in ["uuid", "excerpt", "question"]:
        if parsed_obj.get(field) is not None:
            out[field] = str(parsed_obj[field])

    if "complexity_score" in parsed_obj:
        complexity_raw = parsed_obj["complexity_score"]
    elif "complexity_level" in parsed_obj:
        complexity_raw = parsed_obj["complexity_level"]
    else:
        return {}, "Missing complexity_score field"

    try:
        complexity = int(complexity_raw)
    except (ValueError, TypeError):
        return {}, f"Invalid complexity_score value: {complexity_raw}"
    if not (0 <= complexity <= 3):
        return {}, f"complexity_score out of range: {complexity}"
    out["complexity_score"] = str(complexity)

    if "linguistic_score" in parsed_obj:
        linguistic_raw = parsed_obj["linguistic_score"]
    elif "linguistic_correctness_naturalness" in parsed_obj:
        linguistic_raw = parsed_obj["linguistic_correctness_naturalness"]
    else:
        return {}, "Missing linguistic_score field"

    try:
        linguistic = int(linguistic_raw)
    except (ValueError, TypeError):
        return {}, f"Invalid linguistic_score value: {linguistic_raw}"
    if not (0 <= linguistic <= 4):
        return {}, f"linguistic_score out of range: {linguistic}"
    out["linguistic_score"] = str(linguistic)

    reasoning_text = str(parsed_obj.get("reasoning", "") or "").strip()
    if len(reasoning_text) > REASONING_MAX_CHARS:
        reasoning_text = reasoning_text[:REASONING_MAX_CHARS]
    out["reasoning"] = reasoning_text
    return out, ""


def _extract_content_from_choice(choice: Dict[str, object]) -> str:
    message = (choice.get("message") or {}) if isinstance(choice, dict) else {}
    content = message.get("content", "") if isinstance(message, dict) else ""

    if isinstance(content, list):
        chunks: List[str] = []
        for item in content:
            if isinstance(item, dict):
                text_val = item.get("text")
                if text_val is not None:
                    chunks.append(str(text_val))
            elif isinstance(item, str):
                chunks.append(item)
        return "".join(chunks)

    return str(content or "")


def _extract_usage_stats(data: Dict[str, object]) -> Dict[str, int]:
    """Pull cache/token counters from an OpenRouter chat-completions response.

    Field names vary across providers; we collect all of them best-effort.
    Returns zeros for missing fields.
    """
    usage = data.get("usage") if isinstance(data, dict) else None
    if not isinstance(usage, dict):
        return {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0}

    def _to_int(value: object) -> int:
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0

    prompt_tokens = _to_int(usage.get("prompt_tokens"))
    completion_tokens = _to_int(usage.get("completion_tokens"))

    # OpenAI/Gemini: usage.prompt_tokens_details.cached_tokens
    cached = 0
    details = usage.get("prompt_tokens_details")
    if isinstance(details, dict):
        cached = max(cached, _to_int(details.get("cached_tokens")))

    # Anthropic (sometimes surfaced through OpenRouter):
    #   usage.cache_read_input_tokens / cache_creation_input_tokens
    cached = max(cached, _to_int(usage.get("cache_read_input_tokens")))

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cached_tokens": cached,
    }


def call_openrouter_eval(
    api_key: str,
    model_id: str,
    prompt_text: str,
    row: Dict[str, str],
    timeout_seconds: int,
    max_retries: int,
    max_output_tokens: int,
) -> Tuple[Dict[str, str], str, Dict[str, int]]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    site_url = os.getenv("OPENROUTER_SITE_URL")
    app_name = os.getenv("OPENROUTER_APP_NAME")
    if site_url:
        headers["HTTP-Referer"] = site_url
    if app_name:
        headers["X-Title"] = app_name

    # Prompt caching:
    # - Anthropic models on OpenRouter require an explicit cache breakpoint via
    #   `cache_control: {type: "ephemeral"}` on the system content block.
    # - Gemini and OpenAI cache long, byte-identical prompts automatically; no
    #   special structure is required and they accept a plain string `content`.
    # We therefore only switch to the structured-content form for Anthropic to
    #   avoid changing the request shape for providers that don't need it.
    if model_id.startswith("anthropic/"):
        system_content = [
            {
                "type": "text",
                "text": prompt_text,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    else:
        system_content = prompt_text

    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": build_eval_user_message(row)},
        ],
        "temperature": 0,
        "max_tokens": max_output_tokens,
    }

    # Gemini "thinking" models bill internal reasoning tokens as output tokens
    # and those tokens count against `max_tokens`. For a structured 0–3 / 0–4
    # scoring task, low reasoning effort is sufficient and substantially
    # reduces both truncation risk and per-call output cost.
    if model_id.startswith("google/gemini"):
        payload["reasoning"] = {"effort": "low"}

    last_error = "Unknown OpenRouter error"
    last_usage: Dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0}
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload,
                timeout=timeout_seconds,
            )

            if response.status_code != 200:
                last_error = f"HTTP {response.status_code}: {response.text[:500]}"
                # Insufficient credits is non-transient; do not burn retries.
                if response.status_code == 402:
                    break
            else:
                try:
                    data = response.json()
                except json.JSONDecodeError as exc:
                    last_error = f"Non-JSON OpenRouter response: {exc}; raw={response.text[:500]}"
                    data = {}

                last_usage = _extract_usage_stats(data if isinstance(data, dict) else {})

                choices = data.get("choices", []) if isinstance(data, dict) else []
                first_choice = choices[0] if choices else {}
                finish_reason = ""
                if isinstance(first_choice, dict):
                    finish_reason = str(first_choice.get("finish_reason") or "")

                content = _extract_content_from_choice(first_choice if isinstance(first_choice, dict) else {})
                if not content.strip():
                    suffix = f"; finish_reason={finish_reason}" if finish_reason else ""
                    last_error = f"Empty response content{suffix}"
                else:
                    parsed, parse_error = parse_single_eval_json(content)
                    if parse_error:
                        suffix = f"; finish_reason={finish_reason}" if finish_reason else ""
                        last_error = (
                            f"Invalid JSON output: {parse_error}{suffix}; raw_content={content[:500]}"
                        )
                    else:
                        return parsed, "", last_usage
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)

        if attempt < max_retries:
            time.sleep(1.5 * attempt)

    return {}, f"ERROR: {last_error}", last_usage


def get_openrouter_available_credits(api_key: str, timeout_seconds: int = 20) -> Tuple[float, float, float, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.get(OPENROUTER_CREDITS_URL, headers=headers, timeout=timeout_seconds)
        if response.status_code != 200:
            return 0.0, 0.0, 0.0, f"HTTP {response.status_code}: {response.text[:300]}"

        payload = response.json() if response.text else {}
        data = payload.get("data") if isinstance(payload, dict) else {}
        total_credits = float((data or {}).get("total_credits") or 0.0)
        total_usage = float((data or {}).get("total_usage") or 0.0)
        available = total_credits - total_usage
        return total_credits, total_usage, available, ""
    except Exception as exc:  # noqa: BLE001
        return 0.0, 0.0, 0.0, str(exc)


def _worker_eval(args: Tuple) -> Tuple[int, Dict[str, str], str, Dict[str, int]]:
    idx, api_key, model_id, prompt_text, row, timeout_seconds, max_retries, max_output_tokens = args
    parsed, err, usage = call_openrouter_eval(
        api_key=api_key,
        model_id=model_id,
        prompt_text=prompt_text,
        row=row,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        max_output_tokens=max_output_tokens,
    )
    return idx, parsed, err, usage


def _format_eta_hms(total_seconds: int) -> str:
    if total_seconds < 0:
        return "--:--:--"
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _model_progress_line(completed: int, total: int, start_time: float) -> str:
    if total <= 0:
        return "  evaluating 0/0"
    ratio = min(max(completed / total, 0.0), 1.0)
    width = 28
    filled = int(width * ratio)
    bar = "#" * filled + "-" * (width - filled)
    elapsed = max(time.time() - start_time, 1e-6)
    speed = completed / elapsed if completed else 0.0
    eta = int((total - completed) / speed) if speed > 0 else -1
    eta_text = _format_eta_hms(eta)
    return f"  evaluating [{bar}] {completed}/{total} ({ratio * 100:5.1f}%) ETA {eta_text}"


def row_needs_evaluation(row: Dict[str, str]) -> bool:
    if (row.get("evaluation_error") or "").strip():
        return True
    return any(not (row.get(field) or "").strip() for field in REQUIRED_OUTPUT_FIELDS)


def load_resume_rows_jsonl(
    output_path: Path,
    input_rows: List[Dict[str, str]],
) -> Tuple[List[Dict[str, str]], List[int]]:
    if not output_path.exists():
        return [dict(row) for row in input_rows], list(range(len(input_rows)))

    existing_rows: List[Dict[str, str]] = []
    with output_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                existing_rows.append(json.loads(line))

    if len(existing_rows) != len(input_rows):
        print(
            f"[RESUME] Existing file row count mismatch for {output_path.name} "
            f"({len(existing_rows)} vs {len(input_rows)}). Re-evaluating all rows."
        )
        return [dict(row) for row in input_rows], list(range(len(input_rows)))

    pending_indices = [i for i, row in enumerate(existing_rows) if row_needs_evaluation(row)]
    print(
        f"[RESUME] {output_path.name}: reusing {len(existing_rows) - len(pending_indices)} completed rows, "
        f"retrying {len(pending_indices)} rows"
    )
    return existing_rows, pending_indices


def write_jsonl(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


_PERSISTENT_ERROR_MARKERS = (
    "HTTP 401",
    "HTTP 402",
    "HTTP 403",
    "insufficient_quota",
    "invalid_api_key",
    "authentication",
    "unauthorized",
    "forbidden",
    "credits",
)

# Heuristic: consider these substrings to indicate a transient network/timeout
# failure. Used to detect recurring-timeout streaks that justify aborting the
# current model run rather than burning paid retries on a flaky route.
_TIMEOUT_ERROR_MARKERS = (
    "timeout",
    "timed out",
    "read timed out",
    "connection aborted",
    "connection reset",
    "connection error",
    "connectionerror",
    "max retries exceeded",
    "http 408",
    "http 502",
    "http 503",
    "http 504",
    "http 524",
)

MAX_CONSECUTIVE_TIMEOUTS = 10


def _is_persistent_error(error_text: str) -> bool:
    """Return True if the error looks like an auth/credits/quota issue that
    will not resolve by retrying.
    """
    if not error_text:
        return False
    lowered = error_text.lower()
    for marker in _PERSISTENT_ERROR_MARKERS:
        if marker.lower() in lowered:
            return True
    return False


def _is_timeout_error(error_text: str) -> bool:
    if not error_text:
        return False
    lowered = error_text.lower()
    for marker in _TIMEOUT_ERROR_MARKERS:
        if marker in lowered:
            return True
    return False


def append_errors_report(
    report_path: Path,
    model_label: str,
    model_id: str,
    failed_rows: List[Dict[str, str]],
) -> None:
    if not failed_rows:
        return
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("a", encoding="utf-8") as f:
        for r in failed_rows:
            entry = {
                "uuid": str(r.get("uuid") or ""),
                "evaluator_model_name": model_label,
                "evaluator_model_id": model_id,
                "evaluation_error": str(r.get("evaluation_error") or ""),
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _base_output_row(input_row: Dict[str, str], model_label: str, model_id: str) -> Dict[str, str]:
    return {
        "uuid": str(input_row.get("uuid") or ""),
        "excerpt": str(input_row.get("excerpt") or ""),
        "question": str(input_row.get("question") or ""),
        "complexity_score": "",
        "linguistic_score": "",
        "reasoning": "",
        "evaluator_model_name": model_label,
        "evaluator_model_id": model_id,
        "evaluation_error": "",
    }


def evaluate_rows_for_input(args: argparse.Namespace) -> int:
    if not args.input_json.exists():
        raise SystemExit(f"Input JSON/JSONL not found: {args.input_json}")
    if not args.prompt_file.exists():
        raise SystemExit(f"Prompt file not found: {args.prompt_file}")

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is not set.")

    rows = load_question_rows(args.input_json)
    if not rows:
        raise SystemExit(f"Input has no rows: {args.input_json}")

    if args.limit and args.limit > 0:
        rows = rows[: args.limit]
        print(f"[INFO] Using first {len(rows)} rows due to --limit")

    model_map = parse_model_map(args.models)
    if not model_map:
        raise SystemExit("No models configured for evaluation")

    prompt_text = read_prompt(args.prompt_file)
    base_name = args.input_json.stem

    run_start_ts = time.time()
    n_models = len(model_map)
    print(
        f"\n[RUN] models={n_models} rows={len(rows)} workers={args.max_workers} "
        f"checkpoint_every={args.checkpoint_every} "
        f"errors_report={args.errors_report}"
    )

    for model_index, (model_label, model_id) in enumerate(model_map.items(), start=1):
        model_start_ts = time.time()
        print(f"\n[MODEL {model_index}/{n_models}] {model_label} ({model_id})")
        print(f"[MODEL] rows={len(rows)}, workers={args.max_workers}")

        total_credits, total_usage, available_credits, credits_err = get_openrouter_available_credits(
            api_key=api_key,
            timeout_seconds=min(args.timeout_seconds, 20),
        )
        if credits_err:
            print(f"[CREDITS] Could not fetch credits before {model_label}: {credits_err}")
        else:
            print(
                f"[CREDITS] total={total_credits:.3f} used={total_usage:.3f} "
                f"available={available_credits:.3f}"
            )
            if available_credits <= 0:
                print(
                    f"[FATAL] Available credits are <= 0 before {model_label}. "
                    "Stopping to avoid all-error burn."
                )
                return 1

        output_path = args.output_folder / f"{base_name}_eval_{model_label}.jsonl"

        if not args.no_resume_existing:
            result_rows, pending_indices = load_resume_rows_jsonl(output_path, rows)
            for i, r in enumerate(result_rows):
                r.setdefault("evaluator_model_name", model_label)
                r.setdefault("evaluator_model_id", model_id)
                if "excerpt" not in r:
                    r["excerpt"] = str(rows[i].get("excerpt") or "")
                if "uuid" not in r:
                    r["uuid"] = str(rows[i].get("uuid") or "")
                if "question" not in r:
                    r["question"] = str(rows[i].get("question") or "")
                r.setdefault("reasoning", "")
                r.setdefault("evaluation_error", "")
                for field in REQUIRED_OUTPUT_FIELDS:
                    r.setdefault(field, "")
        else:
            result_rows = [_base_output_row(r, model_label, model_id) for r in rows]
            pending_indices = list(range(len(rows)))

        if not pending_indices:
            print(f"[SKIP] {model_label}: no pending rows")
            continue

        work_items = [
            (
                idx,
                api_key,
                model_id,
                prompt_text,
                rows[idx],
                args.timeout_seconds,
                args.max_retries,
                args.max_output_tokens,
            )
            for idx in pending_indices
        ]

        completed = 0
        errors = 0
        consecutive_timeouts = 0
        aborted_for_timeouts = False
        start_ts = time.time()
        aborted_for_credits = False
        usage_totals = {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0}
        usage_calls = 0
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = {executor.submit(_worker_eval, item): item[0] for item in work_items}
            for future in as_completed(futures):
                idx, parsed, err, usage = future.result()

                if usage:
                    usage_totals["prompt_tokens"] += int(usage.get("prompt_tokens", 0) or 0)
                    usage_totals["completion_tokens"] += int(usage.get("completion_tokens", 0) or 0)
                    usage_totals["cached_tokens"] += int(usage.get("cached_tokens", 0) or 0)
                    if int(usage.get("prompt_tokens", 0) or 0) > 0:
                        usage_calls += 1

                if err:
                    errors += 1
                    row_out = _base_output_row(rows[idx], model_label, model_id)
                    row_out["evaluation_error"] = err
                    if _is_timeout_error(err):
                        consecutive_timeouts += 1
                    else:
                        consecutive_timeouts = 0
                else:
                    consecutive_timeouts = 0
                    row_out = _base_output_row(rows[idx], model_label, model_id)
                    # Authoritative identifiers come from the input row, not
                    # from the model's echoed JSON. Some models (notably
                    # Mistral) occasionally mangle the echoed uuid, and we
                    # already instruct the prompt to omit excerpt/question.
                    row_out["complexity_score"] = parsed.get("complexity_score", "")
                    row_out["linguistic_score"] = parsed.get("linguistic_score", "")
                    row_out["reasoning"] = parsed.get("reasoning", "")

                result_rows[idx] = row_out
                completed += 1
                print("\r" + _model_progress_line(completed, len(work_items), start_ts), end="", flush=True)

                if consecutive_timeouts >= MAX_CONSECUTIVE_TIMEOUTS:
                    print(
                        f"\n[FATAL] {model_label}: {consecutive_timeouts} consecutive timeout/network errors. "
                        f"Cancelling pending futures and stopping the run."
                    )
                    for pending_future in futures:
                        if not pending_future.done():
                            pending_future.cancel()
                    aborted_for_timeouts = True
                    break

                if args.checkpoint_every > 0 and (completed % args.checkpoint_every == 0):
                    write_jsonl(output_path, result_rows)
                    print(
                        f"\n[CHECKPOINT] {model_label}: saved {completed}/{len(work_items)} "
                        f"completed rows -> {output_path}"
                    )
                    # Mid-run credit guard: re-check credits at each checkpoint
                    # and abort the remaining pending futures if depleted.
                    _, _, mid_available, mid_err = get_openrouter_available_credits(
                        api_key=api_key,
                        timeout_seconds=min(args.timeout_seconds, 20),
                    )
                    if mid_err:
                        print(f"[CREDITS] mid-run check failed: {mid_err}")
                    elif mid_available <= 0:
                        print(
                            f"[FATAL] Mid-run credits depleted (available={mid_available:.3f}). "
                            f"Cancelling pending futures for {model_label}."
                        )
                        for pending_future in futures:
                            if not pending_future.done():
                                pending_future.cancel()
                        aborted_for_credits = True
                        break
        print()

        success = len(work_items) - errors
        print(f"[MODEL DONE] success={success}, errors={errors}")
        if usage_calls > 0:
            total_prompt = usage_totals["prompt_tokens"]
            total_cached = usage_totals["cached_tokens"]
            total_completion = usage_totals["completion_tokens"]
            cache_pct = (100.0 * total_cached / total_prompt) if total_prompt > 0 else 0.0
            print(
                f"[USAGE] {model_label}: calls_with_usage={usage_calls} "
                f"prompt_tokens={total_prompt} cached_tokens={total_cached} "
                f"({cache_pct:.1f}% cached) completion_tokens={total_completion}"
            )
        else:
            print(f"[USAGE] {model_label}: no usage stats reported by provider")
        if aborted_for_credits:
            write_jsonl(output_path, result_rows)
            print(f"[WRITE] {output_path} (partial; aborted for credits)")
            failed_rows = [r for r in result_rows if (r.get("evaluation_error") or "").strip()]
            append_errors_report(args.errors_report, model_label, model_id, failed_rows)
            return 1

        if aborted_for_timeouts:
            write_jsonl(output_path, result_rows)
            print(f"[WRITE] {output_path} (partial; aborted for timeouts)")
            failed_rows = [r for r in result_rows if (r.get("evaluation_error") or "").strip()]
            append_errors_report(args.errors_report, model_label, model_id, failed_rows)
            return 1

        write_jsonl(output_path, result_rows)
        print(f"[WRITE] {output_path}")

        # Per-model wall time + cross-model total ETA.
        model_elapsed = int(time.time() - model_start_ts)
        run_elapsed = int(time.time() - run_start_ts)
        models_remaining = n_models - model_index
        avg_per_model = run_elapsed / model_index if model_index > 0 else 0
        total_eta = int(models_remaining * avg_per_model) if models_remaining > 0 else 0
        print(
            f"[TIMING] model_elapsed={_format_eta_hms(model_elapsed)} "
            f"run_elapsed={_format_eta_hms(run_elapsed)} "
            f"models_remaining={models_remaining} "
            f"total_run_eta={_format_eta_hms(total_eta)}"
        )

        # Soft-fail: collect every failed row into the aggregated errors report
        # for later inspection / re-run, regardless of failure rate.
        failed_rows = [r for r in result_rows if (r.get("evaluation_error") or "").strip()]
        if failed_rows:
            append_errors_report(args.errors_report, model_label, model_id, failed_rows)
            print(
                f"[ERRORS] {model_label}: {len(failed_rows)} failed row(s) appended to {args.errors_report}"
            )

        # Strict halt: if a model produced 0 successes, something is systemically
        # wrong (auth, route, prompt rejection, persistent provider failure).
        # Stop the whole run rather than burn credits on the next model.
        if success == 0:
            print(
                f"[FATAL] Model {model_label}: 0 successes / {len(work_items)} attempts. Stopping."
            )
            return 1

    total_run_elapsed = int(time.time() - run_start_ts)
    print(f"\n[RUN DONE] total_elapsed={_format_eta_hms(total_run_elapsed)}")
    return 0


def consolidate_eval_jsonls_to_json(
    input_json: Path,
    output_folder: Path,
    model_map: Dict[str, str],
    output_json: Path,
) -> int:
    base_name = input_json.stem
    rows_out: List[Dict[str, object]] = []

    for model_label, model_id in model_map.items():
        eval_output = output_folder / f"{base_name}_eval_{model_label}.jsonl"
        if not eval_output.exists():
            raise SystemExit(f"Expected evaluator output JSONL not found: {eval_output}")

        with eval_output.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                row = json.loads(line)
                raw_complexity = str(row.get("complexity_score", "")).strip()
                raw_linguistic = str(row.get("linguistic_score", "")).strip()

                complexity_score = int(raw_complexity) if raw_complexity.isdigit() else None
                linguistic_score = int(raw_linguistic) if raw_linguistic.isdigit() else None

                rows_out.append(
                    {
                        "uuid": str(row.get("uuid") or ""),
                        "excerpt": str(row.get("excerpt") or ""),
                        "question": str(row.get("question") or ""),
                        "complexity_score": complexity_score,
                        "linguistic_score": linguistic_score,
                        "reasoning": str(row.get("reasoning") or ""),
                        "evaluator_model_name": str(row.get("evaluator_model_name") or model_label),
                        "evaluator_model_id": str(row.get("evaluator_model_id") or model_id),
                        "evaluation_error": str(row.get("evaluation_error") or ""),
                    }
                )

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(rows_out, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(rows_out)


def to_project_relative(path: Path, project_root: Path) -> Path:
    try:
        return path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return path


def main() -> int:
    args = parse_args()

    project_root = Path(__file__).resolve().parent.parent
    os.chdir(project_root)

    ensure_openrouter_key(project_root)

    args.input_json = to_project_relative(args.input_json, project_root)
    args.prompt_file = to_project_relative(args.prompt_file, project_root)
    args.output_folder = to_project_relative(args.output_folder, project_root)
    args.output_json = to_project_relative(args.output_json, project_root)
    if args.errors_report is None:
        args.errors_report = args.output_folder / "errors_report.jsonl"
    else:
        args.errors_report = to_project_relative(args.errors_report, project_root)

    rc = evaluate_rows_for_input(args)
    if rc == 0:
        model_map = parse_model_map(args.models)
        written = consolidate_eval_jsonls_to_json(
            input_json=args.input_json,
            output_folder=args.output_folder,
            model_map=model_map,
            output_json=args.output_json,
        )
        print(f"Wrote consolidated JSON {args.output_json} with {written} rows")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
