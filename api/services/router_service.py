"""
Semantic Router Service
Classifies the user's message into a specific intent category using a fast,
lightweight LLM call. This determines which KB sections get retrieved (RAG).
"""

import httpx
from api.config import GROQ_API_KEY

# Use the faster/lighter model for routing — speed matters here
ROUTER_MODEL = "openai/gpt-oss-20b"

ROUTER_SYSTEM_PROMPT = """\
You are an intent classifier for an Egyptian nursery chatbot.
Classify the user message into EXACTLY ONE intent from this list:

- greeting      → hello, hi, peace greetings, how are you
- pricing       → fees, costs, prices, discounts, payment, refund, uniform, instapay, cash
- schedule      → working hours, days off, holidays, opening/closing times
- location      → address, where are you, map, directions
- curriculum    → subjects, activities, teaching, Jolly Phonics, Montessori, Lego, Quran, certificates, languages, sports
- food          → meals, diet, allergies, menu, snacks, outside food, i care app food
- health        → illness, fever, sick child, injury, medication, safety, first aid
- care          → nap, potty training, daily bag, diapers, first day, transition, separation
- behavior      → special needs, autism, ADHD, speech delay, biting, hitting, behavior modification
- communication → app, i care app, parent meetings, birthday, emergency pickup, cameras, contact
- bus          → school bus, transportation, bus fees, matron, bus availability
- visit         → visit booking, appointment, when to visit, schedule a visit
- general       → anything that does not clearly fit the above

Reply with ONLY the intent word in lowercase. No explanation. No punctuation.
"""

VALID_INTENTS = {
    "greeting", "pricing", "schedule", "location", "curriculum",
    "food", "health", "care", "behavior", "communication", "visit", "general", "bus"
}


async def classify_intent(message: str) -> str:
    """
    Classifies the user message into an intent category.
    Returns 'general' as a safe fallback on any error.
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
                # Extract only the first word in case model adds extra text
                intent = raw.split()[0] if raw.split() else "general"
                result = intent if intent in VALID_INTENTS else "general"
                return result
    except Exception as e:
        print(f"⚠️ Router error (falling back to 'general'): {e}")

    return "general"
