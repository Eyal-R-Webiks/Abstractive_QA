from pathlib import Path
import csv
import html
import statistics
from collections import defaultdict
from datetime import date


base = Path(__file__).resolve().parent.parent
csv_path = base / "il-hym" / "index.csv"
out_path = base / "reports" / "il_hym_index_report.html"


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


with csv_path.open("r", encoding="utf-8", newline="") as handle:
    rows = [row for row in csv.DictReader(handle)]

files_total = len(rows)
lengths = [to_int(row.get("len")) for row in rows]

genre_subgenre_lengths = defaultdict(lambda: defaultdict(list))
genre_lengths = defaultdict(list)
for row in rows:
    genre = str(row.get("genre", "unknown") or "unknown")
    subgenre = str(row.get("subgenre", "unknown") or "unknown")
    length = to_int(row.get("len"))
    genre_subgenre_lengths[genre][subgenre].append(length)
    genre_lengths[genre].append(length)

length_stats = {
    "min": min(lengths) if lengths else 0,
    "max": max(lengths) if lengths else 0,
    "mean": round(statistics.mean(lengths), 2) if lengths else 0,
    "median": round(statistics.median(lengths), 2) if lengths else 0,
    "p10": round(statistics.quantiles(lengths, n=10, method="inclusive")[0], 2) if len(lengths) > 1 else 0,
    "p90": round(statistics.quantiles(lengths, n=10, method="inclusive")[8], 2) if len(lengths) > 1 else 0,
}

bins = [
    (0, 999),
    (1000, 1999),
    (2000, 4999),
    (5000, 9999),
    (10000, 19999),
    (20000, 59999),
    (60000, 99999),
    (100000, 199999),
    (200000, 10**12),
]

length_bins = []
for low, high in bins:
    label = f"{low:,}-{high:,}" if high < 10**12 else f"{low:,}+"
    count = sum(1 for length in lengths if low <= length <= high)
    length_bins.append((label, count))

if lengths:
    grand_mean = statistics.mean(lengths)
    ss_total = sum((length - grand_mean) ** 2 for length in lengths)
    ss_between = sum(
        len(values) * (statistics.mean(values) - grand_mean) ** 2
        for values in genre_lengths.values()
    )
    eta2 = round((ss_between / ss_total), 4) if ss_total else 0
else:
    eta2 = 0

long_rows = sorted(rows, key=lambda row: to_int(row.get("len")), reverse=True)[:50]
short_rows = sorted(rows, key=lambda row: to_int(row.get("len")))[:50]
max_bin = max((count for _, count in length_bins), default=1)


def pct(count):
    return f"{(100.0 * count / files_total):.2f}%" if files_total else "0.00%"


def card(title, value, subtitle):
    return f"""
    <div class=\"card\">
      <div class=\"card-title\">{html.escape(title)}</div>
      <div class=\"card-value\">{html.escape(value)}</div>
      <div class=\"card-sub\">{html.escape(subtitle)}</div>
    </div>
    """


def dist_rows(items, max_value, alt=False):
    bar_class = "bar alt" if alt else "bar"
    output = []
    for name, count in items:
        width = max(1.0, 100.0 * count / max_value) if max_value else 1.0
        output.append(
            f"""<tr>
              <td class=\"genre\">{html.escape(str(name))}</td>
              <td>{count:,}</td>
              <td>{pct(count)}</td>
              <td><div class=\"bar-wrap\"><div class=\"{bar_class}\" style=\"width:{width:.2f}%\"></div></div></td>
            </tr>"""
        )
    return "".join(output)


def build_genre_subgenre_rows():
  groups = []
  for genre in sorted(genre_subgenre_lengths.keys()):
    genre_values = genre_lengths[genre]
    subgenre_names = sorted(
      genre_subgenre_lengths[genre].keys(),
      key=lambda subgenre: (0 if subgenre == genre else 1, subgenre),
    )
    group_rows = [
      f"""<tr class=\"genre-start\">
          <td class=\"genre-cell\"><strong>{html.escape(genre)}</strong></td>
          <td></td>
          <td>{len(genre_values):,}</td>
          <td>{min(genre_values):,}</td>
          <td>{max(genre_values):,}</td>
        </tr>"""
    ]
    for subgenre in subgenre_names:
      values = genre_subgenre_lengths[genre][subgenre]
      if subgenre == genre:
        subgenre_label = "<em>&lt;no subgenre&gt;</em>"
      else:
        subgenre_label = f"<span class=\"mono\">{html.escape(subgenre)}</span>"
      group_rows.append(
        f"""<tr>
          <td class=\"genre-cell\"></td>
                  <td>{subgenre_label}</td>
                  <td>{len(values):,}</td>
                  <td>{min(values):,}</td>
                  <td>{max(values):,}</td>
                </tr>"""
            )
    groups.append(f"<tbody class=\"genre-group\">{''.join(group_rows)}</tbody>")
  return "".join(groups)


