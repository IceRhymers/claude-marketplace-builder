"""TTL cache wrappers for expensive SQL warehouse queries."""

from __future__ import annotations

from cachetools import TTLCache

from core.usage import get_dollar_usage as _get_dollar_usage
from core.usage import get_top_users as _get_top_users
from core.usage import get_user_usage as _get_user_usage

_dollar_usage_cache: TTLCache = TTLCache(maxsize=1, ttl=60)
_top_users_cache: TTLCache = TTLCache(maxsize=1, ttl=60)
_user_usage_cache: TTLCache = TTLCache(maxsize=128, ttl=30)


def get_dollar_usage_cached(client, warehouse_id: str) -> list[dict]:
    key = "dollar_usage"
    if key in _dollar_usage_cache:
        return _dollar_usage_cache[key]
    result = _get_dollar_usage(client, warehouse_id)
    _dollar_usage_cache[key] = result
    return result


def get_top_users_cached(client, warehouse_id: str, n: int = 10) -> list[dict]:
    key = "top_users"
    if key in _top_users_cache:
        return _top_users_cache[key]
    result = _get_top_users(client, warehouse_id, n)
    _top_users_cache[key] = result
    return result


def get_user_usage_cached(client, warehouse_id: str, user_email: str, days: int = 30) -> list[dict]:
    key = (user_email, days)
    if key in _user_usage_cache:
        return _user_usage_cache[key]
    result = _get_user_usage(client, warehouse_id, user_email, days)
    _user_usage_cache[key] = result
    return result
