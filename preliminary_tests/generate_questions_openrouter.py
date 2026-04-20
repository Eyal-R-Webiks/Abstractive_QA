import argparse
import csv
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

# Load .env from the project root (same directory as this script)
load_dotenv(Path(__file__).parent / ".env")

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Default OpenRouter model IDs for the requested providers.
DEFAULT_MODELS: Dict[str, str] = {
    "claude_3_7_sonnet": "anthropic/claude-3.7-sonnet",
    "gemini_2_5_pro": "google/gemini-2.5-pro",
    "gpt_4o": "openai/gpt-4o",
}

SYSTEM_PROMPT = (
    "Read the Hebrew text and ask one natural-sounding information-seeking "
    "question in Hebrew that is interesting and whose answer cannot be "
    "simply extracted verbatim from the given text. Return only the question."
)

TEXT_COLUMN_CANDIDATES = [
    "extracted_text",
    "passage",
    "sentence_text",
    "sample",
    "text",
]


def choose_text_column(fieldnames: List[str]) -> Optional[str]:
    for candidate in TEXT_COLUMN_CANDIDATES:
        if candidate in fieldnames:
            return candidate
    return None


def build_even_random_assignments(
    item_count: int, model_names: List[str], seed: int
) -> List[str]:
    if item_count <= 0:
        return []

    base = item_count // len(model_names)
    remainder = item_count % len(model_names)

    assignments: List[str] = []
    for name in model_names:
        assignments.extend([name] * base)

    # Add one extra assignment to the first N models.
    assignments.extend(model_names[:remainder])

    rng = random.Random(seed)
    rng.shuffle(assignments)
    return assignments


def call_openrouter(
    api_key: str,
    model_id: str,
    text: str,
    timeout_seconds: int = 90,
    max_retries: int = 3,
) -> str:
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

    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Hebrew text:\n{text}\n\nQuestion in Hebrew:",
            },
        ],
        "temperature": 0.9,
        "max_tokens": 120,
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

            if response.status_code == 200:
                data = response.json()
                choices = data.get("choices", [])
                if choices and choices[0].get("message", {}).get("content"):
                    question = choices[0]["message"]["content"].strip()
                    first_line = question.splitlines()[0].strip()
                    if first_line:
                        return first_line

                # Treat empty content as a retryable transient response.
                last_error = "Empty response content"
            else:
                last_error = f"HTTP {response.status_code}: {response.text[:300]}"
        except Exception as exc:
            last_error = str(exc)

        # Small backoff for transient errors.
        if attempt < max_retries:
            time.sleep(1.5 * attempt)

    return f"ERROR: {last_error}"


def _call_one(args: Tuple) -> Tuple[int, str, str]:
    """Worker: returns (row_index, question, error)."""
    idx, api_key, model_id, text = args
    result = call_openrouter(api_key=api_key, model_id=model_id, text=text)
    if result.startswith("ERROR:"):
        return idx, "", result
    return idx, result, ""


def process_csv_file(
    input_path: Path,
    output_path: Path,
    api_key: str,
    model_map: Dict[str, str],
    seed: int,
    max_workers: int = 8,
) -> None:
    with input_path.open("r", encoding="utf-8", newline="") as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    text_column = choose_text_column(fieldnames)
    if not text_column:
        print(f"[SKIP] {input_path.name}: no recognized text column in {fieldnames}")
        return

    populated_indices = [i for i, r in enumerate(rows) if (r.get(text_column) or "").strip()]
    model_names = list(model_map.keys())
    assignments = build_even_random_assignments(len(populated_indices), model_names, seed)

    model_by_row_index: Dict[int, str] = {
        row_idx: assignments[pos] for pos, row_idx in enumerate(populated_indices)
    }

    # Preserve every input column; append generation columns at the end.
    extra_cols = ["question", "model_name", "model_id", "generation_error"]
    output_fieldnames = fieldnames + [c for c in extra_cols if c not in fieldnames]

    print(
        f"[INFO] {input_path.name}: rows={len(rows)}, rows_with_text={len(populated_indices)}, "
        f"text_column={text_column}, workers={max_workers}"
    )

    # Pre-fill results for empty rows; build work items for rows with text.
    results: Dict[int, Dict] = {}
    work_items = []
    model_counts = {name: 0 for name in model_names}

    for idx, row in enumerate(rows):
        text = (row.get(text_column) or "").strip()
        if not text:
            results[idx] = {"question": "", "model_name": "", "model_id": "", "generation_error": "No source text"}
        else:
            model_name = model_by_row_index[idx]
            model_id = model_map[model_name]
            work_items.append((idx, api_key, model_id, text))
            results[idx] = {"question": None, "model_name": model_name, "model_id": model_id, "generation_error": ""}

    completed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_call_one, item): item[0] for item in work_items}
        for future in as_completed(futures):
            idx, question, error = future.result()
            results[idx]["question"] = question
            results[idx]["generation_error"] = error
            model_name = results[idx]["model_name"]
            if not error:
                model_counts[model_name] += 1
            completed += 1
            if completed % 20 == 0:
                print(f"  completed {completed}/{len(work_items)} API calls")

    with output_path.open("w", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=output_fieldnames)
        writer.writeheader()
        for idx, row in enumerate(rows):
            row.update(results[idx])
            writer.writerow(row)

    print(f"[DONE] {input_path.name} -> {output_path.name}")
    print(f"       model usage counts: {model_counts}")


