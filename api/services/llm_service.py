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

    # 1. Safely load chat history
    messages = get_user_history(sender_id)

    groq_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    groq_messages.extend(messages)
    groq_messages.append({"role": "user", "content": message_text})

    payload = {
        "model": GROQ_MODEL,
        "messages": groq_messages,
        "temperature": 0.3,
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
                        await send_fb_message(sender_id, bot_reply)

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
