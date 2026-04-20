import argparse
import csv
import io
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_EMBED_URL = "https://openrouter.ai/api/v1/embeddings"

EVAL_MODELS: Dict[str, str] = {
    "claude_3_7_sonnet_eval": "anthropic/claude-3.7-sonnet",
    "gpt_4o_eval": "openai/gpt-4o",
}

DEFAULT_REQUIRED_OUTPUT_FIELDS = [
    "complexity_level",
    "question_quality",
    "relevance",
    "rationale",
    "identified_issues",
]


def _normalize_wiki_link(link: str) -> str:
    return (link or "").strip().rstrip(";")


def _load_jsonl(path: Path) -> List[Dict]:
    rows: List[Dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


class RagChunkRetriever:
    def __init__(
        self,
        assets_dir: Path,
        api_key: str,
        embedding_model_override: str = "",
        top_k: int = 4,
        max_chars_per_chunk: int = 380,
    ) -> None:
        self.assets_dir = assets_dir
        self.api_key = api_key
        self.top_k = top_k
        self.max_chars_per_chunk = max_chars_per_chunk

        manifest = json.loads((assets_dir / "manifest.json").read_text(encoding="utf-8"))
        self.embedding_model = embedding_model_override.strip() or manifest.get("embedding_model", "openai/text-embedding-3-small")

        self.chunks = _load_jsonl(assets_dir / "chunks.jsonl")
        self.emb_norm = np.load(assets_dir / "chunk_embeddings_norm.npy")

        if len(self.chunks) != int(self.emb_norm.shape[0]):
            raise SystemExit(
                f"RAG assets mismatch: chunks={len(self.chunks)} vs embeddings={self.emb_norm.shape[0]}"
            )

        self.indices_by_link: Dict[str, List[int]] = {}
        for i, ch in enumerate(self.chunks):
            link = _normalize_wiki_link(ch.get("wiki_link", ""))
            self.indices_by_link.setdefault(link, []).append(i)

        self._query_vec_cache: Dict[str, np.ndarray] = {}

    def _embed_query(self, query: str, timeout_seconds: int = 60, max_retries: int = 3) -> np.ndarray:
        query = (query or "").strip()
        if query in self._query_vec_cache:
            return self._query_vec_cache[query]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        site_url = os.getenv("OPENROUTER_SITE_URL")
        app_name = os.getenv("OPENROUTER_APP_NAME")
        if site_url:
            headers["HTTP-Referer"] = site_url
        if app_name:
            headers["X-Title"] = app_name

        payload = {
            "model": self.embedding_model,
            "input": [query],
        }

        last_err = "Unknown query embedding error"
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(
                    OPENROUTER_EMBED_URL,
                    headers=headers,
                    json=payload,
                    timeout=timeout_seconds,
                )
                if resp.status_code != 200:
                    last_err = f"HTTP {resp.status_code}: {resp.text[:240]}"
                else:
                    data = resp.json()
                    arr = data.get("data", [])
                    if not arr:
                        last_err = "Empty embedding response"
                    else:
                        vec = np.asarray(arr[0].get("embedding", []), dtype=np.float32)
                        if vec.size == 0:
                            last_err = "Missing embedding vector"
                        else:
                            norm = np.linalg.norm(vec)
                            if norm == 0:
                                norm = 1.0
                            vec = vec / norm
                            self._query_vec_cache[query] = vec
                            return vec
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)

            if attempt < max_retries:
                time.sleep(1.2 * attempt)

        raise RuntimeError(last_err)

    def retrieve_context_for_row(self, row: Dict[str, str]) -> str:
        query = (row.get("question") or "").strip()
        if not query:
            return ""

        wiki_link = _normalize_wiki_link(row.get("wiki_link", ""))
        candidate_indices = self.indices_by_link.get(wiki_link, [])
        if not candidate_indices:
            # fallback for malformed/missing link in row: search globally
            candidate_indices = list(range(len(self.chunks)))

        qvec = self._embed_query(query)

        cand_mat = self.emb_norm[candidate_indices]
        scores = cand_mat @ qvec
        local_top = np.argsort(-scores)[: self.top_k]

        pieces = []
        for rank, loc in enumerate(local_top, 1):
            idx = candidate_indices[int(loc)]
            ch = self.chunks[idx]
            text = (ch.get("text") or "").strip()
            if len(text) > self.max_chars_per_chunk:
                text = text[: self.max_chars_per_chunk].rstrip() + "..."
            pieces.append(
                f"[chunk {rank}] {text}"
            )

        return "\n".join(pieces)

    def build_contexts(self, rows: List[Dict[str, str]]) -> List[str]:
        contexts: List[str] = []
        print(f"[RAG] Building retrieved contexts for {len(rows)} rows")
        started = time.time()
        for i, row in enumerate(rows, 1):
            try:
                contexts.append(self.retrieve_context_for_row(row))
            except Exception as exc:  # noqa: BLE001
                contexts.append("")
                print(f"[RAG] row={i-1} retrieval error: {str(exc)[:200]}")

            if i % 25 == 0 or i == len(rows):
                elapsed = max(time.time() - started, 1e-6)
                speed = i / elapsed
                eta = int((len(rows) - i) / speed) if speed > 0 else -1
                eta_text = f"{eta}s" if eta >= 0 else "--"
                print(f"\r[RAG] retrieved {i}/{len(rows)} contexts ETA {eta_text}", end="", flush=True)
        print()
        return contexts


