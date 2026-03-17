import redis
import hashlib
import json
from api.core.config import settings

redis_client = redis.from_url(settings.REDIS_URI)

def semantic_cache_get(prompt: str):
    key = f"cache:{hashlib.md5(prompt.encode()).hexdigest()}"
    val = redis_client.get(key)
    if val:
        return json.loads(val)
    return None

def semantic_cache_set(prompt: str, response: dict, ttl: int = 3600):
    key = f"cache:{hashlib.md5(prompt.encode()).hexdigest()}"
    redis_client.setex(key, ttl, json.dumps(response))