bin_rows_html = dist_rows(length_bins, max_bin, alt=True)
genre_subgenre_rows_html = build_genre_subgenre_rows()

long_items = "".join(
    f"<li><span class=\"mono\">{html.escape(row.get('filename', ''))} ({html.escape(row.get('genre', 'unknown'))}) - {to_int(row.get('len')):,}</span></li>"
    for row in long_rows
)
short_items = "".join(
    f"<li><span class=\"mono\">{html.escape(row.get('filename', ''))} ({html.escape(row.get('genre', 'unknown'))}) - {to_int(row.get('len')):,}</span></li>"
    for row in short_rows
)

html_text = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>סקר il-hym index</title>
  <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">
  <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>
  <link href=\"https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap\" rel=\"stylesheet\">
  <style>
    :root {{
      --bg0: #fff8ef;
      --bg1: #ffe3bf;
      --ink: #172026;
      --muted: #5b6670;
      --card: rgba(255,255,255,0.84);
      --line: rgba(23,32,38,0.12);
      --accent: #db4b3f;
      --accent2: #1f8a70;
      --shadow: 0 16px 45px rgba(23,32,38,0.13);
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      font-family: 'Space Grotesk', sans-serif;
      color: var(--ink);
      background:
        radial-gradient(1200px 700px at 8% 8%, #ffd097 0%, transparent 65%),
        radial-gradient(850px 550px at 95% 10%, #ffc7a8 0%, transparent 70%),
        linear-gradient(160deg, var(--bg0), var(--bg1));
      min-height: 100vh;
      direction: rtl;
    }}

    .container {{
      width: min(1200px, 94vw);
      margin: 28px auto 40px;
    }}

    .hero {{
      padding: 26px;
      border-radius: 20px;
      background: var(--card);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      backdrop-filter: blur(4px);
      animation: rise .6s ease;
    }}

    h1 {{
      margin: 0 0 8px;
      font-size: clamp(1.6rem, 4vw, 2.5rem);
      letter-spacing: -0.02em;
    }}

    .subtitle {{
      color: var(--muted);
      font-size: 1rem;
      margin-bottom: 10px;
    }}

    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }}

    .chip {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.82rem;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 5px 10px;
      color: #334;
    }}

    .cards {{
      margin-top: 14px;
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }}

    .card {{
      padding: 14px;
      border-radius: 14px;
      background: #fff;
      border: 1px solid var(--line);
    }}

    .card-title {{
      font-size: 0.85rem;
      color: var(--muted);
      margin-bottom: 6px;
    }}

    .card-value {{
      font-size: clamp(1rem, 2.6vw, 1.7rem);
      font-weight: 700;
      line-height: 1.1;
    }}

    .card-sub {{
      margin-top: 4px;
      color: #49545d;
      font-size: 0.83rem;
    }}

    .panel {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 16px;
      box-shadow: var(--shadow);
      padding: 16px;
      animation: rise .75s ease;
    }}

    h2 {{
      margin: 0 0 10px;
      font-size: 1.16rem;
      letter-spacing: -0.01em;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.92rem;
    }}

    th, td {{
      text-align: right;
      padding: 8px 6px;
      border-bottom: 1px solid var(--line);
      vertical-align: middle;
    }}

    th {{
      color: #2f3a44;
      font-size: 0.82rem;
      letter-spacing: 0.02em;
      text-transform: uppercase;
    }}

    .genre {{
      font-weight: 600;
    }}

    .bar-wrap {{
      width: 100%;
      height: 9px;
      background: #f0e8df;
      border-radius: 999px;
      overflow: hidden;
    }}

    .bar {{
      height: 100%;
      background: linear-gradient(90deg, #ef6a58, #db4b3f);
      border-radius: 999px;
    }}

    .bar.alt {{
      background: linear-gradient(90deg, #34a78c, #1f8a70);
    }}

    .split {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }}

    .list-scroll {{
      max-height: 300px;
      overflow: auto;
      margin: 0;
      padding: 0 18px 0 0;
    }}

    .list-scroll li {{
      margin-bottom: 4px;
      line-height: 1.35;
    }}

    .mono {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.86rem;
    }}

    .ltr-panel {{
      direction: ltr;
      text-align: left;
    }}

    .ltr-panel h2,
    .ltr-panel th,
    .ltr-panel td {{
      text-align: left;
    }}

    .genre-table {{
      border-collapse: separate;
      border-spacing: 0;
    }}

    .genre-table thead th {{
      background: rgba(255,255,255,0.96);
    }}

    .genre-group .genre-start td {{
      border-top: 14px solid transparent;
      background: rgba(219,75,63,0.08);
    }}

    .genre-group:first-of-type .genre-start td {{
      border-top-width: 0;
    }}

    .genre-cell {{
      min-width: 150px;
    }}

    .foot {{
      margin-top: 14px;
      color: #4f5b66;
      font-size: 0.88rem;
      padding: 0 4px;
    }}

    @keyframes rise {{
      from {{ opacity: 0; transform: translateY(10px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}

    @media (max-width: 980px) {{
      .cards {{ grid-template-columns: repeat(2, minmax(0,1fr)); }}
      .split {{ grid-template-columns: 1fr; }}
    }}

    @media (max-width: 560px) {{
      .cards {{ grid-template-columns: 1fr; }}
      th:nth-child(4), td:nth-child(4) {{ display: none; }}
    }}
  </style>
</head>
<body>
  <div class=\"container\">
    <section class=\"hero\">
      <h1>סקר il-hym לפי index.csv</h1>
      <div class=\"subtitle\">התפלגות ז'אנרים ותתי-ז'אנרים ואורכי טקסט</div>
      <div class=\"chips\">
        <span class=\"chip\">מספר קבצים: {files_total:,}</span>
        <span class=\"chip\">תאריך: {date.today().isoformat()}</span>
        <span class=\"chip\">מקור: il-hym/index.csv</span>
        <span class=\"chip\">השפעת genre על אורך (eta2): {eta2}</span>
      </div>
      <div class=\"cards\">
        {card('מינימום', f"{length_stats['min']:,}", 'תווים')}
        {card('חציון', f"{int(length_stats['median']):,}", 'תווים')}
        {card('ממוצע', f"{length_stats['mean']:,}", 'תווים')}
        {card('מקסימום', f"{length_stats['max']:,}", 'תווים')}
        {card('P10', f"{int(length_stats['p10']):,}", 'תווים')}
        {card('P90', f"{int(length_stats['p90']):,}", 'תווים')}
      </div>
    </section>

    <section class=\"panel ltr-panel\" style=\"margin-top:14px;\">
      <h2>Genre/Subgenre Table</h2>
      <table class=\"genre-table\">
        <thead>
          <tr>
            <th>Genre</th>
            <th>Subgenre</th>
            <th>docs_amount</th>
            <th>Min_len</th>
            <th>max_len</th>
          </tr>
        </thead>
        {genre_subgenre_rows_html}
      </table>
    </section>

    <section class=\"panel\" style=\"margin-top:14px;\">
      <h2>טווחי אורך</h2>
      <table>
        <thead>
          <tr><th>טווח</th><th>קבצים</th><th>חלק יחסי</th><th>עמודה חזותית</th></tr>
        </thead>
        <tbody>
          {bin_rows_html}
        </tbody>
      </table>
    </section>

    <section class=\"panel\" style=\"margin-top:14px;\">
      <h2>דוגמאות קבצים</h2>
      <div class=\"split\">
        <div>
          <div class=\"mono\" style=\"margin-bottom:8px;\">50 הקבצים הקצרים ביותר</div>
          <ul class=\"list-scroll\">{short_items}</ul>
        </div>
        <div>
          <div class=\"mono\" style=\"margin-bottom:8px;\">50 הקבצים הארוכים ביותר</div>
          <ul class=\"list-scroll\">{long_items}</ul>
        </div>
      </div>
    </section>

    <div class=\"foot\">
      דוח סטטי שנבנה מתוך il-hym/index.csv
    </div>
  </div>
</body>
</html>
"""

out_path.write_text(html_text, encoding="utf-8")
print(f"WROTE {out_path}")
