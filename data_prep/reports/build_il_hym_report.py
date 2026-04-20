from pathlib import Path
import json
import html

base = Path('.')
json_path = base / 'downloaded' / 'il-hym_survey.json'
out_path = base / 'downloaded' / 'il-hym_survey_report.html'

data = json.loads(json_path.read_text(encoding='utf-8'))

files_total = data['files_total']
length_stats = data['length_stats']
genre_distribution = data['genre_distribution']
genre_stats = data['genre_stats']
length_bins = data['length_bins']
long_files = data['files_gt_60000']
short_files = data['files_lt_200']
eta2 = data['eta_squared_genre_length']
lt_2000_rows = data['files_lt_2000']
count_lt_2000 = data['count_lt_2000']
count_2000_to_60000 = data['count_2000_to_60000']
genre_counts_2000_to_60000 = data['genre_counts_2000_to_60000']

max_genre = max(c for _, c in genre_distribution) if genre_distribution else 1
max_bin = max(c for _, c in length_bins) if length_bins else 1


def pct(n):
    return f"{(100.0 * n / files_total):.2f}%"


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

hist_bars = []
for b, c in length_bins:
    h = max(6.0, 220.0 * c / max_bin)
    hist_bars.append(
        f'''
        <div class="hist-item">
          <div class="hist-col-wrap">
            <div class="hist-col" style="height:{h:.2f}px"></div>
          </div>
          <div class="hist-count">{c:,}</div>
          <div class="hist-label">{html.escape(str(b))}</div>
        </div>
        '''
    )

from collections import defaultdict

long_rows = []
for row in long_files[:30]:
    long_rows.append(
        f"<tr><td>{html.escape(row['file'])}</td><td>{html.escape(row['genre'])}</td><td>{row['length']:,}</td></tr>"
    )

short_rows = []
for row in short_files[:30]:
    short_rows.append(
        f"<tr><td>{html.escape(row['file'])}</td><td>{html.escape(row['genre'])}</td><td>{row['length']:,}</td></tr>"
    )

# Sample files <2000 by genre (3 per genre)
lt_2000_by_genre = defaultdict(list)
for row in lt_2000_rows:
    lt_2000_by_genre[row['genre']].append(row)

lt_2000_samples = []
for genre in sorted(lt_2000_by_genre.keys()):
    lt_2000_samples.extend(lt_2000_by_genre[genre][:3])

len_lt_2000_items = ''.join(
  f'<li><span class="mono">{html.escape(row["file"])} ({html.escape(row["genre"])}) — {row["length"]}</span></li>' for row in sorted(lt_2000_samples, key=lambda r: (r['genre'], r['length']))
)

max_2000_60000_genre = max((c for _, c in genre_counts_2000_to_60000), default=1)
genre_2000_60000_rows = ''.join(
  f'''<tr>
    <td class="genre">{html.escape(g)}</td>
    <td>{c:,}</td>
    <td>{(100.0 * c / count_2000_to_60000):.1f}%</td>
    <td><div class="bar-wrap"><div class="bar alt" style="width:{max(1.0, 100.0*c/max_2000_60000_genre):.2f}%"></div></div></td>
  </tr>'''
  for g, c in genre_counts_2000_to_60000
)

