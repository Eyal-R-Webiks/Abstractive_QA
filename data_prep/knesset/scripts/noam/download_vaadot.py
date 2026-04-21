from datasets import load_dataset  # pip install datasets
import json

# ─── PARAMS ────────────────────────────────────────────────────────────────────
# This downloads sentences (no morphological annotations) from HuggingFace.
# Each line in the output is one sentence with its metadata.
# Run this once. Next step is build_protocols.py.

LOCAL_OUTPUT_FILE = "sentences_raw.jsonl"

DATASET_ID = "HaifaCLGroup/KnessetCorpus"
SUBSET     = "committee_no_morph_all_features_sentences"

# Only these fields are kept — enough to reconstruct protocols and filter later.
FIELDS_TO_KEEP = [
    "protocol_name",
    "session_name",
    "protocol_date",
    "knesset_number",
    "turn_num_in_protocol",
    "sent_num_in_turn",
    "speaker_name",
    "sentence_text",
]

# ─── FUNCTIONS ─────────────────────────────────────────────────────────────────

def serialize_value(value):
    # Some fields come back as Python datetime objects instead of strings
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def download_all_sentences():
    print(f"Connecting to {DATASET_ID} / {SUBSET} ...")
    dataset = load_dataset(DATASET_ID, name=SUBSET, split="train", streaming=True)

    saved = 0
    with open(LOCAL_OUTPUT_FILE, "w", encoding="utf-8") as out:
        for sentence in dataset:
            slim = {k: serialize_value(sentence.get(k)) for k in FIELDS_TO_KEEP}
            out.write(json.dumps(slim, ensure_ascii=False) + "\n")
            saved += 1
            if saved % 100_000 == 0:
                print(f"  {saved:,} sentences saved...")

    print(f"\nDone. {saved:,} sentences saved to {LOCAL_OUTPUT_FILE}")
    print("Next step: run build_protocols.py")


if __name__ == "__main__":
    download_all_sentences()