def read_prompt(prompt_path: Path) -> str:
    return prompt_path.read_text(encoding="utf-8").strip()


def build_eval_user_message(
    prompt_text: str,
    row: Dict[str, str],
    required_output_fields: List[str],
    rag_context: str = "",
) -> str:
    # Keep request compact to fit low credit/token limits.
    requested_headers = required_output_fields
    extracted_text = (row.get("extracted_text", "") or "")[:120]
    question = (row.get("question", "") or "")[:120]

    if rag_context.strip():
        return (
            f"{prompt_text}\n"
            f"CSV only, exactly 2 lines: header then one row. Header must be: {','.join(requested_headers)}\n"
            f"excerpt_text: {extracted_text}\n"
            f"retrieved_context_from_full_document:\n{rag_context}\n"
            f"question: {question}\n"
        )

    return (
        f"{prompt_text}\n"
        f"CSV only, exactly 2 lines: header then one row. Header must be: {','.join(requested_headers)}\n"
        f"text: {extracted_text}\n"
        f"question: {question}\n"
    )


def _extract_csv_lines(text: str, required_output_fields: List[str]) -> List[str]:
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        return []

    # Best effort: locate header line that contains all required output fields.
    for i in range(len(lines)):
        header_lower = lines[i].lower()
        if all(field in header_lower for field in required_output_fields):
            if i + 1 < len(lines):
                return [lines[i], lines[i + 1]]

    # Fallback: first two non-empty lines.
    return lines[:2]


def parse_single_eval_csv(response_text: str, required_output_fields: List[str]) -> Tuple[Dict[str, str], str]:
    lines = _extract_csv_lines(response_text, required_output_fields)
    if len(lines) < 2:
        return {}, "Could not find CSV header+row in model response"

    csv_payload = "\n".join(lines)
    try:
        reader = csv.DictReader(io.StringIO(csv_payload))
        rows = list(reader)
        if len(rows) != 1:
            return {}, f"Expected one CSV data row, got {len(rows)}"

        row = rows[0]
        missing = [f for f in required_output_fields if f not in row]
        if missing:
            return {}, f"Missing required output fields: {missing}"

        # Normalize + validate numeric fields depending on configured schema.
        numeric_ranges = {
            "complexity_level": (0, 3),
            "question_quality": (1, 5),
            "relevance": (1, 5),
            "linguistic_correctness_naturalness": (1, 5),
        }
        numeric_fields = [f for f in required_output_fields if f in numeric_ranges]

        for num_field in numeric_fields:
            raw = (row.get(num_field) or "").strip()
            if raw == "":
                return {}, f"Empty numeric field: {num_field}"
            try:
                val = int(raw)
            except ValueError:
                return {}, f"Non-integer value in {num_field}: {raw}"
            low, high = numeric_ranges[num_field]
            if not (low <= val <= high):
                return {}, f"{num_field} out of range: {val}"
            row[num_field] = str(val)

        if "identified_issues" in required_output_fields and not (row.get("identified_issues") or "").strip():
            row["identified_issues"] = "none"

        return row, ""
    except Exception as exc:  # noqa: BLE001
        return {}, f"CSV parse error: {exc}"


