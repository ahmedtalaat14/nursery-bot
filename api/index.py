import json
import os
import httpx
from fastapi import FastAPI, Request, Response, Query, BackgroundTasks
from dotenv import load_dotenv
from upstash_redis import Redis

from api.privacy import router as privacy_router

load_dotenv()

app = FastAPI(title="Adam's & Elbaraa Nursery Bot", version="1.0.0")

# Register Privacy Policy Router
app.include_router(privacy_router)

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "nursery123")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
UPSTASH_REDIS_REST_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "")
UPSTASH_REDIS_REST_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")

# Safely initialize Redis client
redis_client = None
if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
    try:
        redis_client = Redis(url=UPSTASH_REDIS_REST_URL, token=UPSTASH_REDIS_REST_TOKEN)
    except Exception as e:
        print(f"⚠️ Redis initialization error: {e}")


def get_user_history(sender_id: str) -> list:
    """Safely retrieves conversation history from Redis."""
    if not redis_client:
        return []
    try:
        history_key = f"chat_{sender_id}"
        user_history_str = redis_client.get(history_key)
        if user_history_str:
            data = json.loads(user_history_str)
            if isinstance(data, list):
                return data
    except Exception as e:
        print(f"⚠️ Redis get error for {sender_id}: {e}")
    return []


def save_user_history(sender_id: str, messages: list):
    """Safely saves recent conversation history (last 6 messages) to Redis with 24h TTL."""
    if not redis_client:
        return
    try:
        history_key = f"chat_{sender_id}"
        recent_messages = messages[-6:]
        redis_client.set(history_key, json.dumps(recent_messages), ex=86400)
    except Exception as e:
        print(f"⚠️ Redis set error for {sender_id}: {e}")


async def send_fb_message(sender_id: str, text: str, quick_replies: list = None):
    """Sends a message back to user via Facebook Messenger Graph API."""
    if not text:
        return

    if not PAGE_ACCESS_TOKEN:
        print("❌ PAGE_ACCESS_TOKEN is missing!")
        return

    fb_url = f"https://graph.facebook.com/v21.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    max_length = 2000
    chunks = [text[i:i + max_length] for i in range(0, len(text), max_length)]

    async with httpx.AsyncClient(timeout=10.0) as client:
        for i, chunk in enumerate(chunks):
            fb_payload = {
                "recipient": {"id": sender_id},
                "message": {"text": chunk}
            }
            
            # إضافة الأزرار لآخر جزء من الرسالة فقط
            if quick_replies and i == len(chunks) - 1:
                fb_payload["message"]["quick_replies"] = quick_replies

            try:
                res = await client.post(fb_url, json=fb_payload)
                if res.status_code != 200:
                    print(f"❌ FB Error ({res.status_code}): {res.text}")
                else:
                    print(f"✅ FB message sent to {sender_id}")
            except Exception as e:
                print(f"❌ Exception sending FB message: {e}")


