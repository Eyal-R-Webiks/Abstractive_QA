#!/usr/bin/env python3
"""Create a stratified random sample of il-hym docs by genre."""

from __future__ import annotations

import argparse
import csv
import math
import random
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sample files from docs/ while preserving top-level genre distribution."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Path to il-hym root directory (contains index.csv and docs/).",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=600,
        help="Number of files to sample.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible sampling.",
    )
    parser.add_argument(
        "--min-chars",
        type=int,
        default=2000,
        help="Minimum free-text character length (metadata lines are excluded).",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=60000,
        help="Maximum free-text character length (metadata lines are excluded).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for sampled files (default: <root>/sample_600).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete output directory if it already exists.",
    )
    parser.add_argument(
        "--no-force-min-one",
        action="store_true",
        help="Allow tiny genres to receive 0 samples when proportional rounding gives 0.",
    )
    return parser.parse_args()


def read_index(index_path: Path) -> List[Dict[str, str]]:
    if not index_path.exists():
        raise FileNotFoundError(f"Missing index file: {index_path}")

    with index_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    required = {"filename", "genre"}
    if not rows:
        raise ValueError("index.csv is empty.")
    missing = required - set(rows[0].keys())
    if missing:
        raise ValueError(f"index.csv missing required columns: {sorted(missing)}")

    return rows


def free_text_length_without_metadata(file_path: Path) -> int:
    # Treat leading hashtag lines as metadata and exclude them from length constraints.
    lines = file_path.read_text(encoding="utf-8").splitlines()
    body_lines = [line for line in lines if not line.lstrip().startswith("#")]
    return len("\n".join(body_lines))


def proportional_quota(
    counts_by_genre: Dict[str, int],
    sample_size: int,
    force_min_one: bool,
) -> Dict[str, int]:
    total = sum(counts_by_genre.values())
    if sample_size > total:
        raise ValueError(f"sample_size={sample_size} exceeds available files={total}.")

    nonempty_genres = [genre for genre, count in counts_by_genre.items() if count > 0]
    if force_min_one and sample_size < len(nonempty_genres):
        raise ValueError(
            "sample_size is smaller than the number of non-empty genres when min-one is enabled. "
            f"sample_size={sample_size}, genres={len(nonempty_genres)}"
        )

    exact = {
        genre: (sample_size * count / total)
        for genre, count in counts_by_genre.items()
    }
    base = {genre: math.floor(value) for genre, value in exact.items()}

    if force_min_one:
        for genre in nonempty_genres:
            if base[genre] == 0:
                base[genre] = 1

    remainder = sample_size - sum(base.values())

    if remainder < 0:
        # Remove extras from genres that are furthest above their proportional target.
        ranking = sorted(
            nonempty_genres,
            key=lambda genre: (base[genre] - exact[genre], counts_by_genre[genre], genre),
            reverse=True,
        )
        to_remove = -remainder
        for genre in ranking:
            if to_remove == 0:
                break
            min_allowed = 1 if force_min_one else 0
            removable = base[genre] - min_allowed
            if removable <= 0:
                continue
            take = min(removable, to_remove)
            base[genre] -= take
            to_remove -= take

        if to_remove != 0:
            raise ValueError("Could not rebalance quotas after min-one enforcement.")
        remainder = 0

    # Largest remainder method: preserves total and best approximates proportions.
    ranking = sorted(
        counts_by_genre,
        key=lambda genre: (exact[genre] - base[genre], counts_by_genre[genre], genre),
        reverse=True,
    )
    for genre in ranking[:remainder]:
        base[genre] += 1

    for genre, quota in base.items():
        if quota > counts_by_genre[genre]:
            raise ValueError(
                f"Quota {quota} for genre={genre} exceeds available {counts_by_genre[genre]}"
            )

    return base


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    index_path = root / "index.csv"
    docs_dir = root / "docs"
    output_dir = (args.output_dir or (root / "sample_600")).resolve()

    if args.min_chars < 0 or args.max_chars < 0 or args.min_chars > args.max_chars:
        raise ValueError("Invalid length bounds: require 0 <= min_chars <= max_chars.")

    if not docs_dir.exists():
        raise FileNotFoundError(f"Missing docs directory: {docs_dir}")

    rows = read_index(index_path)

    rows_by_genre: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    missing_files = []
    out_of_range_files = 0
    unreadable_files = 0
    for row in rows:
        filename = row["filename"].strip()
        genre = row["genre"].strip()
        if not filename or not genre:
            continue

        src = docs_dir / filename
        if not src.exists():
            missing_files.append(filename)
            continue

        try:
            text_len = free_text_length_without_metadata(src)
        except OSError:
            unreadable_files += 1
            continue

        if text_len < args.min_chars or text_len > args.max_chars:
            out_of_range_files += 1
            continue

        rows_by_genre[genre].append(row)

    if not rows_by_genre:
        raise ValueError("No valid rows found after filtering missing files.")

    if missing_files:
        print(f"Warning: {len(missing_files)} files listed in index.csv were missing in docs/.")
    if unreadable_files:
        print(f"Warning: skipped {unreadable_files} unreadable files.")
    if out_of_range_files:
        print(
            f"Filtered out {out_of_range_files} files outside free-text length range "
            f"[{args.min_chars}, {args.max_chars}]."
        )

    counts = {genre: len(items) for genre, items in rows_by_genre.items()}
    quotas = proportional_quota(
        counts,
        args.sample_size,
        force_min_one=not args.no_force_min_one,
    )

    rng = random.Random(args.seed)
    selected_rows: List[Dict[str, str]] = []
    for genre in sorted(rows_by_genre):
        picked = rng.sample(rows_by_genre[genre], quotas[genre])
        selected_rows.extend(picked)

    rng.shuffle(selected_rows)

    if output_dir.exists() and args.overwrite:
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for row in selected_rows:
        filename = row["filename"].strip()
        src = docs_dir / filename
        dst = output_dir / filename
        shutil.copy2(src, dst)

    sampled_index_path = output_dir / "sampled_index.csv"
    fieldnames = list(rows[0].keys())
    with sampled_index_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(selected_rows)

    print(f"Sample complete: {len(selected_rows)} files copied to {output_dir}")
    print(f"Sample index: {sampled_index_path}")
    print(
        "Length constraint applied to free text only "
        f"(metadata lines excluded): {args.min_chars}-{args.max_chars} chars"
    )
    print("Genre distribution (population -> sample):")

    total_population = sum(counts.values())
    total_sample = len(selected_rows)
    for genre in sorted(counts):
        pop_n = counts[genre]
        samp_n = quotas[genre]
        pop_pct = 100 * pop_n / total_population
        samp_pct = 100 * samp_n / total_sample
        print(f"  {genre:20s} {pop_n:6d} ({pop_pct:6.2f}%) -> {samp_n:4d} ({samp_pct:6.2f}%)")


if __name__ == "__main__":
    main()
