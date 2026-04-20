# Product Requirements Document (PRD)
## PLExp Pilot For Hebrew QA Pipeline

**Project:** PLExp (Procedural Language Experimentation)  
**Version:** 1.0  
**Date:** April 2026  
**Status:** Exploratory Pilot (In Development)  
**Audience:** External ML Pipeline Client

---

## 1. Executive Summary

**PLExp (PipeLine EXPerimentation)** is a small-scale exploratory pilot project designed to:
1. **Develop pipeline architecture skills** — build, test, and validate data collection → processing → generation workflows
2. **Prototype core functionality** — test LLM-based Hebrew question generation on real Wikipedia data
3. **Validate initial assumptions** — confirm feasibility before scaling to the larger production project

**Scope:** 90 annotated Hebrew QA samples (100 Wikipedia articles, 6 text variations) with machine-generated information-seeking questions.

**Purpose:** PLExp serves as a proof-of-concept that will inform the design of a larger, multi-source Hebrew QA dataset creation project involving human annotation layers and model answer generation/evaluation.

**Outcome:** Validated pipeline architecture, sample dataset quality metrics, and documented learnings to guide the larger project.

---

## 2. Problem Statement

**Context:**
- The larger target program requires a full Hebrew QA workflow: question generation, human annotation, answer generation by multiple models, and comparative evaluation
- There is execution risk in moving directly to large-scale production without first validating pipeline mechanics and quality assumptions
- Hebrew-source QA dataset creation needs practical experimentation before committing to broader scope

**Challenge:**
Use PLExp as a controlled pilot that:
- Tests pipeline-building methodology and workflow design with AI assistance
- Verifies early assumptions about Hebrew information-seeking question quality
- Produces evidence and implementation patterns to de-risk the larger multi-stage project

---

## 2.1 Program Context: Pilot vs. Larger Project

**PLExp (This PRD):**
- Single-source pilot (Hebrew Wikipedia)
- Focus on initial experimentation and exploration
- Delivers pilot dataset and documented learnings

**Larger Project (Next Program Stage):**
- Uses 100-300 character Hebrew excerpts from three native Hebrew sources
- Generates "interesting" information-seeking Hebrew questions with LLMs
- Adds human annotation for question classification and evaluation
- Uses approved questions to prompt answers from multiple models
- Adds human evaluation/ranking/classification of model answers

---

## 3. Goals & Objectives

### Primary Goals (PLExp Pilot)
1. **Build and validate pipeline architecture** — Create reproducible, modular pipeline for data collection → text processing → question generation
2. **Prototype LLM question generation** — Test feasibility and quality of machine-generated Hebrew information-seeking questions
3. **Generate pilot dataset** — Collect 90 high-quality samples with metadata for manual review
4. **Document learnings** — Identify best practices, failure modes, and scaling considerations for the production project

### Secondary Goals (Informing Production)
- Validate question quality standards before scaling to larger annotation effort
- Test both Ollama (free/local) and Claude (paid/cloud) LLM options for cost/quality trade-offs
- Identify data structure and metadata requirements for downstream annotation
- Create reusable templates and documentation for larger project teams

### Constraints (Keeping PLExp Exploratory)
- Limited to single source (Wikipedia) vs. 3 sources in production project
- 90 samples vs. hundreds/thousands in full project
- No annotation layer in PLExp (manual review only) vs. systematic annotation in production

---

## 4. Success Criteria

| Metric | Target | Acceptance Criteria |
|--------|--------|-------------------|
| **Data Volume** | 90 rows | Generate questions for 15 rows × 6 text variants |
| **Topic Coverage** | 20 categories | At least 4 articles per topic in final dataset |
| **Question Quality** | 100% valid | All questions are information-seeking, grammatically correct Hebrew |
| **Text Diversity** | 6 variants/article | Mixed lengths (100/150/200 chars) and positions (first/elsewhere) |
| **Completion Date** | By end of April 2026 | Full pipeline tested and production-ready |
| **Pipeline Reliability** | 95%+ success rate | <5% failed API calls or invalid outputs |
| **Pilot Learning Value** | High | Clear list of validated assumptions, failed assumptions, and next-stage recommendations |

