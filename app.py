import os
import requests
import threading
from flask import Flask, request

app = Flask(__name__)

# ==========================================
# 1. إعدادات المفاتيح (Tokens & Keys)
# ==========================================
PAGE_ACCESS_TOKEN = (
    "EAAg9SeLgAw0BReV3Ad1TuHHulZA3YkPgKsb8VyIhGyMNykZAmT0DKe8iAlniwMIcN6cdDhIvf6dyGI8jRWVgZBrufZC90MlcJsxNUhDzvRuqbJbEZBppySOgT6ns39Yvoyc9mByYh1ZBb6jTwMRt2GaeKC0Y96tRmXR1oC0mzYqreH4yafoL0paSgshPJ1KP80ZBPZBpcYpEc6WQOE2qjsV3vgZDZD"
)
VERIFY_TOKEN = "nursery123"
# المفتاح السري بيتقرأ من Vercel بأمان
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# ==========================================
# 2. دالة التفكير والرد (بتشتغل في الخلفية)
# ==========================================


def process_and_reply(sender_id, message_text):
    system_prompt = """
    You are the professional and friendly AI assistant for
    "Adam's & Elbaraa Nursery" (حضانة ادمز و البراء).
    Your goal is to provide specific, accurate information based
    ONLY on the provided knowledge base.

    CRITICAL RULES:
    1. STRICT LANGUAGE MATCHING:
       - If the user asks in English, you MUST reply ENTIRELY in
       English.
       - If the user asks in Arabic, you MUST reply ENTIRELY in
       Arabic.
       - NEVER mix languages in the same response.
    2. PROPER NOUNS & GRAMMAR:
       - In English, always use "City Club members".
       - In Arabic, ALWAYS use EXACTLY "لأعضاء سيتي كلوب".
         DO NOT use words like "للعضوين" or "نادي المدينة".
    3. LINKS: If the user asks for the location, address, or
    wants to visit, you MUST include the Location Map Link. If
    they ask for website or want to book a visit, tour or
    appointment, include the Website Link.
    4. CONCISENESS: Do not provide information the user did not
    ask for. Be brief.
    5. EMOJIS: Use emojis sparingly (maximum 1 or 2 per message).

    NURSERY KNOWLEDGE BASE:
    - Experience: 16 years of expertise.
    - Licensing & Space: Licensed nursery, large area with a 200m
    garden for sun and fresh air.
    - Age Group: From 1 year and 10 months up to 5 years.
    - Attendance & Fees:
        * Half Day: 8:00 AM to 12:00 PM - 4000 EGP/month.
        * Full Day: 5500 EGP/month.
        * Discount: 10% for City Club members.
    - Security: Private on-site cameras (Not available for online viewing).
    - Location & Links:
        * Address: Obour City. Bus service covers all of Obour.
        * Location Map Link: [https://maps.app.goo.gl/BCg3zuNPEEfaXjQp8]
        * Official Website: [ لينك الموقع ]
    - Services: 3 healthy meals daily, Potty training assistance.
    - Curriculum & Activities:
        * International curriculum, Montessori sessions,
        Gymnastics, and Quran.
        * English conversation with foreigners.
        * Learning strategy: Learning through play, activities,
        character building, and behavior modification.
    """

    # تجهيز الطلب لـ Groq
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message_text},
        ],
        "temperature": 0.2,
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=payload,
            headers=headers,
        )

        if response.status_code == 200:
            bot_reply = response.json()["choices"][0]["message"]["content"]

            fb_url = (
                "https://graph.facebook.com/v21.0/me/messages"
                f"?access_token={PAGE_ACCESS_TOKEN}"
            )
            fb_payload = {
                "recipient": {"id": sender_id},
                "message": {"text": bot_reply},
            }
            requests.post(fb_url, json=fb_payload)
        else:
            print(f"Groq API Error: {response.text}")

    except Exception as e:
        print(f"Error in background processing: {e}")


# ==========================================
# 3. مسارات السيرفر (Webhooks)
# ==========================================


@app.route('/webhook', methods=['GET'])
def verify():
    # التحقق من الباب لما فيسبوك يخبط أول مرة
    if (request.args.get("hub.mode") == "subscribe" and
            request.args.get("hub.challenge")):
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

                        # هنا السحر: بنفتح مسار فرعي (Thread)
                        # يعالج الرسالة ويرد
                        thread = threading.Thread(
                            target=process_and_reply,
                            args=(sender_id, message_text))
                        thread.start()

    # بنرد على فيسبوك فوراً عشان ميقلقش ويعمل Timeout
    return 'EVENT_RECEIVED', 200


if __name__ == '__main__':
    app.run(port=5000, debug=True)

