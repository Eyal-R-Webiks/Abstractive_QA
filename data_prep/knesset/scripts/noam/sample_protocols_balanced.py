#!/usr/bin/env python3
"""Sample 320 protocol files with balanced session_name, knesset_number, and char_count."""

from __future__ import annotations

import json
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

SAMPLE_SIZE = 320
SEED = 42


def even_targets(total: int, keys: List[str]) -> Dict[str, int]:
    keys_sorted = sorted(keys)
    base = total // len(keys_sorted)
    rem = total % len(keys_sorted)
    targets = {k: base for k in keys_sorted}
    for k in keys_sorted[:rem]:
        targets[k] += 1
    return targets


def clear_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def quantile_edges(values: List[int], n_bins: int) -> List[int]:
    s = sorted(values)
    edges: List[int] = []
    for i in range(1, n_bins):
        idx = int(i * len(s) / n_bins)
        if idx >= len(s):
            idx = len(s) - 1
        edges.append(s[idx])
    return edges


def bin_index(value: int, edges: List[int]) -> int:
    b = 0
    while b < len(edges) and value > edges[b]:
        b += 1
    return b


def load_records(protocols_dir: Path) -> List[dict]:
    records: List[dict] = []
    for fp in sorted(protocols_dir.glob("*.jsonl")):
        with fp.open("r", encoding="utf-8") as f:
            line = ""
            for raw in f:
                raw = raw.strip()
                if raw:
                    line = raw
                    break
            if not line:
                continue
            row = json.loads(line)

        session = str(row.get("session_name", "")).strip()
        knesset = str(row.get("knesset_number", "")).strip()
        char_count = int(row.get("char_count", 0))

        if not session or not knesset or char_count <= 0:
            continue

        records.append(
            {
                "path": fp,
                "name": fp.name,
                "session": session,
                "knesset": knesset,
                "char_count": char_count,
            }
        )
    return records


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    protocols_dir = repo_root / "knesset" / "protocols"
    output_dir = repo_root / "knesset" / "sample"

    rng = random.Random(SEED)
    records = load_records(protocols_dir)
    if len(records) < SAMPLE_SIZE:
        raise ValueError(f"Not enough records to sample: have {len(records)}, need {SAMPLE_SIZE}")

    session_values = sorted({r["session"] for r in records})
    session_targets = even_targets(SAMPLE_SIZE, session_values)

    available_per_session = Counter(r["session"] for r in records)
    for s, t in session_targets.items():
        if available_per_session[s] < t:
            raise ValueError(f"Not enough docs for session '{s}': have {available_per_session[s]}, need {t}")

    knesset_values = sorted({r["knesset"] for r in records})
    knesset_targets = even_targets(SAMPLE_SIZE, knesset_values)

    n_char_bins = len(knesset_values)
    char_edges = quantile_edges([r["char_count"] for r in records], n_char_bins)
    for r in records:
        r["char_bin"] = str(bin_index(r["char_count"], char_edges))
    char_bin_values = [str(i) for i in range(n_char_bins)]
    char_bin_targets = even_targets(SAMPLE_SIZE, char_bin_values)

    selected: List[dict] = []
    chosen = set()
    session_counts = Counter()
    knesset_counts = Counter()
    char_bin_counts = Counter()

    while len(selected) < SAMPLE_SIZE:
        candidates = [
            r
            for r in records
            if r["name"] not in chosen and session_counts[r["session"]] < session_targets[r["session"]]
        ]
        if not candidates:
            raise RuntimeError("Ran out of candidates before reaching target sample size")

        best_score = None
        best: List[dict] = []
        for r in candidates:
            deficit_k = max(0, knesset_targets[r["knesset"]] - knesset_counts[r["knesset"]])
            deficit_c = max(0, char_bin_targets[r["char_bin"]] - char_bin_counts[r["char_bin"]])
            rem_s = session_targets[r["session"]] - session_counts[r["session"]]
            score = (deficit_k + deficit_c, rem_s)
            if best_score is None or score > best_score:
                best_score = score
                best = [r]
            elif score == best_score:
                best.append(r)

        pick = rng.choice(best)
        selected.append(pick)
        chosen.add(pick["name"])
        session_counts[pick["session"]] += 1
        knesset_counts[pick["knesset"]] += 1
        char_bin_counts[pick["char_bin"]] += 1

    clear_directory(output_dir)
    for r in selected:
        shutil.copy2(r["path"], output_dir / r["name"])

    print(f"Wrote {len(selected)} files to {output_dir}")
    print("Session distribution:")
    for s in sorted(session_counts):
        print(f"  {s}: {session_counts[s]} (target {session_targets[s]})")

    print("Knesset distribution:")
    for k in sorted(knesset_counts):
        print(f"  {k}: {knesset_counts[k]} (target {knesset_targets[k]})")

    print("Char-count bin distribution:")
    for b in sorted(char_bin_counts, key=int):
        print(f"  bin {b}: {char_bin_counts[b]} (target {char_bin_targets[b]})")

    print("Char-count bin edges (upper bounds for bins 0..n-2):")
    print(f"  {char_edges}")


if __name__ == "__main__":
    main()
