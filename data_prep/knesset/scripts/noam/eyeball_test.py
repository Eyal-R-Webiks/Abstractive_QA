from datasets import load_dataset
from collections import defaultdict
import json

# This script is just for eyeballing. It downloads 2000 sentences,
# builds protocols from them, and saves a small sample to disk.
# It won't delete files so you can inspect the results.

SENTENCES_FILE  = "eyeball_sentences.jsonl"
PROTOCOLS_FILE  = "eyeball_protocols.jsonl"
SAMPLE_FILE     = "eyeball_sample.jsonl"

DOWNLOAD_LIMIT  = 2000   # sentences to pull from HF
MIN_CHARS       = 300
MAX_CHARS       = 30000

DATASET_ID = "HaifaCLGroup/KnessetCorpus"
SUBSET     = "committee_no_morph_all_features_sentences"
FIELDS_TO_KEEP = ["protocol_name", "session_name", "protocol_date", "knesset_number",
                  "turn_num_in_protocol", "sent_num_in_turn", "speaker_name", "sentence_text"]


def serialize_value(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def step1_download_sentences():
    print(f"Step 1: downloading {DOWNLOAD_LIMIT} sentences from HF...")
    ds = load_dataset(DATASET_ID, name=SUBSET, split="train", streaming=True)
    saved = 0
    with open(SENTENCES_FILE, "w", encoding="utf-8") as f:
        for row in ds:
            slim = {k: serialize_value(row.get(k)) for k in FIELDS_TO_KEEP}
            f.write(json.dumps(slim, ensure_ascii=False) + "\n")
            saved += 1
            if saved >= DOWNLOAD_LIMIT:
                break
    print(f"  saved {saved} sentences to {SENTENCES_FILE}")


def step2_build_protocols():
    print(f"Step 2: building protocols from {SENTENCES_FILE}...")
    protocols = defaultdict(lambda: {"meta": {}, "sentences": []})

    with open(SENTENCES_FILE, encoding="utf-8") as f:
        for line in f:
            s = json.loads(line)
            name = s["protocol_name"]
            if not protocols[name]["meta"]:
                protocols[name]["meta"] = {k: s[k] for k in ["protocol_name", "session_name", "protocol_date", "knesset_number"]}
            protocols[name]["sentences"].append({
                "turn":          s.get("turn_num_in_protocol", 0),
                "sent_in_turn":  s.get("sent_num_in_turn", 0),
                "sentence_text": s.get("sentence_text", ""),
            })

    with open(PROTOCOLS_FILE, "w", encoding="utf-8") as f:
        for data in protocols.values():
            sorted_sents = sorted(data["sentences"], key=lambda s: (s["turn"], s["sent_in_turn"]))
            text = " ".join(s["sentence_text"] for s in sorted_sents if s["sentence_text"])
            protocol = {**data["meta"], "text": text, "char_count": len(text)}
            f.write(json.dumps(protocol, ensure_ascii=False) + "\n")

    print(f"  built {len(protocols)} protocols, saved to {PROTOCOLS_FILE}")


def step3_collect_sample():
    print(f"Step 3: collecting protocols between {MIN_CHARS}-{MAX_CHARS} chars...")
    collected = []

    with open(PROTOCOLS_FILE, encoding="utf-8") as f:
        for line in f:
            p = json.loads(line)
            if MIN_CHARS <= p["char_count"] <= MAX_CHARS:
                collected.append(p)

    with open(SAMPLE_FILE, "w", encoding="utf-8") as f:
        for p in collected:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    print(f"  {len(collected)} protocols saved to {SAMPLE_FILE}")
    print("\nQuick preview:")
    for p in collected:
        print(f"  {p['session_name']:<35} | {str(p['protocol_date'])[:10]} | {p['char_count']} chars")
        print(f"  {p['text'][:120]}")
        print()


if __name__ == "__main__":
    step1_download_sentences()
    step2_build_protocols()
    step3_collect_sample()
    print(f"Done. Open {SAMPLE_FILE} to inspect.")
