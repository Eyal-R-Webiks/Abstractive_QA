from pathlib import Path
import json
import html
import statistics
from collections import Counter, defaultdict

base = Path('.')
jsonl_path = base / 'downloaded' / 'wiki-extract' / 'hewiki_random_310.jsonl'
out_path = base / 'downloaded' / 'wiki-extract' / 'wiki_extract_survey_report.html'

lines = jsonl_path.read_text(encoding='utf-8').splitlines()
rows = [json.loads(line) for line in lines if line.strip()]

files_total = len(rows)
lengths = [int(r.get('length_chars', 0)) for r in rows]
categories = [str(r.get('category', 'לא ידוע')) for r in rows]

length_stats = {
    'min': min(lengths) if lengths else 0,
    'max': max(lengths) if lengths else 0,
    'mean': round(statistics.mean(lengths), 2) if lengths else 0,
    'median': round(statistics.median(lengths), 2) if lengths else 0,
    'std': round(statistics.pstdev(lengths), 2) if len(lengths) > 1 else 0,
    'p10': round(statistics.quantiles(lengths, n=10, method='inclusive')[0], 2) if len(lengths) > 1 else 0,
    'p90': round(statistics.quantiles(lengths, n=10, method='inclusive')[8], 2) if len(lengths) > 1 else 0,
}

# In-range bins only (as requested, no under-2000 / over-60000 sections)
bins = [
    (2000, 4999),
    (5000, 9999),
    (10000, 19999),
    (20000, 39999),
    (40000, 60000),
]
length_bins = [
    (f'{a}-{b}', sum(1 for L in lengths if a <= L <= b))
    for a, b in bins
]

cat_counter = Counter(categories)
genre_distribution = sorted(cat_counter.items(), key=lambda kv: (-kv[1], kv[0]))

cat_lengths = defaultdict(list)
for r in rows:
    cat_lengths[str(r.get('category', 'לא ידוע'))].append(int(r.get('length_chars', 0)))

genre_stats = []
for g, vals in sorted(cat_lengths.items(), key=lambda kv: (-len(kv[1]), kv[0])):
    genre_stats.append({
        'genre': g,
        'count': len(vals),
        'mean': round(statistics.mean(vals), 2),
        'median': round(statistics.median(vals), 2),
        'std': round(statistics.pstdev(vals), 2) if len(vals) > 1 else 0.0,
        'min': min(vals),
        'max': max(vals),
    })

# eta^2 between category and length
if lengths:
    grand_mean = statistics.mean(lengths)
    ss_total = sum((x - grand_mean) ** 2 for x in lengths)
    ss_between = sum(len(v) * (statistics.mean(v) - grand_mean) ** 2 for v in cat_lengths.values())
    eta2 = round((ss_between / ss_total), 4) if ss_total else 0
else:
    eta2 = 0

max_genre = max((c for _, c in genre_distribution), default=1)
max_bin = max((c for _, c in length_bins), default=1)


def pct(n):
    return f"{(100.0 * n / files_total):.2f}%" if files_total else '0.00%'


def card(title, value, subtitle):
    return f'''
    <div class="card">
      <div class="card-title">{html.escape(title)}</div>
      <div class="card-value">{html.escape(value)}</div>
      <div class="card-sub">{html.escape(subtitle)}</div>
    </div>
    '''


genre_rows = []
for g, c in genre_distribution:
    w = max(1.0, 100.0 * c / max_genre)
    genre_rows.append(
        f'''<tr>
          <td class="genre">{html.escape(g)}</td>
          <td>{c:,}</td>
          <td>{pct(c)}</td>
          <td>
            <div class="bar-wrap"><div class="bar" style="width:{w:.2f}%"></div></div>
          </td>
        </tr>'''
    )

genre_stats_rows = []
for row in genre_stats:
    genre_stats_rows.append(
        f'''<tr>
          <td class="genre">{html.escape(row['genre'])}</td>
          <td>{row['count']:,}</td>
          <td>{row['mean']:,}</td>
          <td>{row['median']:,}</td>
          <td>{row['std']:,}</td>
          <td>{row['min']:,}</td>
          <td>{row['max']:,}</td>
        </tr>'''
    )

