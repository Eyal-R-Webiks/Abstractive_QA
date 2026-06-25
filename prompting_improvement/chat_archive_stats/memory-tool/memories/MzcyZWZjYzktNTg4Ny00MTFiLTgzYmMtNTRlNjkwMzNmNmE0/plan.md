## Plan: Client Meeting Analytics Pack

Build a client-facing analytics package from the meeting_wed TSVs that combines decision-level KPIs, reliability diagnostics, and drill-down evidence. The approach separates true inter-annotator agreement (QWK) from score/quality proxies (IAA%), explicitly handles data anomalies (*, x, #REF!, mixed tokens like 2(1)/1/2), and produces a single HTML dashboard structured for a mixed audience (executive + ops + research).

**Steps**
1. Phase 1 — Data Contract & Parsing Rules
1.1 Define column groups and canonical schema from Results.tsv and QWK_pair_total.tsv (metadata, per-metric annotator scores, consensus fields, IAA%, QWK, 4avg/5avg).
1.2 Define parsing rules for mixed formats: percentage strings, consensus tokens (2(1), 1/2), missing markers (*), issue flag (x), and totals row anomalies (#REF!).
1.3 Create a metric dictionary with explicit interpretation for meeting use: QWK as agreement, IAA as score proxy with caveat. (*blocks phases 2-5*)

2. Phase 2 — Quality Checks & Data Readiness
2.1 Run completeness checks by metric (co/rl/cm/ft/at): missingness rates, invalid tokens, parse failures.
2.2 Produce a “known limitations” table for client transparency (especially attribution/at_issue and total row #REF!).
2.3 Validate that pairwise QWK table aligns with annotator identities and metric names used in Results.tsv. (*depends on step 1*)

3. Phase 3 — KPI Layer (Executive Story)
3.1 Compute headline KPIs:
- Overall QWK by metric (from QWK_pair_total.tsv)
- Mean/median of 4avg and 5avg
- Perfect-consensus rate buckets (100%, 50%, 33.3%, 16.7%, 0%)
- Coverage split by source and level
3.2 Build caveated KPI tiles:
- “Agreement” tiles use QWK
- “Quality/score” tiles use IAA/avg fields with note that these are not reliability coefficients
3.3 Add one-slide narrative summary: strongest/weakest dimensions, where disagreement concentrates. (*depends on phases 1-2*)

4. Phase 4 — Diagnostic Layer (Ops/Research Story)
4.1 Compute disagreement diagnostics:
- Pairwise annotator gap matrix by metric
- Per-metric disagreement distribution
- Source x level x metric breakdown
4.2 Build derived metrics for triage:
- Ambiguity index per question (variance/spread across annotators)
- Disagreement severity buckets
- “High score, low agreement” and “low score, high agreement” slices
4.3 Identify top review candidates (records) with links back to LS task URLs for discussion. (*depends on phases 1-2; parallel with phase 3 once cleaned*)

5. Phase 5 — Visualization Storyboard (Single HTML Dashboard)
5.1 Section A: Executive snapshot
- KPI cards (QWK, 4avg/5avg, coverage)
- Metric ranking bar chart
5.2 Section B: Reliability and agreement
- Heatmap: metric x annotator pair QWK
- Stacked bars: agreement bucket distribution by metric
5.3 Section C: Segmentation
- Grouped bars or heatmap: source x metric
- Grouped bars or heatmap: level x metric
- Optional source x level faceted chart if sample sizes are stable
5.4 Section D: Outliers and action list
- Table of top disagreement records with metric flags and LS URLs
- Attribution caveat panel (at_issue/x + missingness)
5.5 Section E: Appendix methodology
- Definitions, formulas, caveats, and data-cleaning assumptions. (*depends on phases 3-4*)

6. Phase 6 — Meeting Narrative & Q&A Preparation
6.1 Build a 10-15 minute talk track for mixed audience:
- What is stable and trustworthy
- Where rubric/training likely needs refinement
- What decisions the client can take now
6.2 Prepare “defensive” Q&A set:
- Why IAA and QWK diverge
- Why attribution is caveated
- Whether level/source mix biases results
6.3 Prepare appendix backup views for expected deep-dive questions. (*depends on phase 5*)

7. Phase 7 — Verification Before Meeting
7.1 Metric validation checklist:
- Recompute a random sample manually for at least 10 records
- Verify all dashboard aggregates reconcile to TSV counts
7.2 Visualization QA:
- No chart uses malformed total row
- All caveats visible on screen and in appendix
7.3 Stakeholder dry-run:
- One rehearsal pass with timing and “single-message per chart” validation. (*depends on phases 3-6*)

**Relevant files**
- /Users/eyalrosenstein/Documents/Abstractive_QA/Answers/results/meeting_wed/Results.tsv — primary record-level data with per-metric annotator scores, IAA%, QWK, 4avg/5avg, issue tokens.
- /Users/eyalrosenstein/Documents/Abstractive_QA/Answers/results/meeting_wed/QWK_pair_total.tsv — pairwise agreement backbone for reliability visuals.
- /Users/eyalrosenstein/Documents/Abstractive_QA/Answers/results/meeting_wed/headers.tsv — schema clarification for presentation labeling.
- /Users/eyalrosenstein/Documents/Abstractive_QA/generate_iaa_report.py — reusable computation/reporting logic and agreement conventions.
- /Users/eyalrosenstein/Documents/Abstractive_QA/Answers/results/fix_iaa.py — quick reference for IAA-style calculations and sanity checks.
- /Users/eyalrosenstein/Documents/Abstractive_QA/Reports/annotation_stats_0616_tue_1100.md — prior report pattern for annotator-level comparison and narrative style.
- /Users/eyalrosenstein/Documents/Abstractive_QA/Resources/project_info/MAFAT_req_doc_v3.md — project success criteria and metric definitions for client alignment.
- /Users/eyalrosenstein/Documents/Abstractive_QA/Resources/project_info/Abstractive QA_הגדרות_תיוג_שלב_ב_v1.md — detailed scoring rubric and interpretation guidance.
- /Users/eyalrosenstein/Documents/Abstractive_QA/Resources/project_info/Level_definitions_v2_proposal.md — level semantics for level-based segmentation framing.
- /Users/eyalrosenstein/Documents/Abstractive_QA/Resources/project_info/project_end_goal.txt — user-case framing for executive narrative.

**Verification**
1. Reconcile all dashboard totals against parsed Results.tsv row counts (excluding malformed total row).
2. Validate QWK values displayed in visuals exactly match QWK_pair_total.tsv for each metric and pair.
3. Spot-check at least 10 records spanning different levels/sources for parsing correctness (percentages, 2(1), 1/2, *, x).
4. Confirm every executive claim maps to a chart and every chart maps to one explicit decision/action.
5. Run a short dry-run and collect likely client objections, then ensure appendix views answer each objection.

**Decisions**
- Deliverable format: single HTML report/dashboard.
- Audience: mixed (executive + ops + research).
- Reporting convention: include both IAA and QWK, with explicit caveat that QWK is the agreement coefficient.
- Attribution handling: include in main report with clear caveats for at_issue/missingness.
- Scope output: implementation plan plus chart storyboard.
- Included scope: meeting_wed dataset only, no model retraining recommendations.
- Excluded scope: coding implementation, pipeline refactor, or changes to labeling policy documents.

**Further Considerations**
1. If time is tight, prioritize Sections A-B-D of the dashboard; keep segmentation (Section C) as appendix.
2. If client challenges rubric consistency, prepare one extra appendix: side-by-side examples of high-score/low-agreement records.
3. If attribution caveat dominates discussion, pre-commit to a short follow-up calibration protocol instead of debating metric validity during the meeting.