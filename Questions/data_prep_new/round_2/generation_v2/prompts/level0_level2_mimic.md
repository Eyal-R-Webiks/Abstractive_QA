You are an expert in Hebrew reading-comprehension question writing.

Target Level: Level 0 (Unanswerable)
Create exactly one plausible question that sounds answerable from the passage, but the required answer is truly absent from the text.

Mimic target for this prompt: Level 2 style only.
- The question may connect two details or imply a practical linkage between parts of the passage.
- Keep it concise and natural; avoid heavy framing.
- It should feel like light synthesis style, not direct retrieval.

Critical distinction:
- STYLE should feel Level 2.
- LOGIC must remain Level 0: the needed answer is missing from the text.

Hard constraints:
1. Keep Hebrew natural and concise. Sound like a real reader.
2. Do not write thesis-like or inflated language.
3. Do not stack premises (avoid openings like "על פי...", "לאור...", "בהתאם...").
4. Do not add redundant relative clauses (especially ", אשר ..." when unnecessary).
5. Do not create a yes/no question.
6. Do not rely on external knowledge.
7. Do not ask for a detail explicitly present in the text.

Output format:
Return ONLY a JSON array with exactly one object.

JSON schema:
[
  {
    "reasoning": "English: explain why this is Level-0-unanswerable and why the wording mimics Level 2 style only.",
    "question": "Hebrew question",
    "answer_spans": [],
    "expected_answer_spans_level0": ["Exact span string copied from the input text where the missing answer would be expected"]
  }
]
