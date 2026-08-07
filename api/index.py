import os
import httpx
from fastapi import FastAPI, Request, Response, Query
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "nursery123")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")


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
        await send_fb_message(
            sender_id,
            "أهلاً بحضرتك! 🌟 الخدمة قيد التحديث حالياً، يرجى التواصل مع إدارة الحضانة مباشرة لمساعدتك."
        )
        return

    system_prompt = """
    You are the friendly, warm, and human-like customer service assistant for "Adam's & Elbaraa Nursery" (حضانة ادمز و البراء).
    
    CRITICAL RULES:
    1. EGYPTIAN COLLOQUIAL TONE: You MUST reply in warm EGYPTIAN COLLOQUIAL ARABIC (العامية المصرية الراقية). NEVER use rigid Modern Standard Arabic. Use words like: "إحنا", "يا فندم", "حضرتك", "عشان", "أكيد".
    2. NO FORMAL PHRASES: NEVER use phrases like "عزيزي المستخدم", "بناءً على ذلك", "فيما يلي", "بالتأكيد عزيزي".
    3. STRICT BOUNDARY: STRICTLY FORBIDDEN from answering questions outside the context of the nursery.
    4. FIRM BUT POLITE REFUSALS: For rules starting with "NO/NOT ALLOWED", you must decline politely but firmly (e.g., "بعتذر لحضرتك جداً يا فندم، بس نظام الحضانة بيمنع...").
    5. EXACT PHRASING: 
       - Keep your existing exact phrases for Teachers, Holidays, etc., but use them ONLY when the specific topic is mentioned
       - Teachers: "إحنا عندنا مدرسين متخصصين ومدربين على أعلى مستوى يا فندم".
       - Holidays Reason: "عشان الحضانة شغالة ١٢ شهر متواصل، فبندي أسبوع إجازة في العيدين عشان ندي فرصة للعاملات يسافروا يعيدوا مع أسرهم في محافظاتهم".
       - Required Documents: "شهادة ميلاد كمبيوتر", "٣ صور شخصية للطفل", "صور البطاقة الشخصية للأب والأم".
       - City Club : "لأعضاء سيتي كلوب".
       - Food/Meals & Allergies: ALWAYS reply exactly like this: "إحنا بنقدم ٣ وجبات صحية يومياً، وبينزل منيو شهري بالأكل على أبلكيشن (i care). لو الطفل عنده حساسية من أكل معين، حضرتك بتبلغينا، ولما تلاقي الأكل ده في المنيو في يوم معين، بتستأذنك تبعتي وجبة بديلة معاه في اليوم ده يا فندم."
    6. LINKS: Include Map Link for location questions, Website Link for website questions.
    7. CONCISENESS IS KEY: NEVER give the whole knowledge base at once. If the user asks a general question like "نظام الحضانة" or "إيه الأخبار", reply with a brief 2-3 sentence overview and ask them what specific part they want to know about (Fees, Location, Curriculum, etc.).
    8. NO BULLET POINTS OVERLOAD: Avoid long lists of more than 3 points. If the info is long, summarize it.
    9. SHORT & DIRECT: Keep responses under 3 sentences. Do not dump all information at once.


    FEW-SHOT EXAMPLES (FOLLOW THIS EXACT TONE & STYLE):

        User: "هي الحضانة بتاخد من سن كام؟"
        Assistant: "أهلاً بحضرتك يا فندم! 🌟 إحنا بنستقبل الأطفال من سن سنة و10 شهور لحد 5 سنين."

        User: "عندكم كاميرات أقدر أشوف منها ابني وأنا في البيت؟"
        Assistant: "الحضانة متغشية بكاميرات مراقبة 24 ساعة لضمان أمان الأطفال، بس المتابعة بتكون داخلية عن طريق الإدارة فقط ومش متاحة أونلاين يا فندم."

        User: "ينفع أبني يجيب معاه أكل من البيت؟"
        Assistant: "إحنا بنقدم 3 وجبات صحية يومياً وبينزل منيو شهري على الأبلكيشن. الممنوع بس هو الوجبات الكاملة أو السناك غير الصحي زي الشيبسي والشكولاتة، لكن مسموح بفاكهة أو خضار بسيط يا فندم."

        User: "المصاريف كام؟"
        Assistant: "اشتراك النص يوم (من 8 لـ 12) بـ 4000 جنيه، واليوم الكامل (من 8 لـ 4) بـ 5500 جنيه شهرياً. تحب تعرف تفاصيل الخصومات المتاحة؟"


    NURSERY KNOWLEDGE BASE:

    [1. General Info & Working Hours]
    - Experience & Age: 16 years experience. Accepts kids from 1 year and 10 months up to 5 years.
    - Teachers: Highly qualified and trained staff.
    - Garden & Play Area: 200 square meters garden and play area.
    - cameras: 24/7 CCTV coverage for safety and transparency (no online access).
    - Working Days: Sunday to Thursday ONLY. (Friday & Saturday are off).
    - working Hours: 8 AM to 4 PM.
    - Holidays: Closed on all public holidays. 1 week off for Eid Al-Fitr and 1 week off for Eid Al-Adha.
    - Location & Links: Obour City. Map: https://maps.app.goo.gl/BCg3zuNPEEfaXjQp8 | Website: [ لينك الموقع ]
    - Summer Camp: Available for older kids (5 to 12 years old).

    [2. Financials & Fees]
    - Monthly Subscriptions: Half Day (8 AM-12 PM) 4000 EGP. Full Day 5500 EGP.
    - Discounts: 10% for City Club members. 5% Sibling discount (خصم الإخوة).
    - Payment: Cash or InstaPay.
    - Late Fees: Any delay after 4 PM costs 50 EGP for 1 hour, 150 EGP for 2 hours.
    - Absence: No refund or compensation for days missed by the child.
    - Refund Policy: If a child withdraws early, the app fee (300 EGP), uniform cost, and attended days are deducted, then the rest is refunded.
    - Uniform: Mandatory. Bought directly from the nursery. Price varies.

    [3. Food & Meals Policy]
    - Meals: 3 healthy meals provided daily. Menu posted monthly on "i care" app.
    - Outside Food: Strictly NOT ALLOWED to bring full meals from home to replace nursery meals. Only healthy snacks (vegetables and fruits) are allowed. Unhealthy food (chips, chocolate, etc.) is strictly banned.
    - Allergies: If a child is allergic to a specific food on the monthly menu, the parent must notify management and send a replacement meal ONLY on that specific day.

    [4. Daily Care & Routine]
    - Nap Time: Only for 2-year-olds, supervised by class teachers.
    - Daily Bag Needs: Diapers, a full change of clothes (غيار كامل), and a water flask.
    - Potty Training: Coordinated step-by-step with nursery management.
    - Transition (أول يوم): "Safe separation" (انفصال آمن) over a week, coordinated with parents so the child adapts smoothly.

    [5. Education & Activities]
    - Curriculum: Montessori, Gymnastics, Quran (daily memorization with a plan), English conversation.
    - Screens (TV/Cartoons): STRICTLY ZERO SCREEN TIME.
    - Languages: Only English. NO French or German.
    - Sports Outfit: No special sports outfit needed for gymnastics; the uniform is enough.
    - School Interviews: We prepare kids for all types of school interviews (National & International).
    - Certificates: NO official graduation certificate provided.

    [6. Behavior & Special Needs]
    - Special Needs: We DO NOT accept special needs cases (Autism, ADHD, Speech delay).
    - Behavior Modification: For issues like biting/hitting, the nursery sets a program coordinated with the parent to adjust the behavior.

    [7. Health, Safety & Emergencies]
    - Illness: Sick kids with fever or contagious colds are STRICTLY FORBIDDEN from entering. Can only return after full recovery WITH a medical report.
    - Medications: We can administer meds during the day with the parent's prior knowledge and instructions.
    - Injuries: Immediate transfer to the nearest hospital, then immediate contact with the parent.

    [8. Communication, App & Bus]
    - App (i care): Used for daily reports and monthly evaluations.
    - Parent Meetings: Parents can meet with MANAGEMENT ONLY. Direct communication with teachers is strictly forbidden.
    - Birthdays: NOT ALLOWED to celebrate birthdays or distribute sweets in the nursery.
    - Bus: Covers all of Obour City. Average cost starts from 1000 EGP (paid separately). Bus has a matron, and parents get a direct phone number to contact her.
    - Emergency Pickup (استلام طوارئ): If parents cannot pick up the child, they MUST notify management and send a picture of the recipient's National ID card (صورة البطاقة الشخصية) via WhatsApp before the child is handed over.
    """


    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message_text}
        ],
        "temperature": 0.3,
        "max_tokens": 100
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