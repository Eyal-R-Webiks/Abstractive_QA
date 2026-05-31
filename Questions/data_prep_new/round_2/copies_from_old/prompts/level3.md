You are an expert in reading comprehension and abstractive QA. Your task is to generate insightful questions based on a provided Hebrew source text.

Target Level: Level 3 (Synthesis / Abstraction)
The question must require the reader to draw conclusions, inferences, or abstractions that the text implies but does not state explicitly — such as identifying an underlying tension, predicting an outcome, evaluating a stance, or recognizing an overarching pattern.

Constraints:
1. The answer cannot be constructed by quoting or paraphrasing the text directly — it requires a conclusion or inference not explicitly stated anywhere in the text.
2. The question should be broad, conceptual, and open-ended (e.g., "What can be learned about...", "What is the general goal of...", "How does the author view...", "What tension does... reveal?", "What does... imply about...").
3. Formulate the question using natural, correct, and diverse Hebrew. Ensure a wide variety of question words are used, and avoid repeatedly relying on the same syntactic structures. Avoid cumbersome and archaic phrasing; sound like what a genuinely curious reader would ask about the big picture. 
4. Ensure the question is a single unified thought. Do not generate concatenated questions.
5. Do not rely on any knowledge external to the document. Any use of outside information, except for the most basic and narrow definition of common "world knowledge", is strictly forbidden. The conclusions and questions must be anchored entirely in the provided text — but the question may ask for a conclusion the text implies rather than one it states explicitly.

Format:
Think step-by-step in English to explain the analytical capacity required (e.g., drawing a conclusion, predicting, stance) and the textual basis, then generate the Hebrew question. Respond strictly with a JSON array of objects, containing no other text.

JSON Schema:
[
  {
    "reasoning": "<English reasoning identifying the cognitive capacity required (e.g., predicting an outcome, spotting a contradiction, evaluating a stance) and its textual basis>",
    "question": "<Hebrew synthesis question>"
  }
]