bin_rows = []
for b, c in length_bins:
    w = max(1.0, 100.0 * c / max_bin)
    bin_rows.append(
        f'''<tr>
          <td>{html.escape(str(b))}</td>
          <td>{c:,}</td>
          <td>{pct(c)}</td>
          <td>
            <div class="bar-wrap"><div class="bar alt" style="width:{w:.2f}%"></div></div>
          </td>
        </tr>'''
    )

html_text = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>סקר ויקיפדיה בעברית</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
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

    .grid {{
      margin-top: 14px;
      display: grid;
      grid-template-columns: 1.15fr 1fr;
      gap: 14px;
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

    .genre {{ font-weight: 600; }}

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

    .mono {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.86rem;
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
      .grid {{ grid-template-columns: 1fr; }}
    }}

    @media (max-width: 560px) {{
      .cards {{ grid-template-columns: 1fr; }}
      th:nth-child(4), td:nth-child(4) {{ display: none; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <section class="hero">
      <h1>סקר ויקיפדיה בעברית</h1>
      <div class="subtitle">התפלגות קטגוריות ואורכי טקסט במאגר הדגימה</div>
      <div class="chips">
        <span class="chip">מספר קבצים: {files_total:,}</span>
        <span class="chip">תאריך: 2026-04-20</span>
        <span class="chip">מדד: מספר תווים בטקסט ב־plain text</span>
        <span class="chip">השפעת הקטגוריה על האורך (בקירוב): {eta2}</span>
      </div>
      <div class="cards">
        {card('מינימום', f"{length_stats['min']:,}", 'תווים')}
        {card('חציון', f"{int(length_stats['median']):,}", 'תווים')}
        {card('ממוצע', f"{length_stats['mean']:,}", 'תווים')}
        {card('מקסימום', f"{length_stats['max']:,}", 'תווים')}
        {card('עשירון תחתון (10%)', f"{int(length_stats['p10']):,}", 'תווים')}
        {card('עשירון עליון (90%)', f"{int(length_stats['p90']):,}", 'תווים')}
      </div>
    </section>

    <section class="grid">
      <article class="panel">
        <h2>התפלגות לפי קטגוריה</h2>
        <table>
          <thead>
            <tr><th>קטגוריה</th><th>קבצים</th><th>חלק יחסי</th><th>עמודה חזותית</th></tr>
          </thead>
          <tbody>
            {''.join(genre_rows)}
          </tbody>
        </table>
      </article>

      <article class="panel">
        <h2>טווחי אורך</h2>
        <table>
          <thead>
            <tr><th>טווח</th><th>קבצים</th><th>חלק יחסי</th><th>עמודה חזותית</th></tr>
          </thead>
          <tbody>
            {''.join(bin_rows)}
          </tbody>
        </table>
      </article>
    </section>

    <section class="panel" style="margin-top:14px;">
      <h2>אורכים לפי קטגוריה</h2>
      <table>
        <thead>
          <tr>
            <th>קטגוריה</th><th>כמות</th><th>ממוצע</th><th>חציון</th><th>פיזור</th><th>מינימום</th><th>מקסימום</th>
          </tr>
        </thead>
        <tbody>
          {''.join(genre_stats_rows)}
        </tbody>
      </table>
    </section>

    <section class="panel" style="margin-top:14px;">
      <h2>eta²</h2>
      <p style="margin:0; color:#334; line-height:1.55;">
        הערך <span class="mono">{eta2}</span> מציין בקירוב איזה חלק מהשונות באורך הטקסט מוסבר על ידי הקטגוריה.
      </p>
    </section>

    <div class="foot">
      הדוח סטטי ומבוסס על הקובץ downloaded/wiki-extract/hewiki_random_310.jsonl
    </div>
  </div>
</body>
</html>
'''

out_path.write_text(html_text, encoding='utf-8')
print(f'WROTE {out_path}')
