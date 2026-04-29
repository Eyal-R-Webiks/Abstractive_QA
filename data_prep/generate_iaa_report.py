#!/usr/bin/env python3
"""Generate an inter-annotator agreement (IAA) HTML report for the 4 evaluator
models, based on the consolidated scored JSON.

Computes:
  - Per-model score distributions
  - Pairwise exact-agreement %, within-1 agreement %
  - Cohen's kappa (unweighted) and weighted kappa (linear + quadratic)
  - Fleiss' kappa across all 4 raters
  - Group-level raw agreement (% unanimous, % within ±1)
  - Per-model deviation from majority (outlier behaviour)
  - Sample disagreements

Output: data_prep/reports/iaa_report.html
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from html import escape
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Optional, Tuple

INPUT_JSON = Path("data_prep/questions/eval/all_questions_for_eval_scored.json")
OUTPUT_HTML = Path("data_prep/reports/iaa_report.html")

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_pivot() -> Tuple[Dict[str, Dict[str, Tuple[Optional[int], Optional[int]]]], List[str], List[Dict]]:
    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    pivot: Dict[str, Dict[str, Tuple[Optional[int], Optional[int]]]] = defaultdict(dict)
    for r in data:
        u = r["uuid"]
        m = r["evaluator_model_name"]
        pivot[u][m] = (r.get("complexity_score"), r.get("linguistic_score"))
    models = sorted({r["evaluator_model_name"] for r in data})
    return pivot, models, data


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def pairwise_agreement(scores_a: List[int], scores_b: List[int]) -> Tuple[float, float]:
    """Return (exact %, within-1 %)."""
    assert len(scores_a) == len(scores_b)
    n = len(scores_a)
    if n == 0:
        return 0.0, 0.0
    exact = sum(1 for a, b in zip(scores_a, scores_b) if a == b)
    near = sum(1 for a, b in zip(scores_a, scores_b) if abs(a - b) <= 1)
    return 100.0 * exact / n, 100.0 * near / n


def cohen_kappa(scores_a: List[int], scores_b: List[int], weights: str = "none") -> float:
    """Compute Cohen's kappa with optional linear/quadratic weights."""
    cats = sorted(set(scores_a) | set(scores_b))
    if not cats:
        return float("nan")
    idx = {c: i for i, c in enumerate(cats)}
    k = len(cats)
    n = len(scores_a)

    # Confusion matrix
    cm = [[0] * k for _ in range(k)]
    for a, b in zip(scores_a, scores_b):
        cm[idx[a]][idx[b]] += 1

    # Marginals
    row_marg = [sum(row) for row in cm]
    col_marg = [sum(cm[i][j] for i in range(k)) for j in range(k)]

    # Weight matrix
    if weights == "none":
        w = [[0.0 if i == j else 1.0 for j in range(k)] for i in range(k)]
    elif weights == "linear":
        max_d = max(1, k - 1)
        w = [[abs(i - j) / max_d for j in range(k)] for i in range(k)]
    elif weights == "quadratic":
        max_d = max(1, k - 1)
        w = [[((i - j) / max_d) ** 2 for j in range(k)] for i in range(k)]
    else:
        raise ValueError(f"unknown weights: {weights}")

    po = sum(w[i][j] * cm[i][j] for i in range(k) for j in range(k)) / n
    pe = sum(w[i][j] * row_marg[i] * col_marg[j] for i in range(k) for j in range(k)) / (n * n)
    if pe == 0:
        return float("nan")
    return 1.0 - po / pe


def fleiss_kappa(matrix: List[List[int]]) -> float:
    """Fleiss' kappa for N items × k categories matrix (counts per category)."""
    N = len(matrix)
    if N == 0:
        return float("nan")
    n_raters = sum(matrix[0])
    if n_raters <= 1:
        return float("nan")
    k = len(matrix[0])
    p_j = [sum(matrix[i][j] for i in range(N)) / (N * n_raters) for j in range(k)]
    P_i = []
    for row in matrix:
        s = sum(c * (c - 1) for c in row)
        P_i.append(s / (n_raters * (n_raters - 1)))
    P_bar = sum(P_i) / N
    P_e = sum(p * p for p in p_j)
    if P_e == 1:
        return float("nan")
    return (P_bar - P_e) / (1 - P_e)


