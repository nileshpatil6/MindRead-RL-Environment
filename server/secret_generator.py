import json
import os
import uuid
from groq import Groq

GENERATION_PROMPT = """\
Generate a realistic workplace secret for a professional in a {domain} company.

Category: {category}
Difficulty: {difficulty} (0.0 = very easy to infer, 1.0 = very hard)

Output ONLY valid JSON with this exact schema:
{{
  "content": "<the actual hidden mental state or fact — 1-3 sentences, realistic and specific>",
  "persona": "<job title and company type — e.g. 'Senior product manager at a B2B SaaS company'>",
  "context": "<shared context given to the Detective — 2-3 sentences, includes red herrings but NOT the secret>",
  "red_herrings": ["<plausible but irrelevant fact 1>", "<plausible but irrelevant fact 2>"],
  "hint_keywords": ["<keyword1>", "<keyword2>", "<keyword3>", "<keyword4>"]
}}

Rules:
- The secret must be plausible and professional
- The persona must NOT give away the secret (no obvious hints in job title)
- The context must include 2 real red herrings — facts that seem relevant but aren't
- hint_keywords are words that should appear in a CORRECT hypothesis
- difficulty {difficulty}: {'make the secret require precise inference' if {difficulty} > 0.5 else 'make the secret inferable with 3-4 good questions'}
- Do NOT include the word "secret" or "hidden" in the context
- Output ONLY the JSON object, no markdown, no explanation\
"""

CATEGORY_TASK_MAP = {
    "factual": "factual_easy",
    "belief": "belief_inference",
    "goal": "goal_inference",
    "second_order": "second_order",
}


def generate_secret(
    category: str,
    difficulty: float,
    domain: str = "tech startup",
) -> dict:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set")

    client = Groq(api_key=api_key)
    prompt = GENERATION_PROMPT.format(
        category=category,
        difficulty=difficulty,
        domain=domain,
    )

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=400,
    )

    raw = response.choices[0].message.content.strip()

    # strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    data = json.loads(raw)

    task_id = CATEGORY_TASK_MAP.get(category, "factual_easy")
    if category == "factual" and difficulty > 0.5:
        task_id = "factual_hard"

    secret_id = f"gen_{uuid.uuid4().hex[:8]}"

    return {
        "id": secret_id,
        "task_id": task_id,
        "content": data["content"],
        "persona": data["persona"],
        "context": data["context"],
        "difficulty": difficulty,
        "category": category,
        "red_herrings": data.get("red_herrings", []),
        "hint_keywords": data.get("hint_keywords", []),
    }
