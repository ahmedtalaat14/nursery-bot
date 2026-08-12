import json
from upstash_redis import Redis
from api.config import UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN

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