def krippendorff_alpha_ordinal(per_unit: List[List[int]]) -> float:
    """Krippendorff's alpha with ordinal difference metric.

    per_unit: list of lists of ratings (each unit may have variable raters).
    """
    # Flatten to (unit_idx, rating) pairs
    pairs = []
    for i, ratings in enumerate(per_unit):
        for r in ratings:
            pairs.append((i, r))
    if not pairs:
        return float("nan")

    cats = sorted({r for _, r in pairs})
    if len(cats) < 2:
        return float("nan")
    cat_idx = {c: i for i, c in enumerate(cats)}

    # n_v = total occurrences of category v
    n_v = Counter(r for _, r in pairs)
    n_total = sum(n_v.values())

    # Ordinal distance between categories c and c'
    def delta_ord(c1: int, c2: int) -> float:
        if c1 == c2:
            return 0.0
        a, b = sorted([c1, c2])
        # sum of n_g for a <= g <= b minus half the endpoints
        s = sum(n_v.get(g, 0) for g in cats if a <= g <= b)
        s -= (n_v[a] + n_v[b]) / 2.0
        return s * s

    # Observed disagreement
    D_o_num = 0.0
    D_o_den = 0
    for ratings in per_unit:
        m = len(ratings)
        if m < 2:
            continue
        D_o_den += m - 1
        for i in range(m):
            for j in range(m):
                if i == j:
                    continue
                D_o_num += delta_ord(ratings[i], ratings[j])

    if D_o_den == 0:
        return float("nan")
    D_o = D_o_num / (2 * D_o_den)  # /2 because we counted both (i,j) and (j,i) — actually we did, fine

    # Expected disagreement
    D_e = 0.0
    norm = n_total * (n_total - 1)
    if norm == 0:
        return float("nan")
    for c1 in cats:
        for c2 in cats:
            if c1 == c2:
                continue
            D_e += n_v[c1] * n_v[c2] * delta_ord(c1, c2)
    D_e /= norm

    if D_e == 0:
        return float("nan")
    return 1.0 - D_o / D_e


# ---------------------------------------------------------------------------
# Outlier analysis
# ---------------------------------------------------------------------------

def majority_deviation_per_model(
    pivot: Dict[str, Dict[str, Tuple[Optional[int], Optional[int]]]],
    models: List[str],
    score_field_idx: int,
) -> Dict[str, Dict[str, float]]:
    """For each model, compute:
       - % rows where model deviates from the median of the other 3
       - mean abs distance from median of the other 3
    """
    out: Dict[str, Dict[str, float]] = {}
    for m in models:
        deviations: List[float] = []
        diffs_abs: List[float] = []
        for u, by_model in pivot.items():
            scores = {k: v[score_field_idx] for k, v in by_model.items() if v[score_field_idx] is not None}
            if m not in scores:
                continue
            others = [s for k, s in scores.items() if k != m]
            if len(others) < 2:
                continue
            median_others = statistics.median(others)
            mine = scores[m]
            deviations.append(1.0 if mine != median_others else 0.0)
            diffs_abs.append(abs(mine - median_others))
        out[m] = {
            "deviation_rate": 100.0 * sum(deviations) / len(deviations) if deviations else 0.0,
            "mean_abs_dev": sum(diffs_abs) / len(diffs_abs) if diffs_abs else 0.0,
            "n": len(deviations),
        }
    return out


def all_disagreement_examples(
    data: List[Dict],
    pivot: Dict[str, Dict[str, Tuple[Optional[int], Optional[int]]]],
    models: List[str],
    field_idx: int,
    field_name: str,
    max_examples: int = 3,
) -> List[Dict]:
    """Return rows where the spread of scores is widest (max - min)."""
    rows = []
    for u, by_model in pivot.items():
        scores = [(k, v[field_idx]) for k, v in by_model.items() if v[field_idx] is not None]
        if len(scores) < len(models):
            continue
        vals = [s for _, s in scores]
        spread = max(vals) - min(vals)
        rows.append((spread, u, dict(scores)))
    rows.sort(key=lambda x: -x[0])

    # Find original question text + reasoning per model
    by_uuid_model = defaultdict(dict)
    for r in data:
        by_uuid_model[r["uuid"]][r["evaluator_model_name"]] = r

    out = []
    for spread, u, scores in rows[:max_examples]:
        first = next(iter(by_uuid_model[u].values()))
        out.append({
            "uuid": u,
            "spread": spread,
            "question": first.get("question", "")[:300],
            "excerpt": first.get("excerpt", "")[:200],
            "scores": scores,
            "reasonings": {m: by_uuid_model[u].get(m, {}).get("reasoning", "") for m in models},
        })
    return out


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def kappa_band(k: float) -> str:
    if k != k:  # NaN
        return "n/a"
    if k < 0:
        return "worse than chance"
    if k < 0.20:
        return "slight"
    if k < 0.40:
        return "fair"
    if k < 0.60:
        return "moderate"
    if k < 0.80:
        return "substantial"
    if k < 1.00:
        return "almost perfect"
    return "perfect"


