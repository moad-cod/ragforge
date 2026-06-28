from groq import Groq
from app.core.config import settings
import json

client = Groq(api_key=settings.GROQ_API_KEY)

PROPOSITION_PROMPT = """Decompose the following text into simple, atomic propositions.
Each proposition must:
- Be a single self-contained fact
- Be understandable without context
- Be as short as possible

Return ONLY a JSON array of strings. No explanation.

Example output:
["FloodScan data covers 1998 to 2022.", "WorldPop 2020 data was used.", "Somalia has two flood seasons."]

Text to decompose:
{text}"""

def chunk(text: str) -> list[str]:
    # Split into paragraphs first, then decompose each
    paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 50]
    all_propositions = []

    for para in paragraphs:
        try:
            response = client.chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=[{
                    "role": "user",
                    "content": PROPOSITION_PROMPT.format(text=para)
                }],
                max_tokens=1024,
                temperature=0,
            )
            raw = response.choices[0].message.content.strip()
            propositions = json.loads(raw)
            all_propositions.extend(propositions)
        except Exception as e:
            # Fallback: keep the paragraph as-is
            print(f"Proposition extraction failed: {e}")
            all_propositions.append(para)

    return all_propositions