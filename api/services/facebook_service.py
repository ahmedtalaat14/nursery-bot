import httpx
from api.config import PAGE_ACCESS_TOKEN


async def send_fb_message(
    sender_id: str,
    text: str,
    quick_replies: list = None,
    call_admin: bool = False,
):
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
            is_last = i == len(chunks) - 1

            fb_payload = {
                "recipient": {"id": sender_id},
                "message": {"text": chunk}
            }

            # Add quick replies to the last text message only.
            if quick_replies and is_last:
                fb_payload["message"]["quick_replies"] = quick_replies

            try:
                res = await client.post(fb_url, json=fb_payload)
                if res.status_code != 200:
                    print(f"❌ FB Error ({res.status_code}): {res.text}")
                else:
                    print(f"✅ FB message sent to {sender_id}")
            except Exception as e:
                print(f"❌ Exception sending FB message: {e}")

        # For questions the bot cannot answer, show a real Messenger call button.
        if call_admin:
            call_payload = {
                "recipient": {"id": sender_id},
                "message": {
                    "attachment": {
                        "type": "template",
                        "payload": {
                            "template_type": "button",
                            "text": "للتواصل مع إدارة الحضانة مباشرةً 📞",
                            "buttons": [
                                {
                                    "type": "phone_number",
                                    "title": "اتصل بإدارة الحضانة 📞",
                                    "payload": "+201111299025"
                                }
                            ]
                        }
                    }
                }
            }

            try:
                res = await client.post(fb_url, json=call_payload)
                if res.status_code != 200:
                    print(f"❌ FB Call Button Error ({res.status_code}): {res.text}")
                else:
                    print(f"✅ FB call button sent to {sender_id}")
            except Exception as e:
                print(f"❌ Exception sending FB call button: {e}")
