#!/usr/bin/env python3
"""Split vaadot_sample_mod.jsonl into per-(session_name, protocol_name) files."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path


def safe_part(value: str) -> str:
    value = value.strip()
    value = re.sub(r"[\\/\x00-\x1f]", "_", value)
    value = re.sub(r"\s+", "_", value)
    return value


def main() -> None:
    base_dir = Path(__file__).resolve().parents[1]
    noam_dir = base_dir / "noam"
    input_path = noam_dir / "vaadot_sample_mod.jsonl"
    mapping_path = noam_dir / "vaadot_per_req.json"
    output_dir = base_dir / "protocols"

    output_dir.mkdir(parents=True, exist_ok=True)

    mapping_list = json.loads(mapping_path.read_text(encoding="utf-8"))
    abb_by_session = {
        item.get("session_name", "").strip(): item.get("session_abb", "").strip()
        for item in mapping_list
        if item.get("session_name") and item.get("session_abb")
    }

    grouped = defaultdict(list)
    with input_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            session_name = (row.get("session_name") or "").strip()
            protocol_name = (row.get("protocol_name") or "").strip()
            grouped[(session_name, protocol_name)].append(row)

    missing_mappings = set()
    written_files = 0

    for (session_name, protocol_name), rows in grouped.items():
        session_abb = abb_by_session.get(session_name)
        if not session_abb:
            missing_mappings.add(session_name)
            session_abb = "unknown"

        file_name = f"{safe_part(session_abb)}_{safe_part(protocol_name)}.jsonl"
        out_path = output_dir / file_name

        with out_path.open("w", encoding="utf-8") as out:
            for row in rows:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")

        written_files += 1

    print(f"Done. Wrote {written_files} files to {output_dir}")
    print(f"Input rows: {sum(len(v) for v in grouped.values()):,}")
    print(f"Unique (session_name, protocol_name) pairs: {len(grouped):,}")

    if missing_mappings:
        print("Missing session_name -> session_abb mappings for:")
        for name in sorted(missing_mappings):
            print(f"- {name}")


if __name__ == "__main__":
    main()
