# הגדרות רמות סיווג שאלות — הצעה לגרסה 2
## Abstractive QA Project — Level Definitions Revision Proposal

**Date:** May 2026  
**Purpose:** Proposed revision of question-level definitions for Part I annotation (question classification only; answer evaluation is out of scope here).  
**Working principle:** Definitions are *Bloom-informed* but *not Bloom-centred*. Bloom's Revised Taxonomy (Anderson & Krathwohl, 2001) is used as a reference and communication device for academic audiences, not as a definitional foundation. The taxonomy is self-standing and purpose-built for document-grounded abstractive QA evaluation.

---

## Current Definitions (v1.4)

> Source: `resources/project_info/guidelines_part1_v1.4.md` §§ "רמה 0" – "רמה 3"  
> Secondary source: `resources/project_info/Level_definitons_suggestion.md`

### רמה 0: ללא מענה במסמך
שאלות רלוונטיות לנושא המסמך אך התשובה אינה מופיעה בו כלל. כדי לענות "תשובה נכונה", המודל נדרש לזהות שהמידע הרלוונטי לא נמצא במסמך ולהצהיר על כך במפורש.

*התאמה לבלום (v1.4):* ידע מטא-קוגניטיבי – זיהוי גבולות הידע (מה ידוע ומה לא).

### רמה 1: איתור ושליפה
התשובה נמצאת במשפט אחד, ביטוי ספציפי או נתון המצוין מפורשות במסמך. לא נדרשת הבנה מעמיקה או חיבור בין רעיונות. גם שאלה כמו "מה הם קו"ח דיגיטליים?" נכנסת לרמה 1 כל עוד היא דורשת להסביר מושג/רעיון ספציפי ולא מערכות יחסים בין דברים.

*התאמה לבלום (v1.4):* "זכירה" – היכולת לזהות ולשלוף עובדות ומושגים בסיסיים מהטקסט.

### רמה 2: אינטגרציה והבנה
התשובה דורשת חיבור בין 2–3 משפטים או רעיונות המופיעים במקומות שונים במסמך, הבנת קשרים לוגיים, או יישום מידע בהקשר חדש אך דומה. מענה על השאלה דורש התייחסות למערכת יחסים בין פרטי מידע, כמו: מה קדם למה, מה הוביל למה, מה ההבדלים בין X ל-Y.

*התאמה לבלום (v1.4):* "הבנה" ו"יישום" – חיבור בין פריטי מידע וזיהוי קשרים לוגיים ביניהם.

### רמה 3: חשיבה קדימה, אבסטרקטיות וסינתזה
השאלה דורשת מהמודל להבין את ה"תמונה הגדולה" או ליישם מסקנות על תרחיש חדש. כולל: חיזוי והשלכות, הבעת עמדה מנומקת, סינתזה מוגבלת, הסקת מסקנה. רמה זו יכולה לדרוש שימוש בידע עולם בסיסי אבל לא בעובדות שאינן בטקסט.

*התאמה לבלום (v1.4):* "ניתוח" – זיהוי דפוסים, פירוק מידע לגורמיו, הסקת מסקנות שאינן מפורשות בטקסט.

---

## Proposed Definitions (v2)

### רמה 0: ללא מענה במסמך *(name unchanged)*

> **הגדרה:**
> השאלה רלוונטית לנושא המסמך, אך המידע הדרוש למענה עליה **אינו מופיע בו כלל**. תשובה נכונה היא הצהרה מפורשת שהמסמך אינו מכיל מידע זה. שאלה ברמה זו היא שאלה תקינה לחלוטין — היא בודקת האם המודל יודע *מתי לא לענות*.

**What changed:** The v1.4 Bloom framing ("ידע מטא-קוגניטיבי") is removed. Bloom's metacognitive dimension refers to awareness of one's *own* thinking processes — applying it to "the document doesn't contain this" is a category error. This level is a document-grounded QA-specific category with no direct Bloom equivalent.

*הערת בלום (אינפורמטיבית בלבד):* אין מקבילה ישירה בטקסונומיה של בלום — קטגוריה ייחודית ל-QA מבוסס-מסמך.

---

