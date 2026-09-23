"""
Semantic Router Service
Classifies the user's message into a specific intent category using a fast,
lightweight LLM call. This determines which KB sections get retrieved (RAG).
"""

import re
import httpx
from api.config import GROQ_API_KEY

# Use the faster/lighter model for routing — speed matters here
ROUTER_MODEL = "openai/gpt-oss-20b"

ROUTER_SYSTEM_PROMPT = """\
You are an intent classifier for an Egyptian nursery chatbot.
Classify the user message using intents from this list:

- greeting      → hello, hi, peace greetings, how are you
- pricing       → fees, costs, prices, subscription, discounts, payment, refund, uniform, instapay, cash, one-day / daily hosting price (استضافة يوم)
- schedule      → working hours, days off, holidays, opening/closing times
- location      → address, where are you, map, directions
- curriculum    → subjects, activities, teaching, Jolly Phonics, Montessori, Lego, Quran lessons for the child, certificates, languages, sports
- food          → meals, diet, allergies, menu, snacks, outside food, i care app food
- health        → illness, fever, sick child, injury, medication, safety, first aid
- care          → nap, potty training, daily bag, diapers, first day, transition, separation
- behavior      → special needs, autism, ADHD, speech delay, biting, hitting, behavior modification
- communication → app, i care app, parent meetings, birthday, emergency pickup, cameras, contact
- bus           → school bus, transportation, bus fees, matron, bus availability
- visit         → visit booking, appointment, when to visit, how/when to apply or enroll a child (أقدم لابني)
- jobs          → the sender wants to WORK at the nursery: job vacancies, hiring, "are you hiring Quran teachers?" (محتاجين مدرسين؟ / مش محتاجين مدرسة قرآن؟), sending a CV
- general       → asking for general details/info about the nursery, or anything that does not clearly fit the above

If the message contains several questions, reply with ALL matching intents (max 3), separated by commas.
Reply with ONLY the intent word(s) in lowercase. No explanation.
"""

VALID_INTENTS = {
    "greeting", "pricing", "schedule", "location", "curriculum", "food", "health",
    "care", "behavior", "communication", "visit", "general", "bus", "jobs",
}


async def classify_intent(message: str) -> list[str]:
    """
    Classifies the user message into one or more intent categories.
    Returns ['general'] as a safe fallback on any error.
    """
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": ROUTER_MODEL,
        "messages": [
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": message}
        ],
        "temperature": 0.0,   # deterministic — always same answer for same input
        "max_tokens": 200,
    }

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers=headers
            )
            if response.status_code == 200:
                raw = response.json()["choices"][0]["message"].get("content", "").strip().lower()
                intents = [w for w in re.findall(r"[a-z]+", raw) if w in VALID_INTENTS]
                # Keep order, drop duplicates, max 3 intents
                intents = list(dict.fromkeys(intents))[:3]
                return intents or ["general"]
    except Exception as e:
        print(f"⚠️ Router error (falling back to 'general'): {e}")

    return ["general"]