html_text = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>סקר מאגר ישראל היום</title>
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

    .split {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }}

    .hist-wrap {{
      margin-top: 8px;
      padding: 10px 10px 4px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.75);
    }}

    .hist-grid {{
      min-height: 300px;
      display: grid;
      grid-template-columns: repeat(9, minmax(0, 1fr));
      gap: 8px;
      align-items: end;
    }}

    .hist-item {{
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: end;
      gap: 4px;
    }}

    .hist-col-wrap {{
      height: 220px;
      width: 100%;
      display: flex;
      align-items: end;
      justify-content: center;
    }}

    .hist-col {{
      width: 80%;
      min-width: 18px;
      background: linear-gradient(180deg, #4ec9b0, #1f8a70);
      border-radius: 8px 8px 4px 4px;
      box-shadow: 0 8px 16px rgba(31, 138, 112, 0.25);
      transition: transform .2s ease;
    }}

    .hist-col:hover {{
      transform: translateY(-2px);
    }}

    .hist-count {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.75rem;
      color: #334;
    }}

    .hist-label {{
      text-align: center;
      font-size: 0.72rem;
      color: #46535d;
      word-break: break-word;
      line-height: 1.15;
    }}

    .file-lists {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-top: 10px;
    }}

    .list-box {{
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(255,255,255,0.76);
      padding: 10px;
    }}

    .list-title {{
      font-weight: 700;
      margin-bottom: 6px;
      font-size: 0.95rem;
    }}

    .list-scroll {{
      max-height: 260px;
      overflow: auto;
      margin: 0;
      padding: 0 18px 0 0;
    }}

    .list-scroll li {{
      margin-bottom: 4px;
      line-height: 1.35;
    }}

    .recommendation-box {{
      margin-top: 12px;
      border: 1px solid rgba(219, 75, 63, 0.35);
      background: linear-gradient(180deg, rgba(255, 245, 235, 0.95), rgba(255, 239, 222, 0.95));
      border-radius: 12px;
      padding: 12px 14px;
      color: #582f27;
      font-weight: 600;
      box-shadow: 0 8px 20px rgba(219, 75, 63, 0.12);
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
      .split {{ grid-template-columns: 1fr; }}
      .hist-grid {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      .file-lists {{ grid-template-columns: 1fr; }}
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
      <h1>סקר מאגר ישראל היום</h1>
      <div class="subtitle">התפלגות נושאים ואורכי הטקסט החופשי</div>
      <div class="chips">
        <span class="chip">מספר קבצים: {files_total:,}</span>
        <span class="chip">תאריך: 2026-04-19</span>
        <span class="chip">מדד: מספר תווים בטקסט ללא שורות תגיות</span>
        <span class="chip">השפעת הנושא על האורך (בקירוב): {eta2}</span>
      </div>
      <div class="cards">
        {card('מינימום', f"{length_stats['min']:,}", 'תווים')}
        {card('חציון', f"{int(length_stats['median']):,}", 'תווים')}
        {card('ממוצע', f"{length_stats['mean']:,}", 'תווים')}
        {card('מקסימום', f"{length_stats['max']:,}", 'תווים')}
        {card('< 2,000', f"{count_lt_2000:,}", pct(count_lt_2000))}
        {card('2,000–60,000', f"{count_2000_to_60000:,}", pct(count_2000_to_60000))}
        {card('> 60,000', f"{data['count_gt_60000']:,}", pct(data['count_gt_60000']))}
      </div>
    </section>

    <section class="grid">
      <article class="panel">
        <h2>התפלגות לפי נושא</h2>
        <table>
          <thead>
            <tr><th>נושא</th><th>קבצים</th><th>חלק יחסי</th><th>עמודה חזותית</th></tr>
          </thead>
          <tbody>
            {''.join(genre_rows)}
          </tbody>
        </table>
      </article>

      <article class="panel">
        <h2>היסטוגרמה: התפלגות אורכים</h2>
        <div class="mono" style="margin-bottom:8px;">כל עמודה מייצגת טווח אורכים, והגובה מראה כמה קבצים יש בטווח הזה</div>
        <div class="hist-wrap">
          <div class="hist-grid">
            {''.join(hist_bars)}
          </div>
        </div>
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
      <h2>אורכים לפי נושא</h2>
      <table>
        <thead>
          <tr>
            <th>נושא</th><th>כמות</th><th>ממוצע</th><th>אמצעי</th><th>פיזור</th><th>מינימום</th><th>מקסימום</th>
          </tr>
        </thead>
        <tbody>
          {''.join(genre_stats_rows)}
        </tbody>
      </table>
    </section>

    <section class="panel" style="margin-top:14px;">
      <h2>מה זה eta² ואיך מפרשים את זה?</h2>
      <p style="margin:0 0 10px; color:#334; line-height:1.55;">
        eta² (נקרא "אטה בריבוע") הוא מספר בין 0 ל-1 שמראה כמה מהשונות באורכי הטקסט
        מוסברת על ידי חלוקה לנושאים. למשל, ערך גבוה אומר שלנושא יש קשר חזק יותר לאורך הטקסט.
      </p>
      <p style="margin:0 0 10px; color:#334; line-height:1.55;">
        בדוח הזה הערך הוא <span class="mono">{eta2}</span>, כלומר בערך
        <span class="mono">{eta2 * 100:.1f}%</span> מהשונות באורך קשורה לנושא.
        זה מצביע על קשר מורגש, אבל לא קשר מלא.
      </p>
      <p style="margin:0; color:#44515b; line-height:1.55;">
        בצורה פשוטה: מחשבים את הפער בין ממוצע האורך בכל נושא לממוצע הכללי,
        ומשווים את ההשפעה הזאת לשונות הכוללת בכלל הנתונים.
      </p>
    </section>

    <section class="panel" style="margin-top:14px;">
      <h2>דוגמאות קבצים</h2>
      <div class="split">
        <div>
          <div class="mono" style="margin-bottom:8px;">דוגמאות: קבצים עם אורך &lt; 2,000 תווים (סה"כ {count_lt_2000:,})</div>
          <ul class="list-scroll">
            {len_lt_2000_items}
          </ul>
        </div>
        <div>
          <div class="mono" style="margin-bottom:8px;">דוגמאות: קבצים ארוכים מ-60,000 תווים (סה"כ {data['count_gt_60000']:,})</div>
          <ul class="list-scroll">
            {''.join(f'<li><span class="mono">{html.escape(row["file"])} ({html.escape(row["genre"])}) — {row["length"]:,}</span></li>' for row in data['files_gt_60000'][:50])}
          </ul>
        </div>
      </div>
    </section>
        </div>
      </div>
    </section>

    <div class="foot">
      הדוח סטטי ומבוסס על קובץ הנתונים downloaded/il-hym_survey.json
    </div>
  </div>
</body>
</html>
'''

out_path.write_text(html_text, encoding='utf-8')
print(f'WROTE {out_path}')