def call_openrouter_eval(
    api_key: str,
    model_id: str,
    prompt_text: str,
    row: Dict[str, str],
    required_output_fields: List[str],
    rag_context: str = "",
    timeout_seconds: int = 90,
    max_retries: int = 3,
    max_output_tokens: int = 64,
) -> Tuple[Dict[str, str], str]:
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

    user_prompt = build_eval_user_message(
        prompt_text,
        row,
        required_output_fields=required_output_fields,
        rag_context=rag_context,
    )
    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "system",
                "content": "Evaluate Hebrew QA. Output strict CSV only.",
            },
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens": max_output_tokens,
    }

    last_error = "Unknown OpenRouter error"
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload,
                timeout=timeout_seconds,
            )
            if response.status_code != 200:
                last_error = f"HTTP {response.status_code}: {response.text[:300]}"
            else:
                data = response.json()
                choices = data.get("choices", [])
                content = ""
                if choices:
                    content = (choices[0].get("message", {}) or {}).get("content", "")
                if not content:
                    last_error = "Empty response content"
                else:
                    parsed, parse_error = parse_single_eval_csv(content, required_output_fields)
                    if parse_error:
                        last_error = f"Invalid CSV output: {parse_error}"
                    else:
                        return parsed, ""
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)

        if attempt < max_retries:
            time.sleep(1.5 * attempt)

    return {}, f"ERROR: {last_error}"


def _worker(args: Tuple) -> Tuple[int, Dict[str, str], str]:
    (
        idx,
        api_key,
        model_id,
        prompt_text,
        row,
        required_output_fields,
        rag_context,
        timeout_seconds,
        max_retries,
        max_output_tokens,
    ) = args
    parsed, err = call_openrouter_eval(
        api_key=api_key,
        model_id=model_id,
        prompt_text=prompt_text,
        row=row,
        required_output_fields=required_output_fields,
        rag_context=rag_context,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        max_output_tokens=max_output_tokens,
    )
    return idx, parsed, err


def _progress_line(completed: int, total: int, start_time: float, label: str) -> str:
    if total <= 0:
        return f"{label} 0/0"
    ratio = min(max(completed / total, 0.0), 1.0)
    width = 28
    filled = int(width * ratio)
    bar = "#" * filled + "-" * (width - filled)
    elapsed = max(time.time() - start_time, 1e-6)
    speed = completed / elapsed if completed else 0.0
    eta = int((total - completed) / speed) if speed > 0 else -1
    eta_text = f"{eta}s" if eta >= 0 else "--"
    return (
        f"{label} [{bar}] {completed}/{total} "
        f"({ratio * 100:5.1f}%) ETA {eta_text}"
    )


def evaluate_model(
    rows: List[Dict[str, str]],
    model_label: str,
    model_id: str,
    api_key: str,
    prompt_text: str,
    required_output_fields: List[str],
    max_workers: int,
    timeout_seconds: int,
    max_retries: int,
    max_output_tokens: int,
    rag_contexts: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, str]], int, int]:
    print(f"\n[MODEL] {model_label} ({model_id})")
    print(f"[MODEL] rows={len(rows)}, workers={max_workers}")

    results: List[Dict[str, str]] = [dict(r) for r in rows]
    errors = 0

    work_items = [
        (
            i,
            api_key,
            model_id,
            prompt_text,
            row,
            required_output_fields,
            (rag_contexts[i] if rag_contexts and i < len(rag_contexts) else ""),
            timeout_seconds,
            max_retries,
            max_output_tokens,
        )
        for i, row in enumerate(rows)
    ]

    completed = 0
    start_ts = time.time()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_worker, item): item[0] for item in work_items}
        for future in as_completed(futures):
            idx, parsed, err = future.result()
            if err:
                errors += 1
                for f in required_output_fields:
                    results[idx][f] = ""
                results[idx]["evaluation_error"] = err
            else:
                for f in required_output_fields:
                    results[idx][f] = parsed.get(f, "")
                results[idx]["evaluation_error"] = ""

            results[idx]["evaluator_model_name"] = model_label
            results[idx]["evaluator_model_id"] = model_id

            completed += 1
            print(
                "\r" + _progress_line(completed, len(work_items), start_ts, "  evaluating"),
                end="",
                flush=True,
            )
    if work_items:
        print()

    success = len(rows) - errors
    print(f"[MODEL DONE] success={success}, errors={errors}")

    if errors:
        sample_errors = [
            (i, r.get("evaluation_error", ""))
            for i, r in enumerate(results)
            if (r.get("evaluation_error") or "").strip()
        ][:3]
        for i, err_msg in sample_errors:
            print(f"  sample_error row={i}: {err_msg[:240]}")

    # Fail-fast condition requested by user.
    if success == 0:
        raise SystemExit(
            f"[FATAL] Model {model_label} returned only errors for all {len(rows)} rows. Stopping."
        )

    # Retry only failed lines once if not all failed.
    if 0 < errors < len(rows):
        failed_indices = [i for i, r in enumerate(results) if (r.get("evaluation_error") or "").strip()]
        print(f"[RETRY] {model_label}: retrying {len(failed_indices)} failed rows once")

        retry_items = [
            (
                i,
                api_key,
                model_id,
                prompt_text,
                rows[i],
                required_output_fields,
                (rag_contexts[i] if rag_contexts and i < len(rag_contexts) else ""),
                timeout_seconds,
                max_retries,
                max_output_tokens,
            )
            for i in failed_indices
        ]

        fixed = 0
        retry_completed = 0
        retry_start_ts = time.time()
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_worker, item): item[0] for item in retry_items}
            for future in as_completed(futures):
                idx, parsed, err = future.result()
                if not err:
                    for f in required_output_fields:
                        results[idx][f] = parsed.get(f, "")
                    results[idx]["evaluation_error"] = ""
                    fixed += 1
                else:
                    # Persist final error after retry.
                    results[idx]["evaluation_error"] = err
                retry_completed += 1
                print(
                    "\r" + _progress_line(retry_completed, len(retry_items), retry_start_ts, "  retrying "),
                    end="",
                    flush=True,
                )
        if retry_items:
            print()

        errors_after_retry = sum(1 for r in results if (r.get("evaluation_error") or "").strip())
        print(
            f"[RETRY DONE] {model_label}: fixed={fixed}, "
            f"remaining_errors={errors_after_retry}"
        )
        return results, len(rows) - errors_after_retry, errors_after_retry

    return results, success, errors


