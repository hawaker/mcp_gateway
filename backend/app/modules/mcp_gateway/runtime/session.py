"""SSE 会话放在 Redis，GET 和 POST 不必落在同一进程。"""

import json
from typing import Any

SSE_KEY = "mcp:sse:{session_id}"
SSE_CHANNEL = "mcp:sse:channel:{session_id}"
SESSION_TTL_SECONDS = 60


def session_key(session_id: str) -> str:
    return SSE_KEY.format(session_id=session_id)


def message_channel(session_id: str) -> str:
    return SSE_CHANNEL.format(session_id=session_id)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


async def write_session(redis: Any, session_id: str, group_id: int) -> None:
    """记下这条 SSE 属于哪个 MCP 组。键带 TTL，避免断线后一直留着。"""
    await redis.set(session_key(session_id), json.dumps({"group_id": group_id}), ex=SESSION_TTL_SECONDS)


async def refresh_session(redis: Any, session_id: str) -> None:
    """GET 还挂着时把 TTL 续上。"""
    await redis.expire(session_key(session_id), SESSION_TTL_SECONDS)


async def read_session(redis: Any, session_id: str) -> int | None:
    """键不存在或内容不是组号时返回 None。"""
    raw = _text(await redis.get(session_key(session_id)))
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    group_id = data.get("group_id")
    if isinstance(group_id, bool) or not isinstance(group_id, int):
        return None
    return group_id


async def publish_result(redis: Any, session_id: str, payload: dict[str, Any]) -> None:
    """把 JSON-RPC 结果交给挂着 GET 的那个进程。"""
    await redis.publish(message_channel(session_id), json.dumps(payload, ensure_ascii=False))
