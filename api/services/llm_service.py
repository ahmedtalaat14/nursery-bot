import random
import httpx
from api.config import GROQ_API_KEY, GROQ_MODEL
from api.prompts import SYSTEM_PROMPT
from api.services.redis_service import get_user_history, save_user_history
from api.services.facebook_service import send_fb_message

async def process_and_reply(sender_id: str, message_text: str):
    """Processes user query through Groq LLM API and replies on Facebook."""
    if not GROQ_API_KEY:
        print("❌ GROQ_API_KEY missing!")
        await send_fb_message(sender_id, "بعتذر لحضرتك، الخدمة غير متاحة حالياً. يرجى التواصل معنا لاحقاً يا فندم.")
        return

    # 🌟 اعتراض ضغطة Get Started وإرسال الأزرار السريعة مباشرة
    if message_text.strip().lower() in ["get started", "get_started_payload", "بدء الاستخدام"]:
        welcome_text = "وعليكم السلام ورحمة الله وبركاته! أهلاً بحضرتك في حضانة آدمز والبراء 🌟 إزاي أقدر أساعدك النهاردة؟"
        
        buttons = [
            {"content_type": "text", "title": "مواعيد العمل 🕒", "payload": "عايز اعرف مواعيد العمل"},
            {"content_type": "text", "title": "المصاريف 💰", "payload": "المصاريف كام؟"},
            {"content_type": "text", "title": "مواعيد الزيارة 📅", "payload": "ايه هي مواعيد الزيارة؟"}
        ]
        
        await send_fb_message(sender_id, welcome_text, quick_replies=buttons)
        
        messages = get_user_history(sender_id)
        messages.append({"role": "assistant", "content": welcome_text})
        save_user_history(sender_id, messages)
        return

    # 1. Safely load chat history
    messages = get_user_history(sender_id)

    groq_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    groq_messages.extend(messages)
    groq_messages.append({"role": "user", "content": message_text})

    payload = {
        "model": GROQ_MODEL,
        "messages": groq_messages,
        "temperature": 0.1,  # 🌟 تم التقليل لمنع التأليف تماماً
        "max_tokens": 500
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers=headers
            )
            if response.status_code == 200:
                res_json = response.json()
                choices = res_json.get('choices', [])
                if choices and 'message' in choices[0]:
                    bot_reply = choices[0]['message'].get('content', '')
                    if bot_reply and bot_reply.strip():
                        bot_reply = bot_reply.strip()
                        
                        # 🌟 بنك الأسئلة الشاملة واستبعاد السؤال الحالي
                        all_suggested_buttons = [
                            {"content_type": "text", "title": "المنهج والأنشطة 🎨", "payload": "المنهج بتاعكم إيه؟"},
                            {"content_type": "text", "title": "المصاريف 💰", "payload": "المصاريف كام؟"},
                            {"content_type": "text", "title": "مواعيد الزيارة 📅", "payload": "ايه هي مواعيد الزيارة؟"},
                            {"content_type": "text", "title": "مواعيد العمل 🕒", "payload": "عايز اعرف مواعيد العمل"},
                            {"content_type": "text", "title": "سن القبول 👶", "payload": "بتاخدوا من سن كام؟"},
                            {"content_type": "text", "title": "مكانكم فين؟ 📍", "payload": "مكان الحضانة فين؟"}
                        ]

                        filtered_buttons = [
                            btn for btn in all_suggested_buttons 
                            if btn["payload"] != message_text.strip()
                        ]

                        dynamic_buttons = random.sample(filtered_buttons, 3)

                        # إرسال رد الموديل ومرفق معاه الأزرار المتغيرة
                        await send_fb_message(sender_id, bot_reply, quick_replies=dynamic_buttons)

                        # Update conversation history
                        messages.append({"role": "user", "content": message_text})
                        messages.append({"role": "assistant", "content": bot_reply})
                        save_user_history(sender_id, messages)
                    else:
                        print("❌ Empty reply received from Groq API")
                        await send_fb_message(sender_id, "أهلاً بحضرتك يا فندم! إزاي أقدر أساعدك النهاردة بالحضانة؟")
                else:
                    print("❌ Malformed response choices from Groq API")
                    await send_fb_message(sender_id, "أهلاً بحضرتك يا فندم! إزاي أقدر أساعدك النهاردة بالحضانة؟")
            else:
                print(f"❌ Groq Error ({response.status_code}): {response.text}")
                await send_fb_message(sender_id, "بعتذر لحضرتك جداً، حصل عطل بسيط. تقدر تسألني تاني أو تتواصل مع الإدارة يا فندم.")
        except Exception as e:
            print(f"❌ Exception processing Groq: {e}")
            await send_fb_message(sender_id, "بعتذر لحضرتك جداً، حدث خطأ مؤقت. تقدر تسألني تاني يا فندم.")