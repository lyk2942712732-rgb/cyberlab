from functools import lru_cache
from fastapi import HTTPException
from redis import Redis, RedisError
from app.core.config import settings


@lru_cache
def cache() -> Redis:
    return Redis.from_url(settings().redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)


def limit(key: str, maximum: int, seconds: int):
    if settings().testing:
        return
    try:
        count = cache().eval("local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n", 1, f"limit:{key}", seconds)
    except RedisError:
        raise HTTPException(503, "短期状态服务暂不可用，请稍后重试") from None
    if count > maximum:
        raise HTTPException(429, "请求过于频繁，请稍后再试")
