You are an expert in reading comprehension and abstractive QA. Your task is to generate insightful questions based on a provided Hebrew source text.

Target Level: Level 2 (Integration / Multi-hop)
The question must require the reader to integrate or bridge information from at least *two distinct, non-adjacent sentences* in the text to formulate a complete answer.

Constraints:
1. Ask about relationships between distinct facts, processes, comparisons, or cause-and-effect chains spanning multiple separate parts of the text.
2. The answer must be fully assembled from explicit facts in the text — no inference or conclusion beyond what is stated is required.
3. Formulate the question using natural, correct, and diverse Hebrew. Ensure a wide variety of question words are used, and avoid repeatedly relying on the same syntactic structures. Avoid cumbersome and archaic phrasing.
4. The question must flow naturally and organically as a single unified query. Do *not* generate concatenated questions (i.e., do not simply join two separate straightforward questions with an "and").
5. Do not rely on any knowledge external to the document. Any use of outside information, except for the most basic and narrow definition of common "world knowledge", is strictly forbidden. The integration must rely exclusively on facts presented within the text.

Format:
Think step-by-step in English to identify the specific sentences (e.g., "[S2] and [S8]") that must be combined, then generate the Hebrew question. Respond strictly with a JSON array of objects, containing no other text.

JSON Schema:
[
  {
    "reasoning": "<English reasoning identifying the distinct sentences that must be integrated>",
    "question": "<Hebrew integration question>"
  }
]
