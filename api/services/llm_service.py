import asyncio
import random
import httpx
from api.config import GROQ_API_KEY, GROQ_MODEL
from api.prompts import SYSTEM_PROMPT_TEMPLATE
from api.services.redis_service import get_user_history, save_user_history
from api.services.facebook_service import send_fb_message
from api.services.router_service import classify_intent
from api.services.rag_service import retrieve_context
from api.services.reflection_service import reflect_and_validate
from api.services.quick_rules import (
    UNKNOWN_INFO_REPLY, PARTIAL_INFO_REPLY, JOB_INQUIRY_REPLY, NO_ANSWER_REPLY,
    ACADEMY_REPLY, ACADEMY_NOTE,
    is_job_inquiry, is_no_answer_complaint, is_academy_inquiry, match_ice_breaker,
    mentions_academy, WEBSITE_PAYLOAD, WEBSITE_BUTTON_TITLE, WEBSITE_REPLY,
)

WEBSITE_BUTTON = {"content_type": "text", "title": WEBSITE_BUTTON_TITLE, "payload": WEBSITE_PAYLOAD}

TOPIC_BUTTONS = [
    {"content_type": "text", "title": "المنهج والأنشطة 🎨", "payload": "المنهج بتاعكم إيه؟"},
    {"content_type": "text", "title": "المصاريف 💰", "payload": "المصاريف كام؟"},
    {"content_type": "text", "title": "مواعيد الزيارة 📅", "payload": "ايه هي مواعيد الزيارة؟"},
    {"content_type": "text", "title": "مواعيد العمل 🕒", "payload": "عايز اعرف مواعيد العمل"},
    {"content_type": "text", "title": "سن القبول 👶", "payload": "بتاخدوا من سن كام؟"},
    {"content_type": "text", "title": "مكانكم فين؟ 📍", "payload": "مكان الحضانة فين؟"},
    {"content_type": "text", "title": "الوجبات 🍽️", "payload": "نظام الوجبات إيه؟"},
    {"content_type": "text", "title": "الباص 🚌", "payload": "الباص متاح؟"},
]


def build_quick_replies(current_message: str, include_website: bool = True) -> list:
    """The website button is always shown first, plus 3 random topic buttons."""
    others = [b for b in TOPIC_BUTTONS if b["payload"] != current_message.strip()]
    buttons = random.sample(others, min(3, len(others)))
    return [WEBSITE_BUTTON] + buttons if include_website else buttons


def is_website_request(message: str) -> bool:
    return message.strip() in (WEBSITE_PAYLOAD, WEBSITE_BUTTON_TITLE)

CONTACT_ADMIN_MARKER = "[[CONTACT_ADMIN]]"
JOB_INQUIRY_MARKER = "[[JOB_INQUIRY]]"
NO_ANSWER_MARKER = "[[NO_ANSWER]]"
ACADEMY_MARKER = "[[ACADEMY]]"

# Only phrases that clearly mean "I don't have this info". Generic words like
# "مش متوفر" are NOT listed: they appear in valid answers too
# (e.g. "مفيش استضافة يومية", "الفرنساوي مش متوفر").
UNKNOWN_INFO_PHRASES = (
    "معندناش معلومات", "معنديش معلومات", "مش عندنا معلومات", "مش عندي معلومات",
    "المعلومة دي مش متوفرة", "المعلومه دي مش متوفره", "لا توجد معلومات",
    "don't have that information", "do not have that information", "i don't know",
)


def is_unknown_info_reply(reply: str) -> bool:
    normalized = reply.strip().lower()
    # A long reply with real content is never treated as "unknown".
    if len(normalized) > 200:
        return False
    return any(phrase in normalized for phrase in UNKNOWN_INFO_PHRASES)


def strip_markers(reply: str) -> str:
    return reply.replace(CONTACT_ADMIN_MARKER, "").replace(ACADEMY_MARKER, "").strip()


async def send_and_save(sender_id: str, messages: list, user_text: str, reply: str, **send_kwargs):
    await send_fb_message(sender_id, reply, **send_kwargs)
    messages.append({"role": "user", "content": user_text})
    messages.append({"role": "assistant", "content": reply})
    save_user_history(sender_id, messages)


