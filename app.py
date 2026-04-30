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
    You are the friendly, warm, and human-like customer service assistant for "Adam's & Elbaraa Nursery" (حضانة ادمز و البراء).
    
    CRITICAL RULES:
    1. EGYPTIAN COLLOQUIAL TONE (CRITICAL):
       - You MUST reply in warm EGYPTIAN COLLOQUIAL ARABIC (العامية المصرية الراقية).
       - NEVER use rigid Modern Standard Arabic (الفصحى). DO NOT use words like "نحن" or "يرجى".
       - Use words like: "إحنا", "يا فندم", "حضرتك", "بنقدم", "عشان".
    2. STRICT BOUNDARY: You are STRICTLY FORBIDDEN from answering questions outside the context of the nursery.
    3. PROPER NOUNS & EXACT ARABIC PHRASING:
       - Food/Meals: ALWAYS reply exactly like this: "إحنا بنقدم ٣ وجبات صحية يومياً للأطفال يا فندم، ولو الطفل عنده حساسية من أكل معين بنستأذن حضرتك تبعتي أكل بديل معاه." (NEVER translate "nursery" to "مرضعة").
       - Required Documents: "شهادة ميلاد كمبيوتر", "٣ صور شخصية للطفل", "صور البطاقة الشخصية للأب والأم".
       - Holidays Reason: "عشان الحضانة شغالة ١٢ شهر متواصل، فبندي أسبوع إجازة في العيدين عشان ندي فرصة للعاملات يسافروا يعيدوا مع أسرهم في محافظاتهم".
       - City Club: "لأعضاء سيتي كلوب".
    4. LINKS: Include Location Map Link for location questions. Include Website Link for website questions.
    5. CONCISENESS: Be brief, friendly, and do not volunteer unasked information.

    NURSERY KNOWLEDGE BASE:
    - Experience: 16 years.
    - Licensing & Space: Licensed, 200m garden.
    - Age: 1 year and 10 months up to 5 years.
    - Fees: Half Day (8 AM-12 PM) 4000 EGP. Full Day 5500 EGP. 10% discount for City Club members. No trial period.
    - Services: 3 healthy meals daily. Potty training assistance.
    - Payment: Cash or InstaPay.
    - Health & Safety: No resident doctor. Parents contacted immediately for pick-up if a child is sick.
    - Security: Private cameras (not online). Pick-up by pre-registered people ONLY.
    - Communication: Daily reports and monthly evaluations via mobile app.
    - Curriculum: Montessori, Gymnastics, Quran, English conversation with foreigners.
    - Holidays: Official state holidays + full week for Eid Al-Fitr and Eid Al-Adha.
    - Location & Transportation: Obour City. We have a bus service that covers all areas of Obour City. Map: https://maps.app.goo.gl/BCg3zuNPEEfaXjQp8 | Website: [ لينك الموقع ]
    """

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message_text}
        ],
        "temperature": 0.4
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