def pct(x: float) -> str:
    return f"{x:5.1f}%"


def kfmt(k: float) -> str:
    if k != k:
        return "n/a"
    return f"{k:+.3f}"


def model_short(name: str) -> str:
    return {
        "gemini_3_1_pro_eval": "Gemini-3.1-Pro",
        "gpt_5_4_mini_eval": "GPT-5.4-mini",
        "mistral_large_2407_eval": "Mistral-L-2407",
        "claude_3_7_sonnet_eval": "Claude-3.7-Sonnet",
    }.get(name, name)


def render_html(
    *,
    n_items: int,
    models: List[str],
    dist_complexity: Dict[str, Counter],
    dist_linguistic: Dict[str, Counter],
    pair_metrics_complexity: Dict[Tuple[str, str], Dict[str, float]],
    fleiss_complexity: float,
    group_unanimous_pct: float,
    group_within1_pct: float,
    deviation_complexity: Dict[str, Dict[str, float]],
    disagreement_examples_complexity: List[Dict],
) -> str:
    def dist_table(dist: Dict[str, Counter], cats: List[int]) -> str:
        rows = []
        for m in models:
            cells = []
            total = sum(dist[m].values())
            for c in cats:
                n = dist[m].get(c, 0)
                p = (100.0 * n / total) if total else 0.0
                cells.append(f"<td>{n} ({p:.1f}%)</td>")
            cells.append(f"<td>{total}</td>")
            rows.append(f"<tr><td>{model_short(m)}</td>{''.join(cells)}</tr>")
        head = "".join(f"<th>{c}</th>" for c in cats) + "<th>n</th>"
        return f"<table><thead><tr><th>Model</th>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"

    def pair_table(pm: Dict[Tuple[str, str], Dict[str, float]]) -> str:
        rows = []
        for (a, b), v in pm.items():
            rows.append(
                "<tr>"
                f"<td>{model_short(a)}</td>"
                f"<td>{model_short(b)}</td>"
                f"<td>{pct(v['exact'])}</td>"
                f"<td>{pct(v['within1'])}</td>"
                f"<td>{kfmt(v['kappa_unweighted'])} <span class='band'>({kappa_band(v['kappa_unweighted'])})</span></td>"
                f"<td>{kfmt(v['kappa_linear'])} <span class='band'>({kappa_band(v['kappa_linear'])})</span></td>"
                f"<td>{kfmt(v['kappa_quadratic'])} <span class='band'>({kappa_band(v['kappa_quadratic'])})</span></td>"
                "</tr>"
            )
        return (
            "<table><thead><tr>"
            "<th>Model A</th><th>Model B</th>"
            "<th>Exact</th><th>Within-1</th>"
            "<th>κ (unweighted)</th><th>κ (linear)</th><th>κ (quadratic)</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
        )

    def deviation_table(dev: Dict[str, Dict[str, float]]) -> str:
        rows = []
        for m, v in sorted(dev.items(), key=lambda kv: -kv[1]["deviation_rate"]):
            rows.append(
                f"<tr><td>{model_short(m)}</td>"
                f"<td>{pct(v['deviation_rate'])}</td>"
                f"<td>{v['mean_abs_dev']:.3f}</td>"
                f"<td>{v['n']}</td></tr>"
            )
        return (
            "<table><thead><tr>"
            "<th>Model</th>"
            "<th>% rows ≠ median of other 3</th>"
            "<th>Mean |distance from median of other 3|</th>"
            "<th>n</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
        )

    def example_block(ex: List[Dict], score_label: str) -> str:
        if not ex:
            return "<p><em>No multi-rater rows found.</em></p>"
        out = []
        for e in ex:
            scores_str = ", ".join(f"{model_short(m)}={v}" for m, v in e["scores"].items())
            reasonings_html = "".join(
                f"<li><b>{model_short(m)}:</b> {escape(r or '—')}</li>"
                for m, r in e["reasonings"].items()
            )
            out.append(
                "<div class='example'>"
                f"<div><b>UUID:</b> {e['uuid']} &nbsp; <b>Score spread ({score_label}):</b> {e['spread']}</div>"
                f"<div><b>Question:</b> {escape(e['question'])}</div>"
                f"<div><b>Excerpt:</b> <span class='excerpt'>{escape(e['excerpt'])}…</span></div>"
                f"<div><b>Scores:</b> {scores_str}</div>"
                f"<details><summary>Per-model reasoning</summary><ul>{reasonings_html}</ul></details>"
                "</div>"
            )
        return "\n".join(out)

    css = """
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:1100px;margin:2em auto;padding:0 1.5em;color:#222;line-height:1.55}
    h1{border-bottom:3px solid #333;padding-bottom:.3em}
    h2{border-bottom:1px solid #ccc;padding-bottom:.2em;margin-top:2em}
    h3{margin-top:1.6em}
    table{border-collapse:collapse;margin:1em 0;font-size:.95em}
    th,td{border:1px solid #bbb;padding:.4em .8em;text-align:left}
    th{background:#f0f0f0}
    tbody tr:nth-child(odd){background:#fafafa}
    .explain{background:#eef6ff;border-left:4px solid #4a8edc;padding:.7em 1em;margin:.5em 0 1em;border-radius:3px}
    .explain b{color:#1a4f8c}
    .warn{background:#fff4e0;border-left:4px solid #d99231;padding:.7em 1em;margin:.5em 0 1em;border-radius:3px}
    .key{background:#f3f6fa;padding:.5em .8em;border-radius:4px;display:inline-block;margin:.2em 0}
    .band{color:#666;font-size:.9em}
    .example{border:1px solid #ccc;border-radius:4px;padding:.7em 1em;margin:.7em 0;background:#fcfcfc}
    .excerpt{color:#555;font-size:.93em}
    code{background:#eee;padding:.05em .3em;border-radius:3px;font-size:.93em}
    details{margin-top:.4em}
    summary{cursor:pointer;color:#1a4f8c}
    .scalar{font-size:1.6em;font-weight:600;color:#1a4f8c;margin:.2em 0}
    .scalar-row{display:flex;gap:2em;flex-wrap:wrap;margin:1em 0}
    .scalar-card{border:1px solid #ccc;padding:.6em 1em;border-radius:4px;min-width:180px;background:#fff}
    .scalar-card .lbl{font-size:.85em;color:#666}
    """

    fleiss_band_c = kappa_band(fleiss_complexity)

    def as_pct(k: float) -> str:
        if k != k:
            return "n/a"
        return f"{100.0 * k:+.1f}%"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Inter-Annotator Agreement Report — 4 Evaluator Models</title>
