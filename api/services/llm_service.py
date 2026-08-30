import random
import httpx
from api.config import GROQ_API_KEY, GROQ_MODEL
from api.prompts import SYSTEM_PROMPT_TEMPLATE
from api.services.redis_service import get_user_history, save_user_history
from api.services.facebook_service import send_fb_message
from api.services.router_service import classify_intent
from api.services.rag_service import retrieve_context
from api.services.reflection_service import reflect_and_validate


# The bot uses this fallback when the requested information is not available
# in the nursery knowledge base. Keep the wording stable so the user always
# knows how to reach the administration.
UNKNOWN_INFO_PHRASES = (
    "معندناش معلومات",
    "معنديش معلومات",
    "مش عندنا معلومات",
    "مش عارف",
    "مش متوفر",
    "لا توجد معلومات",
    "لا أعرف",
    "don't have that information",
    "do not have that information",
    "not available",
    "i don't know",
)


def is_unknown_info_reply(reply: str) -> bool:
    """Detect whether the LLM is saying that the information is unavailable."""
    normalized = reply.strip().lower()
    return any(phrase in normalized for phrase in UNKNOWN_INFO_PHRASES)


UNKNOWN_INFO_REPLY = (
    "بعتذر لحضرتك، المعلومة دي مش متوفرة عندي حالياً. 🙏\n\n"
    "• للتواصل مع إدارة الحضانة مباشرةً، تقدر تتصل على الرقم الموجود في الزر تحت 👇"
)


async def process_and_reply(sender_id: str, message_text: str):
    """
    Main pipeline:
    1. Semantic Routing  → classify user intent
    2. RAG               → retrieve only relevant KB sections
    3. Main LLM + CoT    → generate answer from focused context
    4. Self-Reflection   → validate & correct the answer
    5. Send              → push final reply to Facebook
    """
    if not GROQ_API_KEY:
        print("❌ GROQ_API_KEY missing!")
        await send_fb_message(sender_id, "بعتذر لحضرتك، الخدمة غير متاحة حالياً. يرجى التواصل معنا لاحقاً يا فندم.")
        return

    # ── Intercept "Get Started" postback ─────────────────────────────────────
    clean_msg = message_text.strip().lower()
    if clean_msg in ["get started", "get_started_payload", "بدء الاستخدام"]:
        welcome_text = (
            "أهلاً بحضرتك في حضانة آدمز والبراء 🌟 "
            "انا المساعد الشخصي الذكي، هنا عشان أساعدك تعرف كل تفاصيل الحضانة "
            "من مواعيد العمل، المصاريف، المنهج، ومواعيد الزيارة. "
            "إزاي أقدر أساعدك ؟  "
        )
        buttons = [
            {"content_type": "text", "title": "مواعيد العمل 🕒", "payload": "عايز اعرف مواعيد العمل"},
            {"content_type": "text", "title": "المصاريف 💰",     "payload": "المصاريف كام؟"},
            {"content_type": "text", "title": "مواعيد الزيارة 📅", "payload": "ايه هي مواعيد الزيارة؟"},
        ]
        await send_fb_message(sender_id, welcome_text, quick_replies=buttons)
        messages = get_user_history(sender_id)
        messages.append({"role": "assistant", "content": welcome_text})
        save_user_history(sender_id, messages)
        return

    # ── Step 1: Semantic Routing ──────────────────────────────────────────────
    intent = await classify_intent(message_text)
    print(f"🧭 Intent: {intent}")

    # ── Step 2: RAG — retrieve relevant KB sections ───────────────────────────
    context = retrieve_context(intent)
    print(f"📚 RAG: Retrieved context for intent='{intent}' ({len(context)} chars)")

    # ── Step 3: Build focused system prompt & call main LLM ────────────────────
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context)
    messages = get_user_history(sender_id)

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
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers=headers,
            )

            if response.status_code == 200:
                res_json = response.json()
                choices = res_json.get("choices", [])

                if choices and "message" in choices[0]:
                    bot_reply = choices[0]["message"].get("content", "").strip()

                    if bot_reply:
                        # ── Step 4: Self-Reflection ───────────────────────────
                        bot_reply = await reflect_and_validate(message_text, bot_reply, context)

                        # If the model/reflection says the information is not
                        # available, do not mention the website as a source of
                        # more details. Give the user a direct call button.
                        if is_unknown_info_reply(bot_reply):
                            bot_reply = UNKNOWN_INFO_REPLY
                            await send_fb_message(sender_id, bot_reply, call_admin=True)

                            messages.append({"role": "user", "content": message_text})
                            messages.append({"role": "assistant", "content": bot_reply})
                            save_user_history(sender_id, messages)
                            return

                        # ── Step 5: Send with smart quick-reply buttons ────────
                        all_buttons = [
                            {"content_type": "text", "title": "المنهج والأنشطة 🎨", "payload": "المنهج بتاعكم إيه؟"},
                            {"content_type": "text", "title": "المصاريف 💰",          "payload": "المصاريف كام؟"},
                            {"content_type": "text", "title": "مواعيد الزيارة 📅",    "payload": "ايه هي مواعيد الزيارة؟"},
                            {"content_type": "text", "title": "مواعيد العمل 🕒",       "payload": "عايز اعرف مواعيد العمل"},
                            {"content_type": "text", "title": "سن القبول 👶",          "payload": "بتاخدوا من سن كام؟"},
                            {"content_type": "text", "title": "مكانكم فين؟ 📍",        "payload": "مكان الحضانة فين؟"},
                            {"content_type": "text", "title": "الوجبات 🍽️",           "payload": "نظام الوجبات إيه؟"},
                            {"content_type": "text", "title": "الباص 🚌",              "payload": "الباص متاح؟"},
                        ]
                        # Remove the button matching what the user just asked
                        filtered = [b for b in all_buttons if b["payload"] != message_text.strip()]
                        dynamic_buttons = random.sample(filtered, min(3, len(filtered)))

                        await send_fb_message(sender_id, bot_reply, quick_replies=dynamic_buttons)

                        # Save conversation history
                        messages.append({"role": "user",      "content": message_text})
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