### רמה 1: איתור ושליפה *(name unchanged)*

> **הגדרה:**
> התשובה מצויה **במפורש** במשפט אחד, ביטוי, שם, מספר או פרט עובדתי בטקסט. המענה דורש איתור ושליפה של פריט מידע אחד — או כמה פריטים נפרדים — **מבלי שנדרש להתייחס לקשר לוגי כלשהו ביניהם**.
>
> גם שאלה שדורשת להגדיר מושג, לתאר תהליך ספציפי, או לסכם קטע בודד שייכת לרמה זו — כל עוד אין צורך לחבר בין חלקים שונים של המסמך ולא לנסח מערכת יחסים בין דברים.
>
> **המבחן המכריע:** האם המענה דורש ביסוס של קשר לוגי כלשהו בין פרטי מידע? אם לא — רמה 1.

**What changed:** The concept-explanation edge case ("מה הם קו"ח דיגיטליים?") was previously a sub-bullet. It is now inside the definition itself, because annotators should reach this clarification without hunting for it. The discriminating criterion ("no logical relationship required") is now explicit.

*הערת בלום (אינפורמטיבית בלבד):* מקביל ל"זכירה" (Remember) בטקסונומיה של בלום.

---

### רמה 2: אינטגרציה והסקה *(name changed: הבנה → הסקה)*

> **הגדרה:**
> התשובה דורשת **חיבור של 2–3 פרטי מידע, משפטים או רעיונות המופיעים במקומות שונים במסמך**, והסקת הקשר הלוגי שביניהם. הקשר הנדרש — כרונולוגי, סיבה-ותוצאה, ניגוד, השוואה, ועוד — נשען על מידע שכתוב במסמך, גם אם אינו מנוסח שם במפורש כ"קשר".
>
> **המבחן המכריע:** כל פרטי המידע הרלוונטיים מופיעים בטקסט — כל שנדרש הוא לזהות אותם, לחבר ביניהם, ולנסח את הקשר שביניהם. אם כן — רמה 2.
>
> **ההבדל מרמה 3:** ברמה 2 הקשר נובע ישירות מחיבור מצומצם של עובדות. ברמה 3 נדרש "צעד אחורה" — לראות דפוס, מגמה או מסקנה שאינם ניתנים לגזירה ישירה מחיבור כמה פרטים.

**What changed:** "הבנה" → "הסקה". "הבנה" (understanding) is too broad — it could describe any comprehension including Level 1. "הסקה" (inference) is operationally precise: it signals that a logical relationship must be drawn, not just understood. This also sharpens the Level 2/3 boundary, which is the primary source of annotator disagreement.

*הערת בלום (אינפורמטיבית בלבד):* מקביל בקירוב ל"הבנה" (Understand) ו"יישום" (Apply) בטקסונומיה של בלום.

---

### רמה 3: ניתוח וסינתזה *(name changed: חשיבה קדימה, אבסטרקטיות וסינתזה → ניתוח וסינתזה)*

> **הגדרה:**
> השאלה דורשת הבנת ה"תמונה הגדולה" — **הסקת מסקנה, זיהוי דפוס או מגמה, או ניסוח תובנה שאינם מוצהרים בשום מקום במסמך**, ואינם נובעים מחיבור ישיר של כמה פרטים. רמה זו כוללת בין היתר:
>
> - **זיהוי דפוסים, מגמות או סתירות** לאורך הטקסט
> - **הסקת מסקנה רחבה** שאינה מוצהרת ("מה ניתן להסיק על...?")
> - **חיזוי והשלכה** על בסיס המידע שבמסמך ("מה צפוי לקרות אם...?")
> - **הבעת עמדה מנומקת** על בסיס ראיות מהמסמך ("האם הטקסט תומך ב-X?")
> - **סינתזה** — גיבוש תמונת מצב מתוך מערכות יחסים מרובות
>
> רמה זו **עשויה** לדרוש ידע עולם בסיסי וכללי (למשל: ניסוח שלילי מבטא ביקורת, סתירה בין דברים מצביעה על מתח, אנשים עשויים לומר דבר ולהתכוון לאחר) — אך **לא עובדות ספציפיות שאינן בטקסט**.
>
> **המבחן המכריע:** האם המסקנה שהשאלה מבקשת נמצאת *במפורש* בטקסט, או נובעת *ישירות* מחיבור מצומצם של עובדות? אם כן — בדוק שוב אם מדובר ברמה 2. אם המסקנה דורשת ראייה כוללת, זיהוי דפוס, או שימוש בשיפוט מסדר גבוה — רמה 3.

**What changed:** "חשיבה קדימה" is dropped entirely. "קדימה" (forward/ahead) implicitly restricts the level to predictive/prospective tasks, whereas Level 3 equally includes retrospective pattern analysis, contradiction identification, and evidence-based stances — none of which are "forward-looking." The sub-types list (previously only in the generation prompt) is now in the annotator definition, giving concrete anchors for the hardest level to classify.

*הערת בלום (אינפורמטיבית בלבד):* מקביל בקירוב ל"ניתוח" (Analyze) בטקסונומיה של בלום.

---

## Summary of Changes

| | v1.4 (current) | v2 (proposed) |
|---|---|---|
| Level 0 Bloom framing | "ידע מטא-קוגניטיבי" — used as justification | Removed; described as QA-specific category |
| Level 1 concept-definition case | Sub-bullet only | Promoted into main definition body |
| Level 2 name | **אינטגרציה והבנה** | **אינטגרציה והסקה** |
| Level 2/3 boundary criterion | Implicit | Explicit primary criterion at both levels |
| Level 3 name | **חשיבה קדימה, אבסטרקטיות וסינתזה** | **ניתוח וסינתזה** |
| Level 3 sub-types list | Generation prompt only (`data_prep/prompts/02_question_generation.md`) | Brought into annotator definition |
| Bloom references overall | Partial foundation | Informational footnotes only |

---

## Rationale and Evidence

### On Level 0: removing the Bloom metacognitive framing

The v1.4 framing cites Bloom's metacognitive dimension. However, Bloom's metacognition refers to awareness of one's own cognitive processes ("what do I know about how I think?"), not to recognising the absence of information in a specific external document. No paper in the literature review applies Bloom's metacognitive dimension to unanswerable-question detection.

> Citation: `resources/Bloom_taxonomy/chunks/LLMs_Bloom.jsonl` § section "Metacognitive" — the paper notes that Metacognitive knowledge is not covered by current LLM benchmarks and is categorised as a *knowledge dimension*, not a cognitive level. Mapping Level 0 to it conflates two separate axes of the taxonomy.

### On Level 2: הבנה → הסקה

"הבנה" (understanding) appears at every level of the taxonomy — it is not a discriminating criterion. "הסקה" (inference/drawing a logical relation) is the specific cognitive act that distinguishes Level 2 from Level 1: the answerer must draw a connection, not merely locate information.

> Citation: `resources/project_info/Level_definitions_examples.md` § "רמה 2 — אינטגרציה והסקה" — the earlier working document used "הסקה"; the regression to "הבנה" occurred in v1.4 without a stated justification.
>
> Citation: `resources/Bloom_taxonomy/chunks/LLMs_Bloom.jsonl` § section "Metacognitive" chunk 1 — Bloom's "Understand" is defined as "construct meaning from instructional messages," which is too broad to serve as a level discriminator in a QA context.

### On Level 3: dropping "קדימה"

"חשיבה קדימה" (forward-thinking) implies prediction and prospective tasks. The level's own definition in v1.4 — and all examples across the project documents — include retrospective analysis, contradiction detection, and stance-taking, none of which are forward-looking. The name creates a systematic blind spot where annotators may under-classify retrospective synthesis as Level 3.

> Citation: `resources/project_info/guidelines_part1_v1.4.md` § "רמה 3: חשיבה קדימה, אבסטרקטיות וסינתזה" — the definition body lists "הסקת מסקנה" and "הבעת עמדה מנומקת" as subtypes, neither of which is captured by "קדימה."
>
> Citation: `data_prep/prompts/02_question_generation.md` § "רמה 3: חשיבה אבסטרקטית וסינתזה" — the generation prompt (the richest definition in the project) lists: זיהוי מגמות וסתירות, הרכבת אסטרטגיה, הסקת מסקנה רחבה, הבעת עמדה מנומקת. None of these are exclusively forward-looking.

### On the Level 2/3 boundary as the primary IAA risk

The MAFAT requirement document sets IAA = 0.9 (`resources/project_info/MAFAT_req_doc_v3.md` § "IAA = 0.9"). The 2/3 boundary is the point of highest ambiguity: both levels require drawing logical inferences from text. The proposed explicit discriminating criterion — "all raw material is in the text and only the connection needs to be made" (Level 2) vs. "the conclusion is not derivable from direct connection of a small number of facts" (Level 3) — is intended to reduce this ambiguity.

> Citation: `resources/Bloom_taxonomy/chunks/2408.04394v1.jsonl` § section "2.3 Human Evaluation" — Scaria et al. report inter-annotator agreement on Bloom's Level classification using quadratic weighted Cohen's κ, noting that Bloom level is an *ordinal* metric requiring weighted agreement. Their results show that even expert annotators with domain knowledge achieve κ values in the 0.61–0.67 range for Bloom level — substantially below the 0.9 threshold required by MAFAT. Sharper discriminating criteria directly improve this metric.

### On bringing Level 3 sub-types into the annotator definition

The generation prompt (`data_prep/prompts/02_question_generation.md` § "רמה 3") lists concrete sub-types (prediction, strategy, spotting contradictions, evidence-based stance). The annotator guidelines (v1.4) do not. This creates an asymmetry: the model generating questions has richer guidance than the humans classifying them, which may contribute to misclassification.

### On Bloom as reference vs. foundation

> Citation: `resources/Bloom_taxonomy/chunks/LLMs_Bloom.jsonl` § section "Abstract" — the foundational paper on LLMs and Bloom's taxonomy maps *existing benchmarks* to Bloom levels and finds that Metacognitive, Create, and Evaluate are not covered by current LLM benchmarks. This project's taxonomy (0–3) maps to Remember/Understand+Apply/Analyze, covering the lower four levels — consistent with where LLM performance differentiation is empirically meaningful.
>
> Citation: `resources/Bloom_taxonomy/chunks/2408.04394v1.jsonl` § section "3 Results and Analysis" — Scaria et al. find that GPT-4 adheres to its target Bloom level in only ~70% of generated questions, and that an LLM evaluator (Gemini Pro) does not reliably agree with human expert Bloom classification. This supports: (a) the necessity of human annotation for level verification, and (b) using Bloom as a rough scaffold rather than a precise operational framework.
>
> Citation: `resources/Bloom_taxonomy/chunks/Enhanced_Blooms_Educational_Taxonomy_for_Fosterin.jsonl` § section "2.2 The challenges of guiding and regula" — notes that "in real-world use, the BET framework proved to be often less precise, as the complexity of cognitive demands can vary depending on specific goals." The paper proposes a full replacement taxonomy (LBET) for student-LLM interaction contexts, confirming that researchers actively adapt or replace Bloom when the original framework is not fit for purpose.

---

## Cross-Document Consistency Note

The following documents currently contain varying phrasings of the level definitions and should be aligned to v2 if this proposal is adopted:

| Document | Current Level 2 name | Current Level 3 name |
|---|---|---|
| `resources/project_info/guidelines_part1_v1.4.md` | אינטגרציה והבנה | חשיבה קדימה, אבסטרקטיות וסינתזה |
| `resources/project_info/Level_definitons_suggestion.md` | אינטגרציה והבנה (הבנה/יישום) | חשיבה אבסטרקטית וסינתזה |
| `resources/project_info/Level_definitions_examples.md` | אינטגרציה והסקה (הבנה/יישום) | חשיבה ביקורתית והסקת מסקנות (ניתוח) |
| `resources/project_info/MAFAT_req_doc_v3.md` | אינטגרציה | אבסטרקטית |
| `data_prep/prompts/02_question_generation.md` | אינטגרציה והבנה | חשיבה אבסטרקטית וסינתזה |
| **This document (v2 proposal)** | **אינטגרציה והסקה** | **ניתוח וסינתזה** |
