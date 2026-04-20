import argparse
import csv
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import unquote

import numpy as np
import requests
from dotenv import load_dotenv
from tqdm import tqdm

WIKI_API = "https://he.wikipedia.org/w/api.php"
OPENROUTER_EMBED_URL = "https://openrouter.ai/api/v1/embeddings"


def normalize_wiki_link(link: str) -> str:
    # Some links in the dataset may include a trailing ';'
    return (link or "").strip().rstrip(";")


def title_from_link(link: str) -> str:
    if "/wiki/" not in link:
        return ""
    title = link.split("/wiki/")[-1]
    return unquote(title).replace("_", " ")


def load_articles_from_input(input_csv: Path, max_articles: int = 0) -> List[Dict[str, str]]:
    rows = []
    with input_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    by_link: Dict[str, Dict[str, str]] = {}
    for r in rows:
        link = normalize_wiki_link(r.get("wiki_link", ""))
        if not link:
            continue
        if link not in by_link:
            by_link[link] = {
                "wiki_link": link,
                "article_title": (r.get("article_title") or "").strip() or title_from_link(link),
                "topic": (r.get("topic") or "").strip(),
            }

    articles = list(by_link.values())
    if max_articles > 0:
        articles = articles[:max_articles]
    return articles


def fetch_wikipedia_extract(title: str, timeout: int = 30) -> str:
    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts",
        "explaintext": True,
        "format": "json",
    }
    headers = {"User-Agent": "PLExp-RAG-Prep/1.0"}
    resp = requests.get(WIKI_API, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    pages = data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()), {})
    return (page.get("extract") or "").strip()


def chunk_text(text: str, chunk_size: int, overlap: int) -> List[Tuple[int, int, str]]:
    text = " ".join(text.split())
    if not text:
        return []

    chunks: List[Tuple[int, int, str]] = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + chunk_size, n)

        # Prefer ending at a whitespace boundary when possible.
        if end < n:
            ws = text.rfind(" ", start, end)
            if ws > start + int(chunk_size * 0.6):
                end = ws

        chunk = text[start:end].strip()
        if chunk:
            chunks.append((start, end, chunk))

        if end >= n:
            break

        start = max(0, end - overlap)

    return chunks


def openrouter_embed_batch(
    api_key: str,
    model: str,
    texts: List[str],
    timeout_seconds: int = 90,
    max_retries: int = 4,
) -> List[List[float]]:
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

    payload = {"model": model, "input": texts}

    last_err = "Unknown embeddings error"
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                OPENROUTER_EMBED_URL,
                headers=headers,
                json=payload,
                timeout=timeout_seconds,
            )
            if resp.status_code != 200:
                last_err = f"HTTP {resp.status_code}: {resp.text[:300]}"
            else:
                data = resp.json()
                arr = data.get("data", [])
                # Ensure order by index
                arr = sorted(arr, key=lambda x: x.get("index", 0))
                vectors = [item.get("embedding", []) for item in arr]
                if len(vectors) != len(texts):
                    last_err = f"Embedding count mismatch: got {len(vectors)}, expected {len(texts)}"
                else:
                    return vectors
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)

        if attempt < max_retries:
            time.sleep(1.5 * attempt)

    raise RuntimeError(last_err)