<style>{css}</style>
</head>
<body>

<h1>Inter-Annotator Agreement (IAA) Report</h1>
<p>4 evaluator models scoring <b>{n_items}</b> Hebrew questions on two axes:
<code>complexity_score</code> (0–3) and <code>linguistic_score</code> (0–4).
The analysis below focuses on <code>complexity_score</code>; see section 2 for
why <code>linguistic_score</code> is excluded.</p>

<div class="explain">
<b>What is IAA?</b> When several "annotators" (here, 4 LLMs) score the same items,
inter-annotator agreement measures <i>how often they agree, beyond what we'd
expect by chance</i>. High agreement means the rubric is unambiguous and the
models interpret it similarly. Low agreement means the rubric is fuzzy <i>or</i>
some models drift from it.
</div>

<h2>1. Headline — group-level agreement on complexity_score</h2>

<div class="explain">
These three numbers summarise how well <i>all four models together</i> agree on
the complexity score, and are the single most important results in this report.
The first two are plain percentages — easy to read but uncorrected for chance.
The third (Fleiss' κ) corrects for chance-level agreement.
</div>

<div class="scalar-row">
  <div class="scalar-card">
    <div class="lbl">% items where all 4 models gave the <b>same</b> score (unanimous)</div>
    <div class="scalar">{group_unanimous_pct:.1f}%</div>
    <div class="band">raw agreement, not chance-corrected</div>
  </div>
  <div class="scalar-card">
    <div class="lbl">% items where all 4 models agreed <b>within ±1</b> (max − min ≤ 1)</div>
    <div class="scalar">{group_within1_pct:.1f}%</div>
    <div class="band">raw near-agreement, not chance-corrected</div>
  </div>
  <div class="scalar-card">
    <div class="lbl">Fleiss' κ — complexity_score</div>
    <div class="scalar">{kfmt(fleiss_complexity)}</div>
    <div class="band">{as_pct(fleiss_complexity)} &nbsp;·&nbsp; {fleiss_band_c}</div>
  </div>
</div>

<div class="explain">
<b>How to read these numbers.</b>
<ul>
  <li><b>% unanimous</b> and <b>% within ±1</b> are straightforward percentages
      of items: simple, intuitive, but they include agreement that could happen
      by chance alone (especially because the score distribution is skewed
      toward 1 and 2).</li>
  <li><b>Fleiss' κ</b> is reported on a conventional scale: <code>0</code> =
      chance-level agreement, <code>1</code> = perfect agreement. The
      "percentage" version (κ × 100) shown underneath is <i>not</i> a "% of
      items the models agreed on" — it's the fraction of the way from
      chance-level (0%) to perfect (100%). Rough interpretation guide: &lt;20%
      slight, 20–40% fair, 40–60% moderate, 60–80% substantial, &gt;80% almost
      perfect.</li>
</ul>
Fleiss' κ treats the four complexity values <code>0, 1, 2, 3</code> as
<i>unordered labels</i>, so any disagreement counts equally — <code>0 vs 3</code>
is treated as exactly as bad as <code>1 vs 2</code>. That's an imperfect fit
for a roughly-ordered scale like ours, but it's a reasonable choice given that
the scale isn't a clean numeric ordinal either: the values were introduced by
the rubric (<code>data_prep/prompts/03_question_assessment.md</code>) to label
four <i>qualitative</i> categories (paraphrased: <code>0</code> = unanswerable,
<code>1</code> = directly findable in text, <code>2</code> = needs simple
inference, <code>3</code> = needs deeper synthesis), and category
<code>0</code> ("unanswerable") is arguably not on the same axis at all. For
finer-grained pairwise analysis that does account for distance on the scale,
see the <i>linear / quadratic weighted κ</i> columns in the pairwise table
(section 3).
</div>

<h2>2. Score distributions per model</h2>

<h3>complexity_score (0–3)</h3>
{dist_table(dist_complexity, [0,1,2,3])}

<h3>linguistic_score (0–4)</h3>
{dist_table(dist_linguistic, [0,1,2,3,4])}

<div class="warn">
<b>⚠ Why <code>linguistic_score</code> is excluded from the rest of this
report:</b> the distribution above is extremely skewed — nearly every question
is rated <code>4</code> by every model. On a degenerate distribution like this,
all the agreement metrics break down: you can hit ~99% exact agreement just by
always saying "4", and chance-corrected metrics (κ, α) become numerically
unstable and uninformative. We therefore omit pairwise, group-level, outlier,
and example analyses for the linguistic axis. The distribution table above is
the only meaningful summary of it.
</div>

<h2>3. Pairwise agreement — complexity_score</h2>

<div class="explain">
<b>Exact %</b>: how often two models gave the <i>identical</i> score.<br>
<b>Within-1 %</b>: how often they agreed within ±1 (e.g. one said 2, the other 3).
This is more lenient and useful for ordinal scales where neighbours matter less
than distant disagreements.<br>
<b>Cohen's κ (kappa)</b>: agreement <i>after subtracting</i> the agreement you'd
get just by random chance. 0 = chance-level. 1 = perfect.
Rough guide: &lt;0.2 slight, 0.2–0.4 fair, 0.4–0.6 moderate, 0.6–0.8 substantial,
&gt;0.8 almost perfect.<br>
<b>Linear / Quadratic weighted κ</b>: penalises distant disagreements more than
near ones (so 0 vs 3 hurts more than 0 vs 1). Quadratic weighting penalises
distance even more strongly. For ordinal scores like ours, weighted κ is usually
the most appropriate measure.
</div>

{pair_table(pair_metrics_complexity)}

<h2>4. Outliers — which model disagrees most with the rest?</h2>

<div class="explain">
For each row, we compute the median score of the <i>other 3</i> models, then
ask how often (and by how much) a given model differed from that median.
A model with a high "deviation rate" is the most distinctive judge — that may
mean it's the most accurate or the most idiosyncratic. The data alone cannot
say which.
</div>

{deviation_table(deviation_complexity)}

<h2>5. Examples of maximum disagreement — complexity_score</h2>

{example_block(disagreement_examples_complexity, 'complexity_score')}

<h2>6. Bottom line</h2>
<ul>
<li>All 4 models gave the <b>same exact</b> complexity score on
<b>{group_unanimous_pct:.1f}%</b> of items, and agreed <b>within ±1</b> on
<b>{group_within1_pct:.1f}%</b> of items.</li>
<li>Group-level chance-corrected agreement on <code>complexity_score</code> is
<b>{fleiss_band_c}</b> by Fleiss' κ ({kfmt(fleiss_complexity)},
{as_pct(fleiss_complexity)}).</li>
<li>Pay attention to the <i>weighted</i> kappas (linear/quadratic) in the
pairwise table — they reflect the ordered nature of the scale better than
unweighted κ does.</li>
<li>The "outlier" table is diagnostic: the model with the highest deviation
rate is the one whose judgments most often differ from the consensus — useful
for deciding whether to weight or filter that model later.</li>
</ul>

