import redis
from app.core.config import settings

# Create a shared Redis client instance.
# decode_responses=True ensures Redis automatically decodes bytes to Python strings.
redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