def save_jsonl(path: Path, rows: List[Dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_jsonl(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Hebrew Wikipedia articles from dataset links, chunk, embed, and build reusable RAG assets."
    )
    parser.add_argument(
        "--input-csv",
        default="output_flashlite/all_questions_collated_flashlite.csv",
        help="CSV containing wiki_link/article_title/topic columns",
    )
    parser.add_argument(
        "--output-dir",
        default="output_flashlite/rag_assets",
        help="Directory to save fetched articles, chunks, and embeddings",
    )
    parser.add_argument(
        "--embedding-model",
        default="openai/text-embedding-3-small",
        help="OpenRouter embedding model id",
    )
    parser.add_argument("--chunk-size", type=int, default=700, help="Chunk size in characters")
    parser.add_argument("--chunk-overlap", type=int, default=120, help="Chunk overlap in characters")
    parser.add_argument("--batch-size", type=int, default=64, help="Embedding batch size")
    parser.add_argument("--max-articles", type=int, default=0, help="Optional cap for quick pilots")
    parser.add_argument(
        "--refetch",
        action="store_true",
        help="Refetch articles from Wikipedia even if cache file exists",
    )
    args = parser.parse_args()

    load_dotenv(Path(__file__).parent / ".env")
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is not set.")

    input_csv = Path(args.input_csv)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not input_csv.exists():
        raise SystemExit(f"Input CSV not found: {input_csv}")

    articles_file = out_dir / "articles.jsonl"
    chunks_file = out_dir / "chunks.jsonl"
    embeddings_file = out_dir / "chunk_embeddings.npy"
    manifest_file = out_dir / "manifest.json"

    articles_meta = load_articles_from_input(input_csv, args.max_articles)
    print(f"[INFO] unique articles in input: {len(articles_meta)}")

    cached_by_link = {}
    if articles_file.exists() and not args.refetch:
        for row in load_jsonl(articles_file):
            cached_by_link[row.get("wiki_link", "")] = row

    fetched_rows: List[Dict] = []
    for art in tqdm(articles_meta, desc="Fetching articles"):
        link = art["wiki_link"]
        if link in cached_by_link:
            fetched_rows.append(cached_by_link[link])
            continue

        title = art["article_title"] or title_from_link(link)
        text = ""
        err = ""
        try:
            text = fetch_wikipedia_extract(title)
        except Exception as exc:  # noqa: BLE001
            err = str(exc)

        fetched_rows.append(
            {
                "wiki_link": link,
                "article_title": title,
                "topic": art.get("topic", ""),
                "full_text": text,
                "fetch_error": err,
            }
        )

    save_jsonl(articles_file, fetched_rows)

    valid_articles = [r for r in fetched_rows if (r.get("full_text") or "").strip()]
    print(f"[INFO] fetched successfully: {len(valid_articles)}/{len(fetched_rows)}")

    chunk_rows: List[Dict] = []
    for article_idx, art in enumerate(tqdm(valid_articles, desc="Chunking articles")):
        pieces = chunk_text(art["full_text"], args.chunk_size, args.chunk_overlap)
        for chunk_idx, (start, end, txt) in enumerate(pieces):
            chunk_rows.append(
                {
                    "chunk_id": f"a{article_idx}_c{chunk_idx}",
                    "wiki_link": art["wiki_link"],
                    "article_title": art.get("article_title", ""),
                    "topic": art.get("topic", ""),
                    "chunk_index": chunk_idx,
                    "start_char": start,
                    "end_char": end,
                    "text": txt,
                }
            )

    if not chunk_rows:
        raise SystemExit("No chunks were produced. Check fetched article text content.")

    save_jsonl(chunks_file, chunk_rows)
    print(f"[INFO] total chunks: {len(chunk_rows)}")

    all_texts = [r["text"] for r in chunk_rows]
    vectors: List[List[float]] = []
    for i in tqdm(range(0, len(all_texts), args.batch_size), desc="Embedding chunks"):
        batch = all_texts[i : i + args.batch_size]
        batch_vecs = openrouter_embed_batch(
            api_key=api_key,
            model=args.embedding_model,
            texts=batch,
        )
        vectors.extend(batch_vecs)

    emb = np.asarray(vectors, dtype=np.float32)
    np.save(embeddings_file, emb)

    # Precompute normalized matrix for fast cosine search with numpy.
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    emb_norm = emb / norms
    np.save(out_dir / "chunk_embeddings_norm.npy", emb_norm)

    manifest = {
        "input_csv": str(input_csv),
        "embedding_model": args.embedding_model,
        "chunk_size": args.chunk_size,
        "chunk_overlap": args.chunk_overlap,
        "num_articles": len(valid_articles),
        "num_chunks": len(chunk_rows),
        "embedding_dim": int(emb.shape[1]),
        "files": {
            "articles": articles_file.name,
            "chunks": chunks_file.name,
            "embeddings": embeddings_file.name,
            "embeddings_norm": "chunk_embeddings_norm.npy",
        },
    }
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n[DONE] RAG assets prepared")
    print(f"  - {articles_file}")
    print(f"  - {chunks_file}")
    print(f"  - {embeddings_file}")
    print(f"  - {out_dir / 'chunk_embeddings_norm.npy'}")
    print(f"  - {manifest_file}")


if __name__ == "__main__":
    main()