def repair_failed_rows_in_outputs(
    output_folder: Path,
    api_key: str,
    max_workers: int = 8,
) -> None:
    output_files = sorted(output_folder.glob("*_q_openrouter.csv"))
    if not output_files:
        raise SystemExit(f"No generated output CSV files found in {output_folder}")

    repaired_total = 0
    for output_path in output_files:
        with output_path.open("r", encoding="utf-8", newline="") as infile:
            reader = csv.DictReader(infile)
            fieldnames = reader.fieldnames or []
            rows = list(reader)

        text_column = choose_text_column(fieldnames)
        if not text_column:
            print(f"[SKIP] {output_path.name}: no recognized text column")
            continue

        work_items = []
        for idx, row in enumerate(rows):
            text = (row.get(text_column) or "").strip()
            question = (row.get("question") or "").strip()
            err = (row.get("generation_error") or "").strip()
            model_id = (row.get("model_id") or "").strip()

            if not text or not model_id:
                continue

            if question and not err:
                continue

            work_items.append((idx, api_key, model_id, text))

        if not work_items:
            print(f"[REPAIR] {output_path.name}: no failed rows")
            continue

        print(f"[REPAIR] {output_path.name}: retrying {len(work_items)} failed/empty rows")
        completed = 0
        repaired_file = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_call_one, item): item[0] for item in work_items}
            for future in as_completed(futures):
                idx, question, error = future.result()
                if question and not error:
                    rows[idx]["question"] = question
                    rows[idx]["generation_error"] = ""
                    repaired_file += 1
                else:
                    rows[idx]["generation_error"] = error or "ERROR: Empty response content"
                completed += 1
                if completed % 20 == 0:
                    print(f"  repaired {completed}/{len(work_items)} rows")

        with output_path.open("w", encoding="utf-8", newline="") as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        repaired_total += repaired_file
        print(f"[REPAIR DONE] {output_path.name}: fixed {repaired_file}/{len(work_items)} rows")

    print(f"[REPAIR SUMMARY] total fixed rows: {repaired_total}")


def collate_output_tables(output_folder: Path, combined_filename: str = "all_questions_collated_openrouter.csv") -> Path:
    output_files = sorted(output_folder.glob("*_q_openrouter.csv"))
    if not output_files:
        raise SystemExit(f"No generated output CSV files found in {output_folder}")

    # Build a stable union of all columns and add source filename for traceability.
    union_fields: List[str] = []
    for csv_path in output_files:
        with csv_path.open("r", encoding="utf-8", newline="") as infile:
            reader = csv.DictReader(infile)
            file_fields = reader.fieldnames or []
        for field in file_fields:
            if field not in union_fields:
                union_fields.append(field)

    if "source_file" not in union_fields:
        union_fields.append("source_file")

    combined_path = output_folder / combined_filename
    total_rows = 0
    with combined_path.open("w", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=union_fields)
        writer.writeheader()

        for csv_path in output_files:
            with csv_path.open("r", encoding="utf-8", newline="") as infile:
                reader = csv.DictReader(infile)
                for row in reader:
                    full_row = {field: row.get(field, "") for field in union_fields}
                    full_row["source_file"] = csv_path.name
                    writer.writerow(full_row)
                    total_rows += 1

    print(f"[DONE] Collated {len(output_files)} files into {combined_path.name} ({total_rows} rows)")
    return combined_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Hebrew questions from CSV lines using OpenRouter with balanced multi-model routing."
    )
    parser.add_argument("--input-folder", default="input_for_q", help="Folder with input CSV files")
    parser.add_argument("--output-folder", default="output_for_q", help="Folder for output CSV files")
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible model assignment",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=8,
        help="Number of concurrent API calls (default: 8)",
    )
    parser.add_argument(
        "--retry-failed-only",
        action="store_true",
        help="Retry only failed/empty rows in existing output files instead of full regeneration",
    )
    args = parser.parse_args()

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is not set.")

    input_folder = Path(args.input_folder)
    output_folder = Path(args.output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    if args.retry_failed_only:
        repair_failed_rows_in_outputs(
            output_folder=output_folder,
            api_key=api_key,
            max_workers=args.max_workers,
        )
        collate_output_tables(output_folder)
        print("Failed-row repair complete.")
        return

    input_files = sorted(input_folder.glob("*.csv"))
    if not input_files:
        raise SystemExit(f"No CSV files found in {input_folder}")

    print(f"Found {len(input_files)} input files.")
    for input_path in input_files:
        output_name = input_path.name.replace(".csv", "_q_openrouter.csv")
        output_path = output_folder / output_name
        process_csv_file(
            input_path=input_path,
            output_path=output_path,
            api_key=api_key,
            model_map=DEFAULT_MODELS,
            seed=args.seed,
            max_workers=args.max_workers,
        )

    collate_output_tables(output_folder)
    print("All files processed.")


if __name__ == "__main__":
    main()