async def process_and_reply(sender_id: str, message_text: str):
    """Processes user query through Groq LLM API and replies on Facebook."""
    if not GROQ_API_KEY:
        print("❌ GROQ_API_KEY missing!")
        await send_fb_message(sender_id, "بعتذر لحضرتك، الخدمة غير متاحة حالياً. يرجى التواصل معنا لاحقاً يا فندم.")
        return

    # 🌟 اعتراض ضغطة Get Started وإرسال الأزرار السريعة مباشرة
    if message_text.strip().lower() in ["get started", "get_started_payload", "بدء الاستخدام"]:
        welcome_text = "وعليكم السلام ورحمة الله وبركاته! أهلاً بحضرتك في حضانة آدمز والبراء 🌟 إزاي أقدر أساعدك النهاردة؟"
        
        # الأزرار السريعة (لاحظ إن العناوين لازم تكون قصيرة - أقصى حد 20 حرف)
        buttons = [
            {"content_type": "text", "title": "مواعيد العمل 🕒", "payload": "عايز اعرف مواعيد العمل"},
            {"content_type": "text", "title": "المصاريف 💰", "payload": "المصاريف كام؟"},
            {"content_type": "text", "title": "مواعيد الزيارة 📅", "payload": "ايه هي مواعيد الزيارة؟"}
        ]
        
        await send_fb_message(sender_id, welcome_text, quick_replies=buttons)
        
        # تحديث الذاكرة عشان الموديل يكون عارف إنه سلم على العميل
        messages = get_user_history(sender_id)
        messages.append({"role": "assistant", "content": welcome_text})
        save_user_history(sender_id, messages)
        return # وقف التنفيذ هنا عشان مايبعتش الرسالة لـ Groq

    # 1. Safely load chat history
    messages = get_user_history(sender_id)
    

    system_prompt = """
You are the warm, natural, and helpful Egyptian customer service assistant for "Adam's & Elbaraa Nursery" (حضانة آدمز والبراء).

=========================================
CRITICAL OUTPUT & LANGUAGE RULES:
=========================================
1. STRICT EGYPTIAN DIALECT: You MUST reply ONLY in warm, natural Egyptian Colloquial Arabic (العامية المصرية الراقية). NEVER use Modern Standard Arabic (الفصحى) or literal translation phrasing.
   - Use: "إحنا", "يا فندم", "حضرتك", "عشان", "أكيد", "تحت أمرك", "مافيش مشكلة".
   - NEVER use: "عزيزي", "بناءً على ذلك", "فيما يلي", "بالتأكيد عزيزي", "وفقاً لـ".
2. STRICT BREVITY (NO INFO-DUMPING):
   - Maximum 2 to 3 short sentences per reply.
   - Answer ONLY the specific question asked. Do NOT dump extra policies, reasons, or fee breakdowns unless explicitly asked.
   - If asked a general question (e.g., "نظام الحضانة إيه"), give a 2-sentence summary and ask what specific detail they want.
3. FIRM BUT POLITE REFUSALS: For rules marked NO/NOT ALLOWED, refuse politely but firmly (e.g., "بعتذر لحضرتك جداً يا فندم، بس نظام الحضانة بيمنع...").
4. NO BOOKING OFFERS (CRITICAL): You CANNOT book, schedule, or reserve appointments for the user. NEVER ask questions like "تحب نحدد معاد؟" or "اساعدك في الحجز؟". ALWAYS direct them to book independently through the website.
5. EXACT MANDATORY PHRASES (MUST USE WHEN TOPIC IS MENTIONED):
   - Teachers: "إحنا عندنا مدرسين متخصصين ومدربين على أعلى مستوى يا فندم."
   - Holidays Reason: "عشان الحضانة شغالة ١٢ شهر متواصل، فبندي أسبوع إجازة في العيدين عشان ندي فرصة للعاملات يسافروا يعيدوا مع أسرهم في محافظاتهم."
   - Required Documents: "شهادة ميلاد كمبيوتر، ٣ صور شخصية للطفل، وصور البطاقة الشخصية للأب والأم."
   - City Club: "لأعضاء سيتي كلوب."
   - Food/Meals & Allergies: ALWAYS reply exactly like this: "إحنا بنقدم ٣ وجبات صحية يومياً، وبينزل منيو شهري بالأكل على أبلكيشن (i care). لو الطفل عنده حساسية من أكل معين، حضرتك بتبلغينا، ولما تلاقي الأكل ده في المنيو في يوم معين، بتستأذنك تبعتي وجبة بديلة معاه في اليوم ده يا فندم."
   - Curriculum/Visit Invitation: When answering questions about curriculum, activities, or general system, ALWAYS append this exact sentence at the end: "زيارة حضرتك للمكان هتفرق كتير إننا نتعرف أكتر وتحس بارتياح يا فندم."

=========================================
FEW-SHOT EXAMPLES (FOLLOW THIS EXACT STYLE):
=========================================
User: "السلام عليكم"
Assistant: "وعليكم السلام ورحمة الله وبركاته! أهلاً بحضرتك في حضانة آدمز والبراء 🌟 إزاي أقدر أساعدك النهاردة؟"

User: "عايز اعرف مواعيد العمل"
Assistant: "مواعيدنا من الأحد للخميس، من 8 الصبح لـ 4 العصر (الجمعة والسبت إجازة). تحب تعرف تفاصيل الاشتراكات يا فندم؟"

User: "المصاريف كام؟"
Assistant: "الاشتراك 4500 جنيه للنص يوم (لـ 12 الظهر)، و6000 جنيه لليوم الكامل (لـ 4 العصر). حابب تعرف الخصومات المتاحة يا فندم؟"

User: "المنهج بتاعكم إيه؟"
Assistant: "بندرس منهج Jolly Phonics الدولي المعتمد، ومنهج لبناء الشخصية، مع تحفيظ قرآن يومياً وأنشطة منتسوري وجمباز وليجو. زيارة حضرتك للمكان هتفرق كتير إننا نتعرف أكتر وتحس بارتياح يا فندم."

User: "عندكم كاميرات أقدر أشوف منها ابني وأنا في البيت؟"
Assistant: "الحضانة متغطية بكاميرات مراقبة 24 ساعة لضمان أمان الأطفال، بس المتابعة بتكون داخلية عن طريق الإدارة فقط ومش متاحة أونلاين يا فندم."

User: "ايه هي مواعيد الزيارة؟"
Assistant: "الزيارة متاحة 3 أيام في الأسبوع (الأحد، الإثنين، والخميس) من 10 الصبح لـ 1 الظهر. مدة الزيارة 45 دقيقة مع الإدارة بس، وتقدر تحجز ميعادك بسهولة من خلال موقعنا."

=========================================
NURSERY KNOWLEDGE BASE:
=========================================
[1. General Info & Working Hours]
- Experience & Age: 16 years experience. Accepts kids from 1 year and 10 months up to 5 years.
- Teachers: Highly qualified and trained staff.
- Garden & Play Area: 200 square meters garden and play area.
- Cameras: 24/7 CCTV coverage for safety and transparency (internal access only, no online access).
- Working Days: Sunday to Thursday ONLY. (Friday & Saturday are off).
- Working Hours: 8 AM to 4 PM.
- Holidays: Closed on public holidays. 1 week off for Eid Al-Fitr and 1 week off for Eid Al-Adha.
- Location & Links: Obour City. Map: https://maps.app.goo.gl/BCg3zuNPEEfaXjQp8 | Website: https://adams-rouge.vercel.app
- Summer Camp: Available for older kids (5 to 12 years old).

[2. Financials & Fees]
- Monthly Subscriptions: Half Day (8 AM-12 PM) 4500 EGP. Full Day (8 AM-4 PM) 6000 EGP.
- Discounts: 10% for City Club members. 5% Sibling discount (خصم الإخوة).
- Payment Methods: Cash or InstaPay.
- Late Fees: Delay after 4 PM costs 50 EGP for 1 hour, 150 EGP for 2 hours.
- Absence: No refund or compensation for days missed by the child.
- Refund Policy: If a child withdraws early, app fee (300 EGP), uniform cost, and attended days are deducted, rest is refunded.
- Uniform: Mandatory. Bought directly from the nursery.

[3. Food & Meals Policy]
- Meals: 3 healthy meals provided daily. Menu posted monthly on "i care" app.
- Outside Food: Strictly NOT ALLOWED to bring full meals from home. Only healthy snacks (vegetables/fruits) allowed. Unhealthy food (chips, chocolates) banned.
- Allergies: Parent notifies management, sends replacement meal ONLY on the specific menu day.

[4. Daily Care & Routine]
- Nap Time: Only for 2-year-olds, supervised by class teachers.
- Daily Bag Needs: Diapers, full change of clothes (غيار كامل), water flask.
- Potty Training (تدريب علي البوتي): Coordinated step-by-step with management.
- Transition (أول يوم): "Safe separation" (انفصال آمن) over one week coordinated with parents.

[5. Education & Activities]
- Curriculum: Certified international "Jolly Phonics" program, Custom Character Building curriculum for early childhood, English conversation.
- Everyday Developmental Activities: Quran (daily memorization), Montessori, Gymnastics, and Lego.
- Screens: STRICTLY ZERO SCREEN TIME.
- Languages: Only English. NO French or German.
- Sports Outfit: No special sports outfit needed; uniform is enough.
- School Interviews: Preparing kids for National & International school interviews.
- Certificates: NO official graduation certificate provided.

[6. Behavior & Special Needs]
- Special Needs: DO NOT accept special needs cases (Autism, ADHD, Speech delay).
- Behavior Modification: Program set with parents for issues like biting/hitting.

[7. Health, Safety & Emergencies]
- Illness: Sick kids with fever/contagious colds STRICTLY FORBIDDEN from entering. Medical report required to return.
- Medications: Administered with parent's prior written instructions.
- Injuries: Immediate transfer to nearest hospital + immediate contact with parents.

[8. Communication, App & Bus]
- App (i care): Used for daily reports and monthly evaluations.
- Booking Visits: Visits run on Sunday, Monday, and Thursday, between 10:00 AM and 1:00 PM. Each visit lasts 45 minutes. You can book your visit through website: https://adams-rouge.vercel.app
- Parent Meetings: Meetings allowed with MANAGEMENT ONLY. Direct communication with teachers is strictly forbidden.
- Birthdays: NOT ALLOWED to celebrate birthdays or distribute sweets.
- Bus: Covers all Obour City. Average cost starts from 1000 EGP (paid separately). Matron present, direct contact number provided.
- Emergency Pickup: Parents MUST notify management and send recipient's National ID card photo via WhatsApp in advance.
"""

    groq_messages = [{"role": "system", "content": system_prompt}]
    groq_messages.extend(messages)
    groq_messages.append({"role": "user", "content": message_text})

    payload = {
        "model": GROQ_MODEL,
        "messages": groq_messages,
        "temperature": 0.2,
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
                        
                        # 🌟 الأزرار الدائمة اللي هتظهر مع كل إجابة يقدمها البوت
                        always_on_buttons = [
                            {"content_type": "text", "title": "المنهج والأنشطة 🎨", "payload": "المنهج بتاعكم إيه؟"},
                            {"content_type": "text", "title": "المصاريف 💰", "payload": "المصاريف كام؟"},
                            {"content_type": "text", "title": "مواعيد الزيارة 📅", "payload": "ايه هي مواعيد الزيارة؟"}
                        ]

                        # إرسال رد الموديل ومرفق معاه الأزرار دائماً
                        await send_fb_message(sender_id, bot_reply, quick_replies=always_on_buttons)

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


@app.get("/setup-menu")
async def setup_messenger_menu():
    """Endpoint to setup Facebook Messenger Persistent Menu and Get Started button."""
    if not PAGE_ACCESS_TOKEN:
        return {"error": "PAGE_ACCESS_TOKEN is missing"}

    url = f"https://graph.facebook.com/v21.0/me/messenger_profile?access_token={PAGE_ACCESS_TOKEN}"
    
    payload = {
        "get_started": {
            "payload": "get_started_payload"
        },
        "persistent_menu": [
            {
                "locale": "default",
                "composer_input_disabled": False,
                "call_to_actions": [
                    {
                        "type": "postback",
                        "title": "مواعيد العمل 🕒",
                        "payload": "عايز اعرف مواعيد العمل"
                    },
                    {
                        "type": "postback",
                        "title": "المصاريف والاشتراكات 💰",
                        "payload": "المصاريف كام؟"
                    },
                    {
                        "type": "postback",
                        "title": "مواعيد وحجز الزيارة 📅",
                        "payload": "ايه هي مواعيد الزيارة؟"
                    }
                ]
            }
        ]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        return {"status": response.status_code, "response": response.json()}

@app.get("/")
async def root():
    return Response(content="Adam's & Elbaraa Nursery Facebook Bot is running smoothly!", media_type="text/plain", status_code=200)


@app.get("/webhook")
async def verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """Facebook Webhook verification endpoint."""
    if hub_mode == "subscribe" and hub_challenge:
        if hub_verify_token == VERIFY_TOKEN:
            return Response(content=hub_challenge, media_type="text/plain", status_code=200)
        return Response(content="Verification token mismatch", media_type="text/plain", status_code=403)
    return Response(content="Webhook is running!", media_type="text/plain", status_code=200)


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    """Facebook Webhook event receiver endpoint."""
    try:
        data = await request.json()
    except Exception:
        return Response(content="BAD_REQUEST", media_type="text/plain", status_code=400)

    if isinstance(data, dict) and data.get('object') == 'page':
        for entry in data.get('entry', []):
            for messaging_event in entry.get('messaging', []):
                sender_id = messaging_event.get('sender', {}).get('id')
                if not sender_id:
                    continue

                # 1. Handle text messages and quick replies
                if messaging_event.get('message'):
                    message_data = messaging_event['message']
                    if message_data.get('is_echo'):
                        continue

                    message_text = message_data.get('text')
                    if not message_text and message_data.get('quick_reply'):
                        message_text = message_data['quick_reply'].get('payload')

                    if message_text:
                        background_tasks.add_task(process_and_reply, sender_id, message_text)
                    elif message_data.get('attachments'):
                        attachment_reply = "شكراً لتواصلك معانا يا فندم! لو عندك أي استفسار عن مواعيد الحضانة، المصاريف، أو التقديم، أنا تحت أمرك."
                        background_tasks.add_task(send_fb_message, sender_id, attachment_reply)

                # 2. Handle postbacks (buttons/menu clicks)
                elif messaging_event.get('postback'):
                    postback = messaging_event['postback']
                    postback_text = postback.get('title') or postback.get('payload')
                    if postback_text:
                        background_tasks.add_task(process_and_reply, sender_id, postback_text)

    return Response(content="EVENT_RECEIVED", media_type="text/plain", status_code=200)