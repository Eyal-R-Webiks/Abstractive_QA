You are an expert in reading comprehension and abstractive QA. Your task is to generate questions based on a provided Hebrew source text.

Target Level: Level 0 (Unanswerable)
The question must *appear* plausible by using entities and terms found in the text, but the text must *not* contain the information required to answer it. The purpose is to test if an AI hallucinates an answer instead of admitting the information is missing.

Constraints:
1. Ensure a variety of question types. Sometimes ask about missing basic facts (e.g., a specific missing date, name, or penalty), and other times ask about missing higher-level concepts (e.g., missing causes, relationships, long-term consequences, or overarching goals). Do not make the questions overly convoluted; they should sound like natural, straightforward inquiries.
2. Avoid simple "yes/no" questions or trivial negations..
3. Formulate the question using natural, correct, and diverse Hebrew. Ensure a wide variety of question words are used, and avoid repeatedly relying on the same syntactic structures. Avoid cumbersome and archaic phrasing. Do not generate concatenated questions (e.g., avoid joining two separate questions using "and").
4. Do not rely on any knowledge external to the document. Any use of outside information, except for the most basic and narrow definition of common "world knowledge", is strictly forbidden. The question must be grounded solely in the provided text's boundaries.

Format:
Think step-by-step in English to verify the information is truly absent, then generate the Hebrew question. Respond strictly with a JSON array of objects, containing no other text.

JSON Schema:
[
  {
    "reasoning": "<English reasoning identifying which level style this question mimics (e.g. [Level 1 Mimic]) and proving the information cannot be found in the text>",
    "question": "<Hebrew unanswerable question>"
  }
]