---

## 5. Scope

### In Scope ✓
- Extract 100 Hebrew Wikipedia articles from 20 categories
- Generate 6 text variations per article (multiple lengths + positions)
- Create information-seeking questions for 90 samples (15 per text variant)
- Store output in CSV format with proper metadata (uid, wiki_link, title, topic, question)
- Implement two LLM integration paths (Ollama local + Claude API)
- Document pipeline with code comments and HTML guide
- Version control with Git/GitHub
- Capture explicit pilot findings to guide the larger project design

### Out of Scope ✗
- Full annotation workflow for question quality/classification
- Multi-language support beyond Hebrew
- Real-time API serving
- User interface or dashboard
- Model answer generation and ranking across multiple models
- Performance optimization beyond current scope
- Multi-source ingestion beyond Hebrew Wikipedia

---

## 6. Requirements

### 6.1 Functional Requirements

**FR1: Data Collection**
- Must extract articles from Hebrew Wikipedia MediaWiki API
- Must retrieve 5 articles per topic across 20 categories (100 total)
- Must handle API rate limiting gracefully with retries
- Must validate that returned articles match their assigned topic

**FR2: Text Extraction**
- Must create 6 variations per article:
  - First 100, 150, 200 characters
  - Random 100, 150, 200 characters (starting at sentence boundaries)
- Must extract text starting at sentence boundaries (after periods) to ensure coherence
- Must preserve Unicode and special characters in Hebrew text

**FR3: Question Generation**
- Must generate one information-seeking question per text sample (90 total)
- Questions must be:
  - Information-seeking (not factual recall, but asking about concepts/relationships)
  - Grammatically correct Hebrew
  - Natural phrasing (not robotic or templated)
  - Appropriate to text length (avoid overly complex questions for 100-char texts)

**FR4: Output Format**
- Must produce 6 CSV files (one per text variant)
- Each row must include: extracted_text, uid, wiki_link, article_title, topic, question
- Must use UTF-8 encoding
- Must handle special characters correctly

**FR5: Error Handling**
- Must log all API failures with timestamps and error details
- Must implement fallback mechanisms for failed question generation
- Must validate CSV structure before final output

### 6.2 Non-Functional Requirements

**NFR1: Performance**
- Data collection: Complete in <30 minutes for 100 articles
- Question generation: Complete in <2 hours for 90 samples
- API overhead: Reuse connections to minimize latency

**NFR2: Reliability**
- 95%+ success rate for API calls (allow up to 5% failures with fallbacks)
- All data must persist through process interruptions (save state incrementally)
- No data loss between pipeline stages

**NFR3: Scalability**
- Architecture must support 10x scaling (1000 articles) without major refactoring
- LLM integration must work with swap-able backends (Ollama ↔ Claude)

**NFR4: Maintainability**
- Code must include docstrings and inline comments
- Configuration (topics, API keys, parameters) must be easily modifiable
- Git history must reflect all significant changes

**NFR5: Cost Efficiency**
- Ollama option: $0 (local execution)
- Claude option: <$0.50 for 90 samples (when scaled to production)

---

## 7. Features & Specifications

### 7.1 Stage 1: Wikipedia Data Collection (`wiki_extract.py`)

**Input:** None (queries Wikipedia directly)

**Output:** `output5.csv` (100 articles, 6 text variations each)

**Process Flow:**
```
Define 20 Topics
    ↓
For each topic:
  - Query Wikipedia categorymembers API
  - Randomly select 5 articles with offset
  - For each article:
    - Fetch full text content
    - Extract 6 text variations via extract_at_sentence_boundary()
    - Generate unique ID (UUID)
    - Capture metadata (wiki_link, title, topic)
    ↓
Output to CSV with 10 columns
```

