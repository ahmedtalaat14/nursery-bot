import os
import requests
from flask import Flask, request

app = Flask(__name__)

# ==========================================
# 1. إعدادات المفاتيح (Tokens & Keys)
# ==========================================
PAGE_ACCESS_TOKEN = "EAAg9SeLgAw0BReV3Ad1TuHHulZA3YkPgKsb8VyIhGyMNykZAmT0DKe8iAlniwMIcN6cdDhIvf6dyGI8jRWVgZBrufZC90MlcJsxNUhDzvRuqbJbEZBppySOgT6ns39Yvoyc9mByYh1ZBb6jTwMRt2GAeKC0Y96tRmXR1oC0mzYqreH4yafoL0paSgshPJ1KP80ZBPZBpcYpEc6WQOE2qjsV3vgZDZD"
VERIFY_TOKEN = "nursery123"
# المفتاح السري بيتقرأ من Vercel بأمان
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# ==========================================
# 2. دالة التفكير والرد
# ==========================================
def process_and_reply(sender_id, message_text):
    system_prompt = """
    You are the professional and friendly AI assistant for
    "Adam's & Elbaraa Nursery" (حضانة ادمز و البراء).
    Your goal is to provide specific, accurate information based
    ONLY on the provided knowledge base.

    CRITICAL RULES:
    1. STRICT BOUNDARY (OUT-OF-SCOPE): You are STRICTLY FORBIDDEN from answering questions outside the context of the nursery. If the user asks about anime, science, general knowledge, coding, or anything unrelated to the nursery, you MUST politely decline.
       - In English, reply: "I specialize only in answering questions about Adam's & Elbaraa Nursery. How can I help you with our services today?"
       - In Arabic, reply: "أنا هنا لمساعدتك في أي استفسار يخص حضانة ادمز والبراء فقط. كيف يمكنني مساعدتك اليوم؟"
    2. STRICT LANGUAGE MATCHING:
       - If the user asks in English, you MUST reply ENTIRELY in English.
       - If the user asks in Arabic, you MUST reply ENTIRELY in Arabic.
       - NEVER mix languages in the same response.
    3. PROPER NOUNS & GRAMMAR:
       - In English, always use "City Club members".
       - In Arabic, ALWAYS use EXACTLY "لأعضاء سيتي كلوب".
         DO NOT use words like "للعضوين" or "نادي المدينة".
    4. LINKS: If the user asks for the location, address, or wants to visit, you MUST include the Location Map Link. If they ask for the website, include the Website Link.
    5. CONCISENESS: Do not provide information the user did not ask for. Be brief.
    6. EMOJIS: Use emojis sparingly (maximum 1 or 2 per message).

    NURSERY KNOWLEDGE BASE:
    - Experience: 16 years of expertise.
    - Licensing & Space: Licensed nursery, large area with a 200m garden for sun and fresh air.
    - Age Group: From 1 year and 10 months up to 5 years.
    - Attendance & Fees:
        * Half Day: 8:00 AM to 12:00 PM - 4000 EGP/month.
        * Full Day: 5500 EGP/month.
        * Discount: 10% for City Club members.
        * Note: No trial period is available.
    - Payment Methods: Cash or InstaPay.
    - Health & Safety: No resident doctor. If a child falls ill, parents are contacted immediately for pick-up. For food allergies, parents must send an alternative meal.
    - Security & Pick-up: Private on-site cameras (Not available online). Children are handed over ONLY to pre-registered individuals.
    - Communication: Daily reports and monthly evaluations are provided via our mobile app.
    - Staff & Curriculum: Highly trained and specialized teachers. International curriculum, Montessori, Gymnastics, Quran, and English conversation with foreigners.
    - Required Documents: Computerized birth certificate (شهادة ميلاد كمبيوتر), 3 personal photos of the child (٣ صور شخصية للطفل), and copies of both parents' National ID cards (صور البطاقة الشخصية للأب والأم).
    - Holidays: Closed on all official state holidays. We also take a full week off for Eid Al-Fitr and Eid Al-Adha. Reason: The nursery operates continuously for 12 months a year, so this allows our support workers/nannies (العاملات) to travel to their home governorates within Egypt.
    - Location & Links:
        * Address: Obour City. Bus service covers all of Obour.
        * Location Map Link: https://maps.app.goo.gl/BCg3zuNPEEfaXjQp8
        * Official Website: [ لينك الموقع ]
    """

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message_text}
        ],
        "temperature": 0.2
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers)
        
        if response.status_code == 200:
            bot_reply = response.json()['choices'][0]['message']['content']
            
            fb_url = f"https://graph.facebook.com/v21.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
            fb_payload = {
                "recipient": {"id": sender_id},
                "message": {"text": bot_reply}
            }
            requests.post(fb_url, json=fb_payload)
        else:
            print(f"Groq API Error: {response.text}")
            
    except Exception as e:
        print(f"Error in processing: {e}")

# ==========================================
# 3. مسارات السيرفر (Webhooks)
# ==========================================
@app.route('/webhook', methods=['GET'])
def verify():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return "Verification token mismatch", 403
    return "Webhook is running!", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    
    if data['object'] == 'page':
        for entry in data['entry']:
            for messaging_event in entry['messaging']:
                if messaging_event.get('message'):
                    sender_id = messaging_event['sender']['id']
                    message_text = messaging_event['message'].get('text')
                    
                    if message_text:
                        print(f"New message received from {sender_id}")
                        process_and_reply(sender_id, message_text)
                        
    return 'EVENT_RECEIVED', 200

if __name__ == '__main__':
    app.run(port=5000, debug=True)