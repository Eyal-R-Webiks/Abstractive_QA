import json

# ─── PARAMS ────────────────────────────────────────────────────────────────────
# Run download_vaadot.py first to produce the local file below.

LOCAL_INPUT_FILE = "committee_protocols_local.jsonl"

# Leave TARGET_VAADOT empty [] to sample from all committees.
# Open all_vaadot_names.json (produced by discover_vaadot below) to pick names.
TARGET_VAADOT = [
    "ועדת הכספים",
    "ועדת הכלכלה",
    "ועדת החוקה, חוק ומשפט",
    "ועדת העבודה, הרווחה והבריאות",
    "ועדת החינוך, התרבות והספורט",
    "ועדת הפנים ואיכות הסביבה",
    "ועדת הכנסת",
    "הוועדה לענייני ביקורת המדינה",
    "ועדת העלייה, הקליטה והתפוצות",
    "ועדת הפנים והגנת הסביבה",
    "ועדת החינוך והתרבות",
    "ועדת העבודה והרווחה",
    "הוועדה לקידום מעמד האישה",
    "הוועדה המיוחדת לפניות הציבור",
    "הוועדה המיוחדת לזכויות הילד",
    "ועדת המדע והטכנולוגיה",
    "הוועדה לקידום מעמד האישה ולשוויון מגדרי",
    "ועדת העלייה והקליטה",
    "הוועדה המיוחדת לבחינת בעיית העובדים הזרים",
    "ועדת החוץ והביטחון"
]

YEAR_FILTER      = None   # e.g. 2015, or None to skip
KNESSET_RANGE    = (17, 24)  # e.g. (13, 24), or None to skip
MIN_CHARS        = 2000
MAX_CHARS        = 60000
OUTPUT_FILE      = "vaadot_sample_mod.jsonl"
VAADOT_LIST_FILE = "all_vaadot_names.json"

# ─── FUNCTIONS ─────────────────────────────────────────────────────────────────

def get_protocol_text(protocol):
    # text is already built by build_protocols.py
    return protocol.get("text", "")


def matches_filters(protocol, text):
    if not (MIN_CHARS <= len(text) <= MAX_CHARS):
        return False

    if TARGET_VAADOT and protocol.get("session_name", "") not in TARGET_VAADOT:
        return False

    if YEAR_FILTER is not None:
        date_str = protocol.get("protocol_date", "") or ""
        if not date_str or int(date_str[:4]) != YEAR_FILTER:
            return False

    if KNESSET_RANGE is not None:
        try:
            knesset_number = int(protocol.get("knesset_number"))
        except (TypeError, ValueError):
            return False
        start, end = KNESSET_RANGE
        if not (start <= knesset_number <= end):
            return False

    return True


def discover_vaadot():
    """
    Read the local file and collect every unique committee name.
    Saves to VAADOT_LIST_FILE. Run this once to know what names exist,
    then paste the ones you want into TARGET_VAADOT above.
    """
    print("Scanning local file for committee names...")
    names = set()
    with open(LOCAL_INPUT_FILE, encoding="utf-8") as f:
        for line in f:
            protocol = json.loads(line)
            name = (protocol.get("session_name") or "").strip()
            if name:
                names.add(name)

    sorted_names = sorted(names)
    with open(VAADOT_LIST_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted_names, f, ensure_ascii=False, indent=2)

    print(f"Found {len(sorted_names)} unique committees. Saved to {VAADOT_LIST_FILE}")
    return sorted_names


def collect_docs():
    print(f"Reading from {LOCAL_INPUT_FILE}")
    print(f"Filters: min_chars={MIN_CHARS}, max_chars={MAX_CHARS}, year={YEAR_FILTER}")
    print(f"Knesset range: {KNESSET_RANGE if KNESSET_RANGE is not None else 'ALL'}")
    print(f"Committees: {TARGET_VAADOT if TARGET_VAADOT else 'ALL'}")

    collected = []
    scanned = 0

    with open(LOCAL_INPUT_FILE, encoding="utf-8") as f:
        for line in f:
            protocol = json.loads(line)
            scanned += 1
            text = get_protocol_text(protocol)

            if matches_filters(protocol, text):
                collected.append({
                    "session_name":   protocol.get("session_name"),
                    "protocol_name":  protocol.get("protocol_name"),
                    "protocol_date":  protocol.get("protocol_date"),
                    "knesset_number": protocol.get("knesset_number"),
                    "char_count":     len(text),
                    "text":           text,
                })

            if scanned % 5000 == 0:
                print(f"  scanned {scanned:,} | collected {len(collected):,}")

    print(f"\nDone. Scanned {scanned:,}, collected {len(collected)}.")
    return collected


def save_docs(docs):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    print(f"Saved {len(docs)} docs to {OUTPUT_FILE}")


# ─── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Step 1 (run once after downloading): find all committee names
    # discover_vaadot()

    # Step 2: collect your sample
    docs = collect_docs()
    save_docs(docs)
