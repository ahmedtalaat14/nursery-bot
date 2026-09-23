"""
Deterministic rules that run BEFORE the LLM.
Some messages must always get the same fixed reply (job inquiries, complaints
that nobody answers the phone). Handling them here makes them reliable and
independent of how the LLM interprets the conversation history.
"""

import re

ADMIN_PHONE_DISPLAY = "01111299025"
ADMIN_PHONE_E164 = "+201111299025"
BOOKING_URL = "https://www.adams-elbaraa-nursery.com/book-a-visit"
WEBSITE_URL = "https://www.adams-elbaraa-nursery.com"

WEBSITE_PAYLOAD = "WEBSITE_LINK"
WEBSITE_BUTTON_TITLE = "موقع الحضانة 🌐"
WEBSITE_REPLY = (
    "اتفضل لينك موقع حضانة آدمز والبراء 🌐\n\n"
    "تقدر تعرف أكتر عن الحضانة وتحجز معادك من خلاله:\n"
    f"{WEBSITE_URL}"
)

UNKNOWN_INFO_REPLY = (
    "بعتذر لحضرتك، المعلومة دي مش متوفرة عندي حالياً 🙏\n\n"
    "تقدر تتواصل مع إدارة الحضانة مباشرةً على الرقم:\n"
    f"📞 {ADMIN_PHONE_DISPLAY}"
)

PARTIAL_INFO_REPLY = (
    "ولباقي استفسارات حضرتك، تقدر تتواصل مع إدارة الحضانة مباشرةً على الرقم:\n"
    f"📞 {ADMIN_PHONE_DISPLAY}"
)

JOB_INQUIRY_REPLY = (
    "أهلاً بحضرتك 🌷\n\n"
    "بخصوص الوظايف والتقديم للشغل في الحضانة، ياريت تتواصل مع الإدارة مباشرةً على الرقم:\n"
    f"📞 {ADMIN_PHONE_DISPLAY}"
)

NO_ANSWER_REPLY = (
    "معلش يا فندم، بنعتذر جداً 🙏\n\n"
    "• ممكن يكون في ضغط مكالمات حالياً، ياريت تجرب تتصل تاني كمان شوية.\n\n"
    "• واتأكد إن حضرتك بتتصل في مواعيد العمل: من الأحد للخميس، من 8 الصبح لحد 3 العصر.\n\n"
    f"📞 {ADMIN_PHONE_DISPLAY}"
)

# The page also advertises "Leaders Academy" (summer camp, courses for older
# kids). The bot has no academy data, so these questions go to the administration.
ACADEMY_REPLY = (
    "أهلاً بحضرتك 🌟\n\n"
    "بخصوص Leaders Academy (الكامب والكورسات)، ياريت تتواصل مع الإدارة مباشرةً "
    "على الرقم ده (متاح اتصال وواتساب):\n"
    f"📞 {ADMIN_PHONE_DISPLAY}"
)

ACADEMY_NOTE = (
    "• ولو حضرتك بتسأل عن كورسات أو كامب Leaders Academy، "
    f"تقدر تتواصل مع الإدارة على {ADMIN_PHONE_DISPLAY} (اتصال أو واتساب)."
)

_ARABIC_DIACRITICS = re.compile(r"[ً-ْـ]")


def normalize_arabic(text: str) -> str:
    text = _ARABIC_DIACRITICS.sub("", text.lower())
    text = re.sub("[أإآ]", "ا", text)
    return text.replace("ة", "ه").replace("ى", "ي")


_STAFF = r"(مدرس|مدرسه|مدرسين|مدرسات|معلم|معلمه|معلمين|معلمات|مربيه|مربيات|داده|مساعده|مشرفه|موظف|موظفه|موظفين|سكرتير|سكرتيره)"

JOB_PATTERNS = [
    re.compile(r"(محتاجين|عايزين|عاوزين|مطلوب|طالبين|بتطلبوا|بتدوروا (علي|ع))\s*" + _STAFF),
    re.compile(r"(وظيفه|وظايف|وظائف|فرصه شغل|فرص شغل|فرصه عمل|فرص عمل)"),
    re.compile(r"(اشتغل|اشتغال|شغل)\s*(عندكم|معاكم|في الحضانه)"),
    re.compile(r"(محتاج|محتاجه|عايز|عايزه|عاوز|عاوزه|بدور علي|ادور علي)\s*(شغل|وظيفه)"),
    re.compile(r"(ابعت|ابعتلكم|ارسل)\s*(ال)?(سي في|cv)"),
    re.compile(r"\b(job|jobs|vacancy|vacancies|hiring|cv)\b"),
]

NO_ANSWER_PATTERNS = [
    re.compile(r"(محدش|ماحدش|محد|مفيش حد|مافيش حد|ولا حد)\s*(بيرد|يرد|رد|بيردو|بيردوا)"),
    re.compile(r"(مبيردوش|مابيردوش|مبيردش|مابيردش|مش بيردوا|مش بيردو|مش بيرد)"),
    re.compile(r"(الرقم|التليفون|الموبايل|الخط)\s*(مش بيجمع|مقفول|مغلق|مش متاح|مشغول)"),
    re.compile(r"\b(no one|nobody|no body)\s*(is )?(answer|answering|picks|pick)"),
]


ACADEMY_PATTERN = re.compile(
    r"(ليدرز|leaders|اكاديميه|اكاديمي|academy|كامب|camp|summer|كورس|سباحه|كاراتيه|كارتيه"
    r"|باليه|برمجه|كشافه|دراما|يوجا|after ?school|افتر ?سكول)"
)

# Facebook "ice-breaker" questions shown under the page's ads, mapped to the
# Arabic nursery question they almost always mean (the page's human replies
# answered them with nursery info). Keys are normalized with _ice_breaker_key.
ICE_BREAKERS = {
    "how much does this course cost": ("المصاريف كام؟", True),
    "can you tell me more about this educational institution": ("ممكن تفاصيل عن الحضانة؟", False),
    "can you tell me more about": ("ممكن تفاصيل عن الحضانة؟", False),
    "where are you located": ("مكان الحضانة فين؟", False),
    "are you accepting new students": ("بتقبلوا أطفال جديدة؟ وإزاي أقدم لطفلي؟", False),
    "how can i apply": ("إزاي أقدم لطفلي في الحضانة؟", False),
}


def _ice_breaker_key(text: str) -> str:
    return re.sub(r"[^a-z ]", "", text.lower()).strip()


def match_ice_breaker(message: str):
    """Returns (arabic_question, add_academy_note) for a Facebook ice-breaker, else None."""
    return ICE_BREAKERS.get(_ice_breaker_key(message))


def mentions_academy(message: str) -> bool:
    return bool(ACADEMY_PATTERN.search(normalize_arabic(message)))


def is_academy_inquiry(message: str) -> bool:
    """Clearly about the academy and not about the nursery."""
    return mentions_academy(message) and "حضان" not in normalize_arabic(message)


def is_job_inquiry(message: str) -> bool:
    text = normalize_arabic(message)
    return any(p.search(text) for p in JOB_PATTERNS)


def is_no_answer_complaint(message: str) -> bool:
    text = normalize_arabic(message)
    return any(p.search(text) for p in NO_ANSWER_PATTERNS)