def write_csv(path: Path, rows: List[Dict[str, str]], required_output_fields: List[str]) -> None:
    if not rows:
        raise SystemExit(f"No rows to write for {path}")

    # Keep original columns first, then append eval columns.
    original_fields = list(rows[0].keys())
    append_fields = required_output_fields + [
        "evaluation_error",
        "evaluator_model_name",
        "evaluator_model_id",
    ]

    fieldnames = []
    for f in original_fields + append_fields:
        if f not in fieldnames:
            fieldnames.append(f)

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_input_csv(input_path: Path) -> List[Dict[str, str]]:
    with input_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def row_needs_evaluation(row: Dict[str, str], required_output_fields: List[str]) -> bool:
    if (row.get("evaluation_error") or "").strip():
        return True
    return any(not (row.get(field) or "").strip() for field in required_output_fields)


def load_resume_rows(
    output_path: Path,
    input_rows: List[Dict[str, str]],
    required_output_fields: List[str],
) -> Tuple[List[Dict[str, str]], List[int]]:
    if not output_path.exists():
        return [dict(row) for row in input_rows], list(range(len(input_rows)))

    existing_rows = read_input_csv(output_path)
    if len(existing_rows) != len(input_rows):
        print(
            f"[RESUME] Existing file row count mismatch for {output_path.name} "
            f"({len(existing_rows)} vs {len(input_rows)}). Re-evaluating all rows."
        )
        return [dict(row) for row in input_rows], list(range(len(input_rows)))

    resume_rows = [dict(row) for row in existing_rows]
    pending_indices = [i for i, row in enumerate(resume_rows) if row_needs_evaluation(row, required_output_fields)]
    print(
        f"[RESUME] {output_path.name}: reusing {len(resume_rows) - len(pending_indices)} completed rows, "
        f"retrying {len(pending_indices)} rows"
    )
    return resume_rows, pending_indices


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate generated questions with two OpenRouter models using a shared evaluation prompt."
    )
    parser.add_argument(
        "--input-csv",
        default="output_for_q/all_questions_collated_openrouter.csv",
        help="Input CSV to evaluate",
    )
    parser.add_argument(
        "--prompt-file",
        default="output_for_q/prompt_for_eval.txt",
        help="Evaluation prompt text file",
    )
    parser.add_argument(
        "--output-folder",
        default="output_for_q",
        help="Folder for evaluation outputs",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=24,
        help="Concurrent API workers (increase for faster throughput)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=90,
        help="Per-request timeout",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Retries per request for transient failures",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=64,
        help="max_tokens sent to OpenRouter per evaluation request (lower to reduce credit usage)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional row limit for smoke tests (0 = all rows)",
    )
    parser.add_argument(
        "--resume-existing",
        action="store_true",
        help="Resume from existing per-model evaluation CSVs and only retry rows with missing fields or evaluation_error",
    )
    parser.add_argument(
        "--rag-assets-dir",
        default="",
        help="Optional directory created by prepare_wiki_rag_assets.py to retrieve top chunks per row",
    )
    parser.add_argument(
        "--rag-top-k",
        type=int,
        default=4,
        help="How many retrieved chunks to include per row when using --rag-assets-dir",
    )
    parser.add_argument(
        "--rag-max-chars-per-chunk",
        type=int,
        default=380,
        help="Per-chunk character cap injected into evaluator prompt when using RAG",
    )
    parser.add_argument(
        "--rag-embedding-model",
        default="",
        help="Optional override for query embedding model (defaults to assets manifest embedding_model)",
    )
    parser.add_argument(
        "--required-output-fields",
        default=",".join(DEFAULT_REQUIRED_OUTPUT_FIELDS),
        help="Comma-separated required CSV output fields expected from evaluator model",
    )
    args = parser.parse_args()

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is not set.")

    input_path = Path(args.input_csv)
    prompt_path = Path(args.prompt_file)
    output_folder = Path(args.output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise SystemExit(f"Input CSV not found: {input_path}")
    if not prompt_path.exists():
        raise SystemExit(f"Prompt file not found: {prompt_path}")

    rows = read_input_csv(input_path)
    if not rows:
        raise SystemExit(f"Input CSV has no rows: {input_path}")

    if args.limit > 0:
        rows = rows[: args.limit]
        print(f"[INFO] Using first {len(rows)} rows due to --limit")

    required_output_fields = [f.strip() for f in args.required_output_fields.split(",") if f.strip()]
    if not required_output_fields:
        raise SystemExit("--required-output-fields cannot be empty")

    prompt_text = read_prompt(prompt_path)

    rag_contexts: Optional[List[str]] = None
    if args.rag_assets_dir.strip():
        assets_dir = Path(args.rag_assets_dir)
        if not assets_dir.exists():
            raise SystemExit(f"RAG assets dir not found: {assets_dir}")
        retriever = RagChunkRetriever(
            assets_dir=assets_dir,
            api_key=api_key,
            embedding_model_override=args.rag_embedding_model,
            top_k=args.rag_top_k,
            max_chars_per_chunk=args.rag_max_chars_per_chunk,
        )
        rag_contexts = retriever.build_contexts(rows)

    base_name = input_path.stem
    summary = []

    for model_label, model_id in EVAL_MODELS.items():
        output_path = output_folder / f"{base_name}_eval_{model_label}.csv"

        if args.resume_existing:
            resume_rows, pending_indices = load_resume_rows(
                output_path,
                rows,
                required_output_fields,
            )
            if not pending_indices:
                print(f"[SKIP] {model_label}: no pending rows")
                summary.append((model_label, model_id, len(resume_rows), 0, str(output_path)))
                continue

            pending_rows = [resume_rows[i] for i in pending_indices]
            model_rows_partial, success_count, error_count = evaluate_model(
                rows=pending_rows,
                model_label=model_label,
                model_id=model_id,
                api_key=api_key,
                prompt_text=prompt_text,
                required_output_fields=required_output_fields,
                max_workers=args.max_workers,
                timeout_seconds=args.timeout_seconds,
                max_retries=args.max_retries,
                max_output_tokens=args.max_output_tokens,
                rag_contexts=([rag_contexts[i] for i in pending_indices] if rag_contexts else None),
            )

            for local_idx, global_idx in enumerate(pending_indices):
                resume_rows[global_idx] = model_rows_partial[local_idx]

            total_errors = sum(1 for row in resume_rows if (row.get("evaluation_error") or "").strip())
            total_success = len(resume_rows) - total_errors
            write_csv(output_path, resume_rows, required_output_fields)
            print(f"[WRITE] {output_path}")
            summary.append((model_label, model_id, total_success, total_errors, str(output_path)))
            continue

        model_rows, success_count, error_count = evaluate_model(
            rows=rows,
            model_label=model_label,
            model_id=model_id,
            api_key=api_key,
            prompt_text=prompt_text,
            required_output_fields=required_output_fields,
            max_workers=args.max_workers,
            timeout_seconds=args.timeout_seconds,
            max_retries=args.max_retries,
            max_output_tokens=args.max_output_tokens,
            rag_contexts=rag_contexts,
        )

        write_csv(output_path, model_rows, required_output_fields)
        print(f"[WRITE] {output_path}")

        summary.append((model_label, model_id, success_count, error_count, str(output_path)))

    print("\n=== Evaluation Summary ===")
    for model_label, model_id, success_count, error_count, path in summary:
        print(
            f"{model_label} ({model_id}): success={success_count}, errors={error_count}, output={path}"
        )


if __name__ == "__main__":
    main()
