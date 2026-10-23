"""SSE 会话放在 Redis，GET 和 POST 不必落在同一进程。"""

import json
from typing import Any

SSE_KEY = "mcp:sse:{session_id}"


def session_key(session_id: str) -> str:
    return SSE_KEY.format(session_id=session_id)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


async def write_session(redis: Any, session_id: str, group_id: int) -> None:
    """记下这条 SSE 属于哪个 MCP 组。"""
    await redis.set(session_key(session_id), json.dumps({"group_id": group_id}))


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
