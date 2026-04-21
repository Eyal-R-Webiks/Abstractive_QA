import json
from collections import defaultdict

# ─── PARAMS ────────────────────────────────────────────────────────────────────
# Run download_vaadot.py first to produce SENTENCES_FILE.

SENTENCES_FILE  = "sentences_raw.jsonl"
PROTOCOLS_FILE  = "committee_protocols_local.jsonl"

# ─── FUNCTIONS ─────────────────────────────────────────────────────────────────

def build_protocols_from_sentences():
    print(f"Reading sentences from {SENTENCES_FILE} ...")

    # Group sentences by protocol_name.
    # For each protocol we keep the metadata (same for all sentences in a protocol)
    # and accumulate sentences in order.
    protocols = defaultdict(lambda: {"meta": {}, "sentences": []})

    loaded = 0
    with open(SENTENCES_FILE, encoding="utf-8") as f:
        for line in f:
            sentence = json.loads(line)
            name = sentence["protocol_name"]

            if not protocols[name]["meta"]:
                protocols[name]["meta"] = {
                    "protocol_name":  sentence["protocol_name"],
                    "session_name":   sentence["session_name"],
                    "protocol_date":  sentence["protocol_date"],
                    "knesset_number": sentence["knesset_number"],
                }

            protocols[name]["sentences"].append({
                "turn":          sentence.get("turn_num_in_protocol", 0),
                "sent_in_turn":  sentence.get("sent_num_in_turn", 0),
                "speaker_name":  sentence.get("speaker_name", ""),
                "sentence_text": sentence.get("sentence_text", ""),
            })

            loaded += 1
            if loaded % 100_000 == 0:
                print(f"  {loaded:,} sentences loaded, {len(protocols):,} protocols so far...")

    print(f"\nLoaded {loaded:,} sentences across {len(protocols):,} protocols.")
    print(f"Writing protocols to {PROTOCOLS_FILE} ...")

    written = 0
    with open(PROTOCOLS_FILE, "w", encoding="utf-8") as out:
        for protocol_data in protocols.values():
            # Sort sentences by their position in the protocol
            sorted_sentences = sorted(
                protocol_data["sentences"],
                key=lambda s: (s["turn"], s["sent_in_turn"])
            )
            text = " ".join(s["sentence_text"] for s in sorted_sentences if s["sentence_text"])

            protocol = {**protocol_data["meta"], "text": text, "char_count": len(text)}
            out.write(json.dumps(protocol, ensure_ascii=False) + "\n")
            written += 1

    print(f"Done. {written:,} protocols written to {PROTOCOLS_FILE}")
    print("Next step: run collect_vaadot.py")


if __name__ == "__main__":
    build_protocols_from_sentences()
