import argparse
import json
import os
from pathlib import Path
from typing import List

import numpy as np
import requests
from dotenv import load_dotenv

OPENROUTER_EMBED_URL = "https://openrouter.ai/api/v1/embeddings"


def load_jsonl(path: Path) -> List[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def embed_query(api_key: str, model: str, query: str) -> np.ndarray:
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

    payload = {"model": model, "input": [query]}
    resp = requests.post(OPENROUTER_EMBED_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    vec = data["data"][0]["embedding"]
    arr = np.asarray(vec, dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm == 0:
        norm = 1.0
    return arr / norm


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieve top-k relevant pre-embedded wiki chunks for a query.")
    parser.add_argument("--query", required=True, help="Question/query text")
    parser.add_argument("--assets-dir", default="output_flashlite/rag_assets", help="Directory from prepare_wiki_rag_assets.py")
    parser.add_argument("--top-k", type=int, default=5, help="How many chunks to return")
    args = parser.parse_args()

    load_dotenv(Path(__file__).parent / ".env")
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is not set.")

    assets_dir = Path(args.assets_dir)
    manifest = json.loads((assets_dir / "manifest.json").read_text(encoding="utf-8"))
    embed_model = manifest["embedding_model"]

    chunks = load_jsonl(assets_dir / "chunks.jsonl")
    emb_norm = np.load(assets_dir / "chunk_embeddings_norm.npy")

    q = embed_query(api_key, embed_model, args.query)
    scores = emb_norm @ q
    top_idx = np.argsort(-scores)[: args.top_k]

    print(f"Query: {args.query}\n")
    print(f"Top {len(top_idx)} chunks:\n")
    for rank, i in enumerate(top_idx, 1):
        row = chunks[int(i)]
        score = float(scores[int(i)])
        source = f"{row.get('article_title','')} | {row.get('wiki_link','')} | chunk {row.get('chunk_index','')}"
        print(f"[{rank}] score={score:.4f} :: {source}")
        print(row.get("text", "")[:700])
        print("-" * 80)


if __name__ == "__main__":
    main()
