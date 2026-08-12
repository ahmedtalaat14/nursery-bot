from fastapi import APIRouter, Request, Response, Query, BackgroundTasks
from api.config import VERIFY_TOKEN
from api.services.llm_service import process_and_reply
from api.services.facebook_service import send_fb_message

router = APIRouter()


@router.get("/webhook")
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


@router.post("/webhook")
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
