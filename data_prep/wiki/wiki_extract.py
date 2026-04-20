#!/usr/bin/env python3
"""
Random-ish balanced extractor for Hebrew Wikipedia.

Outputs UTF-8 JSONL records with article text and metadata.

Requirements implemented:
- Target number of articles (default 310)
- Length filter on plain-text extract (default 2000..60000 chars)
- Ignore non-main namespace pages and disambiguation pages
- Roughly even category coverage with randomness
- Single output category field based on sampling category
"""

from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests

API_URL = "https://he.wikipedia.org/w/api.php"


def clean_category_name(name: str) -> str:
    prefix = "קטגוריה:"
    if name.startswith(prefix):
        return name[len(prefix):]
    return name

# 20 broad categories for rough balancing.
CATEGORIES = [
    "קטגוריה:טכנולוגיה",
    "קטגוריה:מדע",
    "קטגוריה:ספורט",
    "קטגוריה:אמנות",
    "קטגוריה:מוזיקה",
    "קטגוריה:ספרות",
    "קטגוריה:קולנוע",
    "קטגוריה:היסטוריה",
    "קטגוריה:גיאוגרפיה",
    "קטגוריה:ביולוגיה",
    "קטגוריה:כימיה",
    "קטגוריה:פיזיקה",
    "קטגוריה:מתמטיקה",
    "קטגוריה:פילוסופיה",
    "קטגוריה:דת",
    "קטגוריה:חברה",
    "קטגוריה:כלכלה",
    "קטגוריה:פוליטיקה",
    "קטגוריה:רפואה",
    "קטגוריה:תחבורה",
]


@dataclass
class Candidate:
    pageid: int
    title: str


class WikiExtractor:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.rng = random.Random(args.seed)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "hewiki-extractor/1.0 "
                    "(research use; contact: local-script; requests via requests library)"
                )
            }
        )
        self.page_cache: Dict[int, Optional[dict]] = {}

    def api_get(self, params: dict) -> dict:
        for attempt in range(1, self.args.max_retries + 1):
            try:
                resp = self.session.get(API_URL, params=params, timeout=self.args.timeout)
                resp.raise_for_status()
                data = resp.json()
                if "error" in data:
                    raise RuntimeError(f"API error: {data['error']}")
                if self.args.request_sleep > 0:
                    time.sleep(self.args.request_sleep)
                return data
            except Exception:
                if attempt >= self.args.max_retries:
                    raise
                # Simple linear backoff to be polite and robust.
                time.sleep(attempt * 0.5)
        raise RuntimeError("Unreachable retry state")

    def fetch_category_pool(self, category: str, max_members: int) -> List[Candidate]:
        members: List[Candidate] = []
        seen = set()
        cmcontinue = None

        while len(members) < max_members:
            params = {
                "action": "query",
                "format": "json",
                "list": "categorymembers",
                "cmtitle": category,
                "cmnamespace": 0,
                "cmtype": "page",
                "cmlimit": 500,
            }
            if cmcontinue:
                params["cmcontinue"] = cmcontinue

            data = self.api_get(params)
            page_list = data.get("query", {}).get("categorymembers", [])
            if not page_list:
                break

            for p in page_list:
                pid = p.get("pageid")
                title = p.get("title")
                if isinstance(pid, int) and isinstance(title, str) and pid not in seen:
                    members.append(Candidate(pageid=pid, title=title))
                    seen.add(pid)
                    if len(members) >= max_members:
                        break

            cmcontinue = data.get("continue", {}).get("cmcontinue")
            if not cmcontinue:
                break

        self.rng.shuffle(members)
        return members

    def fetch_page_details(self, pageid: int) -> Optional[dict]:
        if pageid in self.page_cache:
            return self.page_cache[pageid]

        params = {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "prop": "info|extracts|pageprops|categories",
            "inprop": "url",
            "pageids": str(pageid),
            "explaintext": 1,
            "redirects": 1,
            "cllimit": "max",
            "clshow": "!hidden",
        }

        data = self.api_get(params)
        pages = data.get("query", {}).get("pages", [])
        if not pages:
            self.page_cache[pageid] = None
            return None

        page = pages[0]

        # Exclude non-main namespace, missing pages, and disambiguation.
        if page.get("missing") is True or page.get("ns") != 0:
            self.page_cache[pageid] = None
            return None

        pageprops = page.get("pageprops", {}) or {}
        title = page.get("title", "")
        if "disambiguation" in pageprops or (isinstance(title, str) and "(פירושונים)" in title):
            self.page_cache[pageid] = None
            return None

        text = page.get("extract") or ""
        if not isinstance(text, str):
            self.page_cache[pageid] = None
            return None

        text_len = len(text)
        if text_len < self.args.min_len or text_len > self.args.max_len:
            self.page_cache[pageid] = None
            return None

        record = {
            "pageid": page.get("pageid"),
            "title": title,
            "url": page.get("fullurl"),
            "text": text,
            "length_chars": text_len,
        }

        self.page_cache[pageid] = record
        return record

    def build_quotas(self, categories: List[str], target: int) -> Dict[str, int]:
        k = len(categories)
        base = target // k
        rem = target % k

        quotas = {c: base for c in categories}
        extra = categories[:]
        self.rng.shuffle(extra)
        for c in extra[:rem]:
            quotas[c] += 1
        return quotas

    def collect(self) -> List[dict]:
        categories = CATEGORIES[:]

        pools: Dict[str, List[Candidate]] = {}
        for c in categories:
            pool = self.fetch_category_pool(c, self.args.pool_size_per_category)
            pools[c] = pool
            print(f"Pool {c}: {len(pool)} candidates")

        quotas = self.build_quotas(categories, self.args.target)
        offsets = {c: 0 for c in categories}
        selected: List[dict] = []
        selected_ids = set()

        def try_take_from_category(category: str) -> bool:
            pool = pools[category]
            idx = offsets[category]
            while idx < len(pool):
                cand = pool[idx]
                idx += 1
                offsets[category] = idx

                if cand.pageid in selected_ids:
                    continue

                details = self.fetch_page_details(cand.pageid)
                if not details:
                    continue

                out = {
                    "id": details["pageid"],
                    "title": details["title"],
                    "url": details["url"],
                    "category": clean_category_name(category),
                    "length_chars": details["length_chars"],
                    "text": details["text"],
                    "source": "hewiki",
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                }
                selected.append(out)
                selected_ids.add(cand.pageid)
                return True
            return False

        # Pass 1: quota-driven selection (rough evenness).
        made_progress = True
        while len(selected) < self.args.target and made_progress:
            made_progress = False
            round_order = categories[:]
            self.rng.shuffle(round_order)

            for c in round_order:
                if quotas[c] <= 0:
                    continue
                if try_take_from_category(c):
                    quotas[c] -= 1
                    made_progress = True
                    if len(selected) >= self.args.target:
                        break

        # Pass 2: fallback fill from all remaining pools if any quota failed.
        if len(selected) < self.args.target:
            merged_remaining = []
            for c in categories:
                start = offsets[c]
                for cand in pools[c][start:]:
                    merged_remaining.append((c, cand))
            self.rng.shuffle(merged_remaining)

            for c, cand in merged_remaining:
                if len(selected) >= self.args.target:
                    break
                if cand.pageid in selected_ids:
                    continue
                details = self.fetch_page_details(cand.pageid)
                if not details:
                    continue

                out = {
                    "id": details["pageid"],
                    "title": details["title"],
                    "url": details["url"],
                    "category": clean_category_name(c),
                    "length_chars": details["length_chars"],
                    "text": details["text"],
                    "source": "hewiki",
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                }
                selected.append(out)
                selected_ids.add(cand.pageid)

        self.rng.shuffle(selected)
        return selected


