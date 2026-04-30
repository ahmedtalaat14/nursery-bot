import requests
import os
from flask import Flask, request

app = Flask(__name__)

# 1. حط الكود الطويل بتاعك هنا بين علامات التنصيص (اللي بيبدأ بـ EAA)
PAGE_ACCESS_TOKEN = (
    "EAAg9SeLgAw0BReV3Ad1TuHHulZA3YkPgKsb8VyIhGyMNykZAmT0DKe8iAlniwMIcN6cdDhIvf6dyGI8jRWVgZBrufZC90MlcJsxNUhDzvRuqbJbEZBppySOgT6ns39Yvoyc9mByYh1ZBb6jTwMRt2GAeKC0Y96tRmXR1oC0mzYqreH4yafoL0paSgshPJ1KP80ZBPZBpcYpEc6WQOE2qjsV3vgZDZD"
)
# 2. دي كلمة سر بسيطة هنتأكد بيها إن اللي بيكلمنا هو فيسبوك فعلاً
VERIFY_TOKEN = "nursery123"


@app.route('/', methods=['GET'])
def home():
    return "Nursery Bot is Running Directly with Meta!"


# هنا هنستقبل الداتا من فيسبوك مباشرة
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # فيسبوك بيبعت GET أول مرة عشان يتأكد إن الرابط شغال
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("Webhook Verified successfully by Meta!")
            return challenge, 200
        return "Forbidden", 403

    # ولما عميل يبعت رسالة، فيسبوك بيبعتها لينا كـ POST
    elif request.method == 'POST':
        data = request.json
        if data.get('object') == 'page':
            for entry in data['entry']:
                for messaging_event in entry.get('messaging', []):
                    # لو في رسالة نصية مبعوتة
                    if (
                        messaging_event.get('message')
                        and messaging_event['message'].get('text')
                    ):
                        sender_id = messaging_event['sender']['id']
                        message_text = messaging_event['message']['text']
                        
                        print(f"New message received: {message_text}")
                        
                        # نبعت الرسالة لـ Ollama عشان يفكر
                        bot_reply = get_ollama_response(message_text)
                        
                        # نرد على العميل في الفيسبوك مباشرة
                        send_message(sender_id, bot_reply)
                        
        return "EVENT_RECEIVED", 200


def get_ollama_response(user_message):
    system_prompt = """
    You are the professional and friendly AI assistant for "Adam's & Elbaraa Nursery" (  حضانة ادمز و البراء). 
    Your goal is to provide specific, accurate information based ONLY on the provided knowledge base.

    CRITICAL RULES:
    1. LANGUAGE: Always reply in the same language the user uses. (Arabic for Arabic, English for English).
    2. CONCISENESS: Do not provide information the user did not ask for. Be brief.
    3. EMOJIS: Use emojis sparingly (maximum 1 or 2 per message).
    4. GENERAL INQUIRIES: If the user asks for general info, summarize the top 3-4 highlights only (Experience, Space, Curriculum, Meals).
    5. UNKNOWN INFO: If asked about something not in the list, politely ask them to leave their number for the management to contact them.

    NURSERY KNOWLEDGE BASE:
    - Experience: 16 years of expertise.
    - Licensing & Space: Licensed nursery, large area with a 200m garden for sun and fresh air.
    - Age Group: From 1 year and 10 months up to 5 years.
    - Attendance & Fees:
        * Half Day: 8:00 AM to 12:00 PM - 4000 EGP/month.
        * Full Day: 5500 EGP/month.
        * Discount: 10% for City Club members.
    - Security: Private on-site cameras (Not available for online viewing).
    - Location & Transport: Located in Obour City. Bus service covers all of Obour.
    - Services: 3 healthy meals daily, Potty training assistance.
    - Curriculum & Activities:
        * International curriculum, Montessori sessions, Gymnastics, and Quran.
        * English conversation with foreigners.
        * Learning strategy: Learning through play, activities, character building, and behavior modification.
    """
    
    # حط المفتاح بتاعك هنا بين علامات التنصيص
    GROQ_API_KEY = os.environ("GROQ_API_KEY")
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",  # غيرنا اسم الموديل هنا
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.2
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response_data = response.json()
        
        if 'error' in response_data:
            print("⚠️ المشكلة من Groq:", response_data['error'])
            return "يبدو أن هناك تحديث في النظام."
            
        return response_data['choices'][0]['message']['content']
        
    except Exception as e:
        print("API Exception:", e)
        return "عذراً، يوجد تحديث في النظام حالياً."
    

def send_message(recipient_id, message_text):
    url = (
        f"https://graph.facebook.com/v19.0/me/messages"
        f"?access_token={PAGE_ACCESS_TOKEN}"
    )
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        print("Reply sent to Messenger successfully!")
    else:
        print("Failed to send reply:", response.text)


if __name__ == '__main__':
    app.run(debug=True, port=5000)