**Key Functions:**
- `extract_at_sentence_boundary(text, length)` — Extract N characters starting after a random period
- Wikipedia API calls with User-Agent header (required)
- Random shuffling for diversity

**Error Handling:**
- Retry failed API calls up to 3 times
- Log failed articles with reasons
- Skip articles with <500 total characters

### 7.2 Stage 2: Question Generation (`generate_questions.py`)

**Input:** 6 CSV files from `input_for_q/` folder (15 rows each = 90 total)

**Output:** 6 CSV files in `output_for_q/` with `_q` suffix (same columns + "question")

**LLM Integration:**

**Option A: Ollama (Recommended for initial phase)**
- Free, runs locally
- Model: Mistral 7B
- API endpoint: `http://localhost:11434/api/generate`
- Configuration: Requires `ollama serve` running
- Cost: $0

**Option B: Claude API (For production scale)**
- Anthropic Claude 3.5 Haiku model
- Requires API key: `ANTHROPIC_API_KEY` env variable
- Cost: ~$0.002 per 1000 tokens (~$0.02-0.50 for full run)

**Prompt Template:**
```
Given the following text excerpt, generate a single information-seeking question
that would naturally be asked by someone wanting to learn more about the content.

The question should:
- Be information-seeking (not simple factual recall)
- Sound natural and conversational in Hebrew
- Be appropriate to the text length
- Not contain information not present in the text

Text: [extracted_text]

Question:
```

**Quality Assurance:**
- All generated questions validated for non-empty output
- Fallback: If generation fails, use first 20 words + "?"
- Log all failures for review

---

## 8. Data Specifications

### 8.1 Input Data Structure

