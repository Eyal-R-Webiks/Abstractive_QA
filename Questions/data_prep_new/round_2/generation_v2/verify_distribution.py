import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional

SOURCE_ALIASES = {
    "il_hym": "il-hym",
    "il-hym": "il-hym",
    "israel_hayom": "il-hym",
    "hewiki": "wiki",
    "wiki": "wiki",
    "knesset": "knesset",
}

LEVELS = ["0", "1", "2", "3"]
SOURCES = ["il-hym", "knesset", "wiki"]


def canonicalize_source(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return SOURCE_ALIASES.get(value.strip().lower(), value.strip().lower())


def load_rows(path: Path) -> List[dict]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            rows = json.load(f)
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def level_str_from_row(row: dict) -> Optional[str]:
    if "level" in row and str(row.get("level", "")).strip() != "":
        return str(row.get("level")).strip()
    if "level_intended" in row and str(row.get("level_intended", "")).strip() != "":
        return str(row.get("level_intended")).strip()
    return None


def count_level_source(rows: List[dict]) -> Dict[str, Dict[str, int]]:
    matrix: Dict[str, Dict[str, int]] = {
        lvl: {src: 0 for src in SOURCES} for lvl in LEVELS
    }

    for row in rows:
        if not isinstance(row, dict):
            continue
        lvl = level_str_from_row(row)
        src = canonicalize_source(row.get("source"))
        if lvl in matrix and src in matrix[lvl]:
            matrix[lvl][src] += 1

    return matrix


def build_record_source_map(good_rows: List[dict], bad_rows: List[dict]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}

    for rows in [good_rows, bad_rows]:
        for row in rows:
            if not isinstance(row, dict):
                continue
            record_id = row.get("record_id") or row.get("uuid")
            src = canonicalize_source(row.get("source"))
            if record_id and src:
                mapping[str(record_id)] = src

    return mapping


def input_source_distribution(input_path: Path, record_source_map: Dict[str, str]) -> Dict[str, int]:
    rows = load_rows(input_path)
    counter = Counter()

    for row in rows:
        if not isinstance(row, dict):
            continue
        src = canonicalize_source(row.get("source"))
        if not src:
            rec = row.get("uuid")
            if rec is not None:
                src = record_source_map.get(str(rec))
        if src:
            counter[src] += 1
        else:
            counter["unknown"] += 1

    return dict(counter)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify level/source distribution without exposing question text")
    parser.add_argument("--root", default="data_prep_new/second_round")
    parser.add_argument("--good-path", default="expriment_good_questions.json")
    parser.add_argument("--bad-path", default="experiment_bad_questions.json")
    parser.add_argument("--input-dir", default="copies_from_old/input")
    parser.add_argument("--output", default="generation_v2/distribution_report.json")
    args = parser.parse_args()

    root = Path(args.root)
    good_path = root / args.good_path
    bad_path = root / args.bad_path

    good_rows = load_rows(good_path)
    bad_rows = load_rows(bad_path)

    good_matrix = count_level_source(good_rows)
    bad_matrix = count_level_source(bad_rows)

    record_source_map = build_record_source_map(good_rows, bad_rows)

    input_dist = {}
    for level in ["level0", "level1", "level2", "level3"]:
        input_path = root / args.input_dir / f"{level}_input.json"
        input_dist[level] = input_source_distribution(input_path, record_source_map)

    missing_good_cells = []
    for lvl in LEVELS:
        for src in SOURCES:
            if good_matrix[lvl][src] == 0:
                missing_good_cells.append({"level": lvl, "source": src})

    report = {
        "summary": {
            "good_pool_size": len(good_rows),
            "bad_pool_size": len(bad_rows),
            "missing_good_level_source_cells": missing_good_cells,
            "good_has_full_level_source_coverage": len(missing_good_cells) == 0,
        },
        "good_pool_level_source_counts": good_matrix,
        "bad_pool_level_source_counts": bad_matrix,
        "input_source_distribution_inferred": input_dist,
        "note": "No question text is included in this report.",
    }

    output_path = root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Distribution report written to: {output_path}")


if __name__ == "__main__":
    main()