def write_jsonl(records: List[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_summary(records: List[dict], summary_path: Path, args: argparse.Namespace) -> None:
    by_category = Counter(r["category"] for r in records)

    summary = {
        "target": args.target,
        "collected": len(records),
        "seed": args.seed,
        "length_filter": {"min": args.min_len, "max": args.max_len},
        "output_jsonl": str(args.output),
        "category_counts": dict(sorted(by_category.items(), key=lambda kv: (-kv[1], kv[0]))),
    }

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract random-ish balanced Hebrew Wikipedia articles to JSONL.")
    parser.add_argument("--target", type=int, default=310, help="Number of articles to collect.")
    parser.add_argument("--min-len", type=int, default=2000, help="Minimum article length in chars.")
    parser.add_argument("--max-len", type=int, default=60000, help="Maximum article length in chars.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
    parser.add_argument(
        "--pool-size-per-category",
        type=int,
        default=1200,
        help="How many category members to prefetch per category.",
    )
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds.")
    parser.add_argument("--max-retries", type=int, default=4, help="Max retries per API call.")
    parser.add_argument("--request-sleep", type=float, default=0.03, help="Sleep between API requests.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("downloaded/wiki-extract/hewiki_random_310.jsonl"),
        help="Output JSONL path.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("downloaded/wiki-extract/hewiki_random_310_summary.json"),
        help="Output summary JSON path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    extractor = WikiExtractor(args)

    print(
        f"Collecting target={args.target}, length=[{args.min_len},{args.max_len}], "
        f"seed={args.seed}"
    )
    records = extractor.collect()

    if len(records) < args.target:
        print(
            f"Warning: collected {len(records)} / {args.target}. "
            "Try larger --pool-size-per-category or another --seed."
        )

    write_jsonl(records, args.output)
    write_summary(records, args.summary, args)

    print(f"Wrote JSONL: {args.output}")
    print(f"Wrote summary: {args.summary}")


if __name__ == "__main__":
    main()
