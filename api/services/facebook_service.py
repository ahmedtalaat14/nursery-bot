import httpx
from api.config import PAGE_ACCESS_TOKEN
from api.services.quick_rules import ADMIN_PHONE_E164

# Messenger button template text is limited to 640 characters.
BUTTON_TEMPLATE_MAX_TEXT = 640


async def send_fb_message(
    sender_id: str,
    text: str,
    quick_replies: list = None,
    call_admin: bool = False,
):
    """
    Sends a message back to user via Facebook Messenger Graph API.
    With call_admin=True, the text and a "call the administration" button are
    sent together as ONE message bubble.
    """
    if not text:
        return

    if not PAGE_ACCESS_TOKEN:
        print("❌ PAGE_ACCESS_TOKEN is missing!")
        return

    fb_url = f"https://graph.facebook.com/v21.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"

    if call_admin and len(text) <= BUTTON_TEMPLATE_MAX_TEXT:
        await _send_call_admin_message(fb_url, sender_id, text)
        return

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

    # Text too long for a button template: text was sent above, add the button after it.
    if call_admin:
        await _send_call_admin_message(fb_url, sender_id, "📞 إدارة حضانة آدمز والبراء")


async def _send_call_admin_message(fb_url: str, sender_id: str, text: str):
    """Sends text + a real Messenger call button in a single bubble."""
    call_payload = {
        "recipient": {"id": sender_id},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": text,
                    "buttons": [
                        {
                            "type": "phone_number",
                            "title": "اتصل بالإدارة 📞",
                            "payload": ADMIN_PHONE_E164,
                        }
                    ],
                },
            }
        },
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.post(fb_url, json=call_payload)
            if res.status_code != 200:
                print(f"❌ FB Call Button Error ({res.status_code}): {res.text}")
                # Fallback: at least deliver the text (it already contains the number).
                await client.post(fb_url, json={"recipient": {"id": sender_id}, "message": {"text": text}})
            else:
                print(f"✅ FB call button sent to {sender_id}")
        except Exception as e:
            print(f"❌ Exception sending FB call button: {e}")
