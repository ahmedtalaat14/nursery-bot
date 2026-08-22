"""
RAG Service — Retrieval Augmented Generation
Splits the knowledge base into sections and retrieves only what's relevant
to the user's detected intent. This keeps prompts focused and reduces noise.
"""

# ─── Knowledge Base Split into Sections ──────────────────────────────────────

KNOWLEDGE_BASE: dict[str, str] = {
    "general": """
[General Info & Working Hours]
- Experience & Age: 16 years experience. Accepts kids from 1 year and 10 months up to 5 years.
- Teachers: Highly qualified and trained staff.
- Garden & Play Area: 200 square meters garden and play area.
- Cameras: 24/7 CCTV coverage for safety (internal access only, no online access).
- Working Days: Sunday to Thursday ONLY. (Friday & Saturday are off).
- Working Hours: 8 AM to 4 PM.
- Holidays: Closed on public holidays. 1 week off for Eid Al-Fitr and 1 week off for Eid Al-Adha.
- Location: Obour City. Map: https://maps.app.goo.gl/BCg3zuNPEEfaXjQp8 | Website: https://adams-rouge.vercel.app
- Summer Camp: Available for older kids (5 to 12 years old).
""",

    "pricing": """
[Financials & Fees]
- Monthly Subscriptions: Half Day (8 AM-12 PM) = 4500 EGP. Full Day (8 AM-4 PM) = 6000 EGP.
- Discounts: 10% for City Club members. 5% sibling discount.
- Payment Methods: Cash or InstaPay.
- Late Fees: After 4 PM → 50 EGP for 1 hour delay, 150 EGP for 2 hours.
- Absence: No refund or compensation for days missed.
- Refund Policy: If child withdraws early → app fee (300 EGP) + uniform cost + attended days are deducted, rest is refunded.
- Uniform: Mandatory. Bought directly from the nursery.
""",

    "food": """
[Food & Meals Policy]
- Meals: 3 healthy meals provided daily. Monthly menu posted on "i care" app.
- Outside Food: NOT ALLOWED to bring full meals from home. Only healthy snacks (vegetables/fruits). No chips or chocolates.
- Allergies: Parent notifies management → sends replacement meal ONLY on the specific day that food appears in the menu.
""",

    "curriculum": """
[Education & Activities]
- Curriculum: Certified "Jolly Phonics" international program + Custom Character Building curriculum + English conversation.
- Daily Activities: Quran memorization, Montessori, Gymnastics, Lego.
- Screens: ZERO screen time.
- Languages: English only. No French or German.
- Sports Outfit: Not needed; uniform is sufficient.
- School Interviews: Kids prepared for National & International school interviews.
- Certificates: NO official graduation certificate provided.
""",

    "health": """
[Health, Safety & Emergencies]
- Illness: Sick kids with fever/contagious illness are STRICTLY forbidden from entering. Medical report required to return.
- Medications: Given with parent's prior written instructions only.
- Injuries: Immediate transfer to nearest hospital + immediate parent notification.
""",

    "care": """
[Daily Care & Routine]
- Nap Time: Only for 2-year-olds, supervised by class teachers.
- Daily Bag: Diapers, full change of clothes, water flask.
- Potty Training: Coordinated step-by-step with management.
- First Day Transition: "Safe separation" program over one week, coordinated with parents.
""",

    "behavior": """
[Behavior & Special Needs]
- Special Needs: Does NOT accept Autism, ADHD, or Speech delay cases.
- Behavior Issues: A behavior modification program is set with parents (e.g., biting, hitting).
""",

    "communication": """
[Communication, App & Bus]
- App (i care): Used for daily reports and monthly evaluations.
- Visit Booking: Available Sunday, Monday, Thursday — 10 AM to 1 PM. Each visit is 45 minutes. Book via: https://adams-rouge.vercel.app
- Parent Meetings: With MANAGEMENT ONLY. Direct contact with teachers is strictly forbidden.
- Birthdays: NOT allowed to celebrate or distribute sweets.
- Bus: Covers all Obour City. Starts from 1000 EGP/month (paid separately). Matron on board, direct contact provided.
- Emergency Pickup: Parent MUST notify management and send recipient's National ID photo via WhatsApp in advance.
""",
}

# ─── Intent → Relevant Sections Mapping ──────────────────────────────────────

INTENT_TO_SECTIONS: dict[str, list[str]] = {
    "greeting":      ["general"],
    "pricing":       ["pricing"],
    "schedule":      ["general"],
    "location":      ["general"],
    "curriculum":    ["curriculum"],
    "food":          ["food"],
    "health":        ["health"],
    "care":          ["care"],
    "behavior":      ["behavior"],
    "communication": ["communication"],
    "visit":         ["communication"],
    "bus":           ["communication", "pricing"],
    "general":       list(KNOWLEDGE_BASE.keys()),  # Full KB for ambiguous queries
}


def retrieve_context(intent: str) -> str:
    """
    Retrieve relevant KB sections based on the classified intent.
    Falls back to the full KB for unknown intents.
    """
    sections = INTENT_TO_SECTIONS.get(intent, list(KNOWLEDGE_BASE.keys()))
    context_parts = [KNOWLEDGE_BASE[s] for s in sections if s in KNOWLEDGE_BASE]
    return "\n".join(context_parts).strip()