async def process_and_reply(sender_id: str, message_text: str):
    """
    Main pipeline:
    1. Semantic Routing → classify user intent
    2. RAG → retrieve relevant KB sections
    3. Main LLM → generate grounded answer
    4. Self-Reflection → validate the answer
    5. Send → push final reply to Facebook
    """
    if not GROQ_API_KEY:
        print("❌ GROQ_API_KEY missing!")
        await send_fb_message(sender_id, "بعتذر لحضرتك، الخدمة غير متاحة حالياً. يرجى التواصل معنا لاحقاً يا فندم.")
        return

    clean_msg = message_text.strip().lower()
    if clean_msg in ["get started", "get_started_payload", "بدء الاستخدام"]:
        welcome_text = (
            "أهلاً بحضرتك في حضانة آدمز والبراء 🌟 "
            "انا المساعد الشخصي الذكي، هنا عشان أساعدك تعرف كل تفاصيل الحضانة "
            "من مواعيد العمل، المصاريف، المنهج، ومواعيد الزيارة. "
            "إزاي أقدر أساعدك ؟  "
        )
        buttons = [
            WEBSITE_BUTTON,
            {"content_type": "text", "title": "مواعيد العمل 🕒", "payload": "عايز اعرف مواعيد العمل"},
            {"content_type": "text", "title": "المصاريف 💰", "payload": "المصاريف كام؟"},
            {"content_type": "text", "title": "مواعيد الزيارة 📅", "payload": "ايه هي مواعيد الزيارة؟"},
        ]
        await send_fb_message(sender_id, welcome_text, quick_replies=buttons)
        messages = get_user_history(sender_id)
        messages.append({"role": "assistant", "content": welcome_text})
        save_user_history(sender_id, messages)
        return

    messages = get_user_history(sender_id)

    # "Nursery website" button: send the link directly, no LLM call.
    if is_website_request(message_text):
        print("🌐 Rule: website button")
        await send_fb_message(
            sender_id, WEBSITE_REPLY,
            quick_replies=build_quick_replies(message_text, include_website=False),
        )
        messages.append({"role": "user", "content": WEBSITE_BUTTON_TITLE})
        messages.append({"role": "assistant", "content": WEBSITE_REPLY})
        save_user_history(sender_id, messages)
        return

    # Fixed replies that must not depend on the LLM's interpretation.
    if is_no_answer_complaint(message_text):
        print("☎️ Rule: no-answer complaint")
        await send_and_save(sender_id, messages, message_text, NO_ANSWER_REPLY, call_admin=True)
        return
    if is_job_inquiry(message_text):
        print("💼 Rule: job inquiry")
        await send_and_save(sender_id, messages, message_text, JOB_INQUIRY_REPLY, call_admin=True)
        return
    if is_academy_inquiry(message_text):
        print("🎓 Rule: Leaders Academy inquiry")
        await send_and_save(sender_id, messages, message_text, ACADEMY_REPLY, call_admin=True)
        return

    # Facebook ad ice-breakers are English, but the customers are Egyptian:
    # answer them as the Arabic nursery question they mean.
    add_academy_note = False
    ice_breaker = match_ice_breaker(message_text)
    if ice_breaker:
        message_text, add_academy_note = ice_breaker
        print(f"🧊 Ice-breaker → {message_text}")

    intents = await classify_intent(message_text)
    print(f"🧭 Intents: {intents}")

    if intents == ["jobs"]:
        await send_and_save(sender_id, messages, message_text, JOB_INQUIRY_REPLY, call_admin=True)
        return

    context = retrieve_context(intents)
    print(f"📚 RAG: Retrieved context for intents={intents} ({len(context)} chars)")

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context)

    groq_messages = [{"role": "system", "content": system_prompt}]
    groq_messages.extend(messages)
    groq_messages.append({"role": "user", "content": message_text})

    payload = {
        "model": GROQ_MODEL,
        "messages": groq_messages,
        "temperature": 0.4,
        "max_tokens": 1500,
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            for attempt in range(3):
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                if response.status_code != 429 or attempt == 2:
                    break
                # Groq per-minute rate limit: wait as instructed, then retry.
                wait = min(float(response.headers.get("retry-after", 10)), 20.0)
                print(f"⏳ Groq rate limit, retrying in {wait}s")
                await asyncio.sleep(wait)

            if response.status_code == 200:
                res_json = response.json()
                choices = res_json.get("choices", [])

                if choices and "message" in choices[0]:
                    bot_reply = choices[0]["message"].get("content", "").strip()

                    if bot_reply:
                        # IMPORTANT: handle markers BEFORE reflection, so the
                        # reflection model cannot turn them into invented answers.
                        if JOB_INQUIRY_MARKER in bot_reply:
                            await send_and_save(sender_id, messages, message_text, JOB_INQUIRY_REPLY, call_admin=True)
                            return
                        if NO_ANSWER_MARKER in bot_reply:
                            await send_and_save(sender_id, messages, message_text, NO_ANSWER_REPLY, call_admin=True)
                            return

                        # The model may answer part of a multi-question message and
                        # add a marker for the rest (unknown info / academy).
                        if ACADEMY_MARKER in bot_reply:
                            follow_up = ACADEMY_REPLY
                        elif CONTACT_ADMIN_MARKER in bot_reply:
                            follow_up = PARTIAL_INFO_REPLY
                        else:
                            follow_up = None
                        # The bot has no academy data: if the customer mentioned it,
                        # always point them to the administration for that part.
                        if mentions_academy(message_text):
                            follow_up = ACADEMY_REPLY
                        # Ice-breakers are fully answerable nursery questions.
                        elif ice_breaker and follow_up == PARTIAL_INFO_REPLY:
                            follow_up = None
                        bot_reply = strip_markers(bot_reply)

                        if not bot_reply or is_unknown_info_reply(bot_reply):
                            reply = ACADEMY_REPLY if follow_up == ACADEMY_REPLY else UNKNOWN_INFO_REPLY
                            await send_and_save(sender_id, messages, message_text, reply, call_admin=True)
                            return

                        bot_reply = await reflect_and_validate(message_text, bot_reply, context)
                        bot_reply = strip_markers(bot_reply)

                        if is_unknown_info_reply(bot_reply):
                            await send_and_save(sender_id, messages, message_text, UNKNOWN_INFO_REPLY, call_admin=True)
                            return

                        if add_academy_note and follow_up != ACADEMY_REPLY:
                            bot_reply = f"{bot_reply}\n\n{ACADEMY_NOTE}"

                        if follow_up:
                            # Send the known part, then the admin contact + call button.
                            await send_fb_message(sender_id, bot_reply)
                            await send_fb_message(sender_id, follow_up, call_admin=True)
                            messages.append({"role": "user", "content": message_text})
                            messages.append({"role": "assistant", "content": f"{bot_reply}\n\n{follow_up}"})
                            save_user_history(sender_id, messages)
                            return

                        await send_fb_message(sender_id, bot_reply, quick_replies=build_quick_replies(message_text))

                        messages.append({"role": "user", "content": message_text})
                        messages.append({"role": "assistant", "content": bot_reply})
                        save_user_history(sender_id, messages)

                    else:
                        print("❌ Empty reply from Groq API")
                        await send_fb_message(sender_id, "أهلاً بحضرتك يا فندم! إزاي أقدر أساعدك النهاردة بالحضانة؟")
                else:
                    print("❌ Malformed response from Groq API")
                    await send_fb_message(sender_id, "أهلاً بحضرتك يا فندم! إزاي أقدر أساعدك النهاردة بالحضانة؟")
            else:
                print(f"❌ Groq Error ({response.status_code}): {response.text}")
                await send_fb_message(sender_id, "بعتذر لحضرتك جداً، حصل عطل بسيط. تقدر تسألني تاني أو تتواصل مع الإدارة يا فندم.")

        except Exception as e:
            print(f"❌ Exception: {e}")
            await send_fb_message(sender_id, "بعتذر لحضرتك جداً، حدث خطأ مؤقت. تقدر تسألني تاني يا فندم.")