<p style="color:#888;font-size:.85em;margin-top:3em">
Generated from <code>{escape(str(INPUT_JSON))}</code> using
<code>data_prep/generate_iaa_report.py</code>.
</p>

</body>
</html>
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    pivot, models, data = load_pivot()
    n_items = len(pivot)

    # Score distributions per model
    dist_c: Dict[str, Counter] = {m: Counter() for m in models}
    dist_l: Dict[str, Counter] = {m: Counter() for m in models}
    for u, by_model in pivot.items():
        for m, (c, l) in by_model.items():
            if c is not None:
                dist_c[m][c] += 1
            if l is not None:
                dist_l[m][l] += 1

    # Build per-pair aligned vectors (intersection of UUIDs both rated)
    def pair_vectors(field_idx: int):
        out: Dict[Tuple[str, str], Tuple[List[int], List[int]]] = {}
        for a, b in combinations(models, 2):
            va, vb = [], []
            for u, by_model in pivot.items():
                ra = by_model.get(a, (None, None))[field_idx]
                rb = by_model.get(b, (None, None))[field_idx]
                if ra is None or rb is None:
                    continue
                va.append(ra)
                vb.append(rb)
            out[(a, b)] = (va, vb)
        return out

    pv_c = pair_vectors(0)
    pv_l = pair_vectors(1)

    def pair_metrics(pv):
        out = {}
        for pair, (va, vb) in pv.items():
            ex, w1 = pairwise_agreement(va, vb)
            out[pair] = {
                "exact": ex,
                "within1": w1,
                "kappa_unweighted": cohen_kappa(va, vb, "none"),
                "kappa_linear": cohen_kappa(va, vb, "linear"),
                "kappa_quadratic": cohen_kappa(va, vb, "quadratic"),
            }
        return out

    pm_c = pair_metrics(pv_c)
    pm_l = pair_metrics(pv_l)

    # Fleiss' kappa: build (n_items × k) count matrix per axis
    def build_fleiss_matrix(field_idx: int, cats: List[int]):
        cat_idx = {c: i for i, c in enumerate(cats)}
        M = []
        for u, by_model in pivot.items():
            row = [0] * len(cats)
            for m in models:
                v = by_model.get(m, (None, None))[field_idx]
                if v is not None and v in cat_idx:
                    row[cat_idx[v]] += 1
            if sum(row) == len(models):
                M.append(row)
        return M

    fk_c = fleiss_kappa(build_fleiss_matrix(0, [0, 1, 2, 3]))

    # Group-level raw agreement on complexity_score across all 4 models
    n_full = 0
    n_unanimous = 0
    n_within1 = 0
    for u, by_model in pivot.items():
        vals = [by_model.get(m, (None, None))[0] for m in models]
        if any(v is None for v in vals):
            continue
        n_full += 1
        if len(set(vals)) == 1:
            n_unanimous += 1
        if max(vals) - min(vals) <= 1:
            n_within1 += 1
    group_unanimous_pct = (100.0 * n_unanimous / n_full) if n_full else 0.0
    group_within1_pct = (100.0 * n_within1 / n_full) if n_full else 0.0

    # Outlier deviation
    dev_c = majority_deviation_per_model(pivot, models, 0)
    dev_l = majority_deviation_per_model(pivot, models, 1)

    # Disagreement examples
    ex_c = all_disagreement_examples(data, pivot, models, 0, "complexity_score", max_examples=3)
    ex_l = all_disagreement_examples(data, pivot, models, 1, "linguistic_score", max_examples=3)

    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML.write_text(
        render_html(
            n_items=n_items,
            models=models,
            dist_complexity=dist_c,
            dist_linguistic=dist_l,
            pair_metrics_complexity=pm_c,
            fleiss_complexity=fk_c,
            group_unanimous_pct=group_unanimous_pct,
            group_within1_pct=group_within1_pct,
            deviation_complexity=dev_c,
            disagreement_examples_complexity=ex_c,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