**Source:** Hebrew Wikipedia (https://he.wikipedia.org)

**Topics Included (20 categories):**
1. Technology | 2. Science | 3. Sports | 4. Arts | 5. Music
6. Literature | 7. Cinema | 8. History | 9. Geography | 10. Biology
11. Chemistry | 12. Physics | 13. Mathematics | 14. Philosophy | 15. Religion
16. Society | 17. Economy | 18. Politics | 19. Medicine | 20. Transportation

**Selection Method:** Random selection from Wikipedia category members (not trending/popular bias)

### 8.2 Output Data Structure

**CSV Format:**
```
extracted_text, uid, wiki_link, article_title, topic, question
```

**Field Specifications:**
| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `extracted_text` | String | "ויקיפדיה היא אנציקלופדיה ..." | Hebrew text, varies by variant |
| `uid` | UUID | "123e4567-e89b-12d3-a456-426614174000" | Unique identifier for row |
| `wiki_link` | URL | "https://he.wikipedia.org/wiki/Article" | Direct Wikipedia link |
| `article_title` | String | "ויקיפדיה" | Article title in Hebrew |
| `topic` | String | "Technology" | One of 20 categories |
| `question` | String | "מה משמעות המונח..." | Information-seeking question |

**Encoding:** UTF-8 (handles Hebrew characters correctly)

**Total Rows:** 90 (15 per text variant × 6 variants)

---

## 9. User Stories

**US1:** As an ML engineer, I want to access diverse Hebrew QA samples so that I can train my question-answering model with varied examples.

**US2:** As a researcher, I want to understand how each sample was generated so that I can validate the pipeline's quality.

**US3:** As a product manager, I want to scale this to 1000+ samples so that I can build a production-grade dataset.

---

## 10. Timeline & Milestones

| Phase | Task | Duration | Deadline |
|-------|------|----------|----------|
| **Phase 1** | Data collection (wiki_extract.py) | 1 day | April 12 ✓ |
| **Phase 2** | Question generation - Ollama test | 1 day | April 13 ✓ |
| **Phase 3** | Claude API integration & testing | 1 day | April 13 ✓ |
| **Phase 4** | Production run + quality validation | 1 week | April 19 (target) |
| **Phase 5** | Final review, optimization, archival | 3 days | April 22 (target) |

---

## 11. Dependencies & Risks

### External Dependencies
- **Wikipedia API:** Intermittent availability (~99.5% uptime)
- **LLM Services:** Claude API (paid service, quota depends on account credits)
- **Python Libraries:** requests, anthropic, pandas

### Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Wikipedia API rate limiting | Pipeline slowdown | Implement backoff/retry logic |
| Claude API quota exceeded | Question generation blocked | Use Ollama as fallback |
| Low question quality from LLM | Dataset unusable | Manual review sample + refinement prompt |
| Non-diverse article selection | Biased training data | Random offset + category filtering |
| UTF-8 encoding issues | Data corruption | Validate all outputs before CSV write |

---

## 12. Success Handoff Criteria

PLExp pilot will be considered **ready to hand off to next-stage planning** when:

- ✅ All 90 samples successfully generated with valid questions
- ✅ Manual review of 10% sample (9 questions) confirms information-seeking quality
- ✅ All questions are grammatically correct Hebrew
- ✅ CSV files validated for correct structure and encoding
- ✅ Full documentation with reproducibility steps included
- ✅ Git history with tagged releases
- ✅ Pipeline can run end-to-end with <5% failures
- ✅ Pilot findings are documented with concrete implications for larger project design

---

## 13. Future Roadmap (Toward Larger Project)

**Phase 2 - Multi-Source Data Foundation:**
- Add two additional native-Hebrew sources (total 3 sources)
- Standardize excerpt creation (100-300 chars) across sources
- Add source-level metadata and balancing strategy

**Phase 3 - Question Annotation Layer:**
- Define annotation guidelines for "interesting" information-seeking questions
- Run human classification/evaluation of generated questions
- Produce quality labels and inter-annotator agreement reporting

**Phase 4 - Model Answer Generation & Evaluation:**
- Prompt multiple models with curated questions
- Collect model answers under standardized settings
- Add human ranking/classification/evaluation of answers

**Phase 5 - Comparative Analysis & Production Planning:**
- Compare models by quality dimensions and error types
- Finalize scalable pipeline architecture and operating procedures
- Define production rollout plan and governance

---

## 14. Out of Scope / Assumptions

**Out of Scope:**
- Web scraping beyond Wikipedia MediaWiki API
- Multi-turn conversation generation
- Answer extraction or validation in PLExp
- Production ML model training in PLExp (pilot is for experimentation)

**Assumptions:**
- Wikipedia API remains publicly accessible (no authentication required)
- External client will handle ML model training
- Questions do not need external sources beyond provided text
- Hebrew language quality sufficient for production use
- Larger project will add dedicated annotation resources

---

## 15. Appendix

### A. Technology Stack
- **Language:** Python 3.9+
- **APIs:** Wikipedia MediaWiki API, Anthropic Claude API, Ollama HTTP API
- **Data Format:** CSV (UTF-8)
- **Version Control:** Git + GitHub
- **LLM Options:** Ollama (free) or Claude 3.5 Haiku (paid)

### B. Configuration Parameters
```python
TOPICS = {20 categories}
ARTICLES_PER_TOPIC = 5
TEXT_VARIANTS = [100, 150, 200, "elsewhere_100", "elsewhere_150", "elsewhere_200"]
BATCH_SIZE = 15 (rows to process per input file)
LLM_ENDPOINT = "http://localhost:11434/api/generate" (Ollama)
QUESTION_PROMPT_TEMPLATE = "Given the following text excerpt..."
```

### C. Key Contacts
- **Project Lead:** Eyal Rosenstein
- **Client:** External ML Pipeline Team
- **GitHub Repository:** https://github.com/Eyal-R-Webiks/PLExp

### D. Reference Documents
- [SESSION_SUMMARY.md](SESSION_SUMMARY.md) — Session notes and next steps
- [PROJECT_DOCUMENTATION.html](PROJECT_DOCUMENTATION.html) — Full code walkthrough
- GitHub Issues — Detailed technical specifications

---

**Document Version History:**
- v1.0 (April 14, 2026) — Initial PRD creation

---

*Last Updated: April 14, 2026*  
*Status: Ready for Review*
