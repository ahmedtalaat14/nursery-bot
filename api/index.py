import json
import os
import httpx
from fastapi import FastAPI, Request, Response, Query
from dotenv import load_dotenv
from upstash_redis import Redis

load_dotenv()

app = FastAPI()
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "nursery123")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

redis = Redis(
    url=os.environ.get("UPSTASH_REDIS_REST_URL", ""),
    token=os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
)


async def send_fb_message(sender_id: str, text: str):
    if not PAGE_ACCESS_TOKEN:
        print("❌ PAGE_ACCESS_TOKEN is missing!")
        return

    fb_url = f"https://graph.facebook.com/v21.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    max_length = 2000
    chunks = [text[i:i + max_length] for i in range(0, len(text), max_length)]
    
    async with httpx.AsyncClient(timeout=8.0) as client:
        for chunk in chunks:
            fb_payload = {
                "recipient": {"id": sender_id},
                "message": {"text": chunk}
            }
            try:
                res = await client.post(fb_url, json=fb_payload)
                if res.status_code != 200:
                    print(f"❌ FB Error ({res.status_code}): {res.text}")
                else:
                    print(f"✅ FB message sent to {sender_id}")
            except Exception as e:
                print(f"❌ Exception sending FB message: {e}")


async def process_and_reply(sender_id: str, message_text: str):
    if not GROQ_API_KEY:
        print("❌ GROQ_API_KEY missing!")
        return

    # 1. جلب تاريخ المحادثة من Redis
    history_key = f"chat_{sender_id}"
    user_history_str = redis.get(history_key)
    
    if user_history_str:
        try:
            # لو في تاريخ، بنحوله لـ List
            messages = json.loads(user_history_str)
        except:
            messages = []
    else:
        messages = []

    system_prompt = """
You are the warm, natural, and helpful Egyptian customer service assistant for "Adam's & Elbaraa Nursery" (حضانة آدمز والبراء).

=========================================
CRITICAL OUTPUT & LANGUAGE RULES:
=========================================
1. STRICT EGYPTIAN DIALECT: You MUST reply ONLY in warm, natural Egyptian Colloquial Arabic (العامية المصرية الراقية). NEVER use Modern Standard Arabic (الفصحى).
   - Use: "إحنا", "يا فندم", "حضرتك", "عشان", "أكيد".
2. STRICT BREVITY: Maximum 2 to 3 short sentences per reply. Answer ONLY the specific question asked without extra dumping.
3. FIRM BUT POLITE REFUSALS: For rules marked NO/NOT ALLOWED, refuse politely but firmly.
4. NO BOOKING OFFERS (CRITICAL): You CANNOT book, schedule, or reserve appointments for the user. NEVER ask questions like "تحب نحدد معاد؟" or "اساعدك في الحجز؟". ALWAYS direct them to book independently through the website.
5. EXACT MANDATORY PHRASES:
   - Teachers: "إحنا عندنا مدرسين متخصصين ومدربين على أعلى مستوى يا فندم."
   - Holidays Reason: "عشان الحضانة شغالة ١٢ شهر متواصل، فبندي أسبوع إجازة في العيدين عشان ندي فرصة للعاملات يسافروا يعيدوا مع أسرهم في محافظاتهم."
   - Required Documents: "شهادة ميلاد كمبيوتر، ٣ صور شخصية للطفل، وصور البطاقة الشخصية للأب والأم."
   - Food/Meals & Allergies: "إحنا بنقدم ٣ وجبات صحية يومياً، وبينزل منيو شهري بالأكل على أبلكيشن (i care). لو الطفل عنده حساسية من أكل معين، حضرتك بتبلغينا، ولما تلاقي الأكل ده في المنيو في يوم معين، بتستأذنك تبعتي وجبة بديلة معاه في اليوم ده يا فندم."
   - Curriculum/Visit Invitation: When answering about curriculum, ALWAYS append: "زيارة حضرتك للمكان هتفرق كتير إننا نتعرف أكتر وتحس بارتياح يا فندم."

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
Assistant: " الزيارة متاحة 3 أيام في الأسبوع (الأحد، الإثنين، والخميس) من 10 الصبح لـ 1 الظهر. مدة الزيارة 45 دقيقة مع الإدارة بس، وتقدر تحجز ميعادك بسهولة من خلال موقعنا."

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
- Booking Visits: Visits run on Sunday, Monday, and Thursday, between 10:00 AM and 1:00 PM. Each visit lasts 45 minutes. U can Book YOUR Visit through website
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
        "temperature": 0.3,
        "max_tokens": 500
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers=headers
            )
            if response.status_code == 200:
                res_json = response.json()
                bot_reply = res_json['choices'][0]['message']['content']
                await send_fb_message(sender_id, bot_reply)
                
                # 3. تحديث الذاكرة وحفظها في Redis
                messages.append({"role": "user", "content": message_text})
                messages.append({"role": "assistant", "content": bot_reply})
                
                # الاحتفاظ بآخر 6 رسائل فقط (3 أسئلة و 3 إجابات) لتوفير الـ Tokens
                messages = messages[-6:]
                
                # حفظ في Redis مع انتهاء صلاحية بعد 24 ساعة (86400 ثانية)
                redis.set(history_key, json.dumps(messages), ex=86400)
                
            else:
                print(f"❌ Groq Error ({response.status_code}): {response.text}")
        except Exception as e:
            print(f"❌ Error processing Groq: {e}")


@app.get("/webhook")
async def verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    if hub_mode == "subscribe" and hub_challenge:
        if hub_verify_token == VERIFY_TOKEN:
            return Response(content=hub_challenge, status_code=200)
        return Response(content="Verification token mismatch", status_code=403)
    return Response(content="Webhook is running!", status_code=200)


@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
    except Exception:
        return Response(content="BAD_REQUEST", status_code=400)

    if isinstance(data, dict) and data.get('object') == 'page':
        for entry in data.get('entry', []):
            for messaging_event in entry.get('messaging', []):
                sender_id = messaging_event.get('sender', {}).get('id')
                if not sender_id:
                    continue

                if messaging_event.get('message'):
                    message_data = messaging_event['message']
                    if message_data.get('is_echo'):
                        continue

                    message_text = message_data.get('text')
                    if message_text:
                        await process_and_reply(sender_id, message_text)

    return Response(content="EVENT_RECEIVED", status_code=200)