"""
Build a Label Studio input file from data_prep_3/experiment/output/*.json,
using document metadata from data_prep_3/experiment/docs/.

Output: data_prep_3/experiment/annotation/labelstudio_tasks.json
        (same structure as annotation/ls_input/labelstudio_part1_tasks_new_expanded.json)
"""

import json
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # data_prep_3/experiment
DOCS_DIR = os.path.join(BASE, "docs")
OUTPUT_DIR = os.path.join(BASE, "output")
ANNOTATION_DIR = os.path.join(BASE, "annotation")

MAPPING_FILE = os.path.join(DOCS_DIR, "uuid_mapping.json")
OUTPUT_FILE = os.path.join(ANNOTATION_DIR, "labelstudio_tasks.json")

SOURCE_TO_DATASET = {
    "wiki": "wiki",
    "Il-hym": "il_hym",
    "knesset_short": "knesset",
}

LEVEL_TO_INT = {
    "level0": 0,
    "level1": 1,
    "level2": 2,
    "level3": 3,
}


def load_mapping(path):
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    return {item["uuid"]: item for item in items}


def load_output_files():
    records = {}
    for level in ["level0", "level1", "level2", "level3"]:
        path = os.path.join(OUTPUT_DIR, f"{level}_output.json")
        with open(path, encoding="utf-8") as f:
            items = json.load(f)
        for item in items:
            records[item["uuid"]] = {
                "question": item["question"],
                "reasoning": item["reasoning"],
            }
    return records


def read_doc(level, filename):
    """Return (doc_id, text, dataset_hint) for any supported file type."""
    filepath = os.path.join(DOCS_DIR, level, filename)
    ext = os.path.splitext(filename)[1].lower()
    doc_id = os.path.splitext(filename)[0]

    if ext == ".json":
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        text = data.get("text", "")
        return doc_id, text, "wiki"

    elif ext == ".jsonl":
        # Knesset protocol: first (and usually only) JSONL line
        with open(filepath, encoding="utf-8") as f:
            line = f.readline()
        data = json.loads(line)
        text = data.get("text", "")
        return doc_id, text, "knesset"

    elif ext == ".txt":
        with open(filepath, encoding="utf-8") as f:
            raw = f.read()
        # Header lines start with '#'; strip them, keep the body
        lines = raw.splitlines()
        body_lines = []
        for line in lines:
            if not line.startswith("#"):
                body_lines.append(line)
        text = "\n".join(body_lines).lstrip("\n")
        return doc_id, text, "il_hym"

    else:
        raise ValueError(f"Unsupported file extension: {ext} ({filename})")


def make_excerpt(text, max_chars=200):
    """Return the first ~200 visible characters of text as an excerpt."""
    excerpt = text[:max_chars]
    # Trim to last complete word if cut mid-word
    if len(text) > max_chars:
        last_space = excerpt.rfind(" ")
        if last_space > 0:
            excerpt = excerpt[:last_space]
    return excerpt


def build_tasks():
    mapping = load_mapping(MAPPING_FILE)
    output_records = load_output_files()

    tasks = []
    missing = []

    for uuid, out in output_records.items():
        if uuid not in mapping:
            missing.append(uuid)
            continue

        meta = mapping[uuid]
        level_str = meta["level"]
        source = meta["source"]
        filename = meta["filename"]

        doc_id, text, _ = read_doc(level_str, filename)

        dataset = SOURCE_TO_DATASET.get(source, source)
        level_int = LEVEL_TO_INT[level_str]
        excerpt = make_excerpt(text)

        task = {
            "data": {
                "record_id": uuid,
                "dataset": dataset,
                "doc_id": doc_id,
                "excerpt": excerpt,
                "question": out["question"],
                "text": text,
                "level": level_int,
                "reasoning": out["reasoning"],
            }
        }
        tasks.append(task)

    if missing:
        print(f"WARNING: {len(missing)} UUIDs from output files not found in mapping: {missing}")

    return tasks


def main():
    os.makedirs(ANNOTATION_DIR, exist_ok=True)
    tasks = build_tasks()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    print(f"Written {len(tasks)} tasks to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
