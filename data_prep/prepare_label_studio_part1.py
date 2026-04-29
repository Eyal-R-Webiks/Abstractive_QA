"""Prepare Label Studio Part 1 (question validation) tasks.

Reads:
  - data_prep/questions/eval/all_questions_for_eval.jsonl  (JSON array of {UUID, excerpt, question})
  - data_prep/questions/generation/il-hym_wiki_full.jsonl   (JSONL with uuid, source_dataset, doc_id, text)
  - data_prep/questions/generation/kneeset_full.jsonl       (JSONL with uuid, source_dataset, doc_id, text)

Writes:
  - data_prep/questions/eval/labelstudio_part1_tasks.json   (JSON array of LS tasks)

Each LS task has the form:
  {"data": {"record_id", "source", "doc_id", "excerpt", "question", "text"}}
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULTS = {
    "input": REPO / "data_prep/questions/eval/all_questions_for_eval.jsonl",
    "full_files": [
        REPO / "data_prep/questions/generation/il-hym_wiki_full.jsonl",
        REPO / "data_prep/questions/generation/kneeset_full.jsonl",
    ],
    "output": REPO / "data_prep/questions/eval/labelstudio_part1_tasks.json",
}


def load_doc_index(paths: list[Path]) -> dict[str, dict]:
    idx: dict[str, dict] = {}
    for p in paths:
        with p.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                uuid = rec.get("uuid")
                if not uuid:
                    continue
                idx[uuid] = {
                    "source": rec.get("source_dataset", ""),
                    "doc_id": rec.get("doc_id", ""),
                    "text": rec.get("text", ""),
                }
    return idx


def load_questions(path: Path) -> list[dict]:
    """Input is a JSON array (despite the .jsonl extension)."""
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array in {path}")
    return data


def build_tasks(questions: list[dict], doc_idx: dict[str, dict]) -> tuple[list[dict], list[str]]:
    tasks: list[dict] = []
    missing: list[str] = []
    for q in questions:
        uuid = q.get("UUID") or q.get("uuid")
        if not uuid:
            continue
        doc = doc_idx.get(uuid)
        if not doc:
            missing.append(uuid)
            doc = {"source": "", "doc_id": "", "text": ""}
        tasks.append({
            "data": {
                "record_id": uuid,
                "source": doc["source"],
                "doc_id": doc["doc_id"],
                "excerpt": q.get("excerpt", ""),
                "question": q.get("question", ""),
                "text": doc["text"],
            }
        })
    return tasks, missing


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=DEFAULTS["input"])
    ap.add_argument("--full", type=Path, nargs="+", default=DEFAULTS["full_files"])
    ap.add_argument("--output", type=Path, default=DEFAULTS["output"])
    args = ap.parse_args()

    doc_idx = load_doc_index(args.full)
    questions = load_questions(args.input)
    tasks, missing = build_tasks(questions, doc_idx)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(tasks)} tasks to {args.output}")
    if missing:
        print(f"WARNING: {len(missing)} questions had no matching doc (showing up to 5): {missing[:5]}")


if __name__ == "__main__":
    main()
