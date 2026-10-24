from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema

from .crud import CallLogCRUD
from .model import CallLogModel
from .schema import CallLogAggregateSchema


class CallLogService:
    """记录 tools/call，并按用户和工具汇总次数。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db

    async def write(
        self,
        user_id: int,
        group_id: int,
        tool_name: str,
        system_id: int | None,
        elapsed_ms: int,
        ok: bool,
        http_status: int | None,
    ) -> None:
        await CallLogCRUD(self.auth, self.db).create(
            data={
                "user_id": user_id,
                "group_id": group_id,
                "tool_name": tool_name,
                "system_id": system_id,
                "elapsed_ms": elapsed_ms,
                "ok": ok,
                "http_status": http_status,
            }
        )

    async def aggregate(self) -> list[CallLogAggregateSchema]:
        elapsed = func.coalesce(func.sum(CallLogModel.elapsed_ms), 0)
        stmt = (
            select(
                CallLogModel.user_id,
                CallLogModel.tool_name,
                func.count(CallLogModel.id).label("count"),
                elapsed.label("elapsed_ms"),
                func.max(CallLogModel.created_at).label("created_at"),
            )
            .group_by(CallLogModel.user_id, CallLogModel.tool_name)
            .order_by(CallLogModel.user_id.asc(), CallLogModel.tool_name.asc())
        )
        result = await self.db.execute(stmt)
        rows: list[CallLogAggregateSchema] = []
        for user_id, tool_name, count, elapsed_ms, created_at in result.all():
            when = created_at if isinstance(created_at, datetime) else datetime.fromisoformat(str(created_at))
            rows.append(
                CallLogAggregateSchema(
                    user_id=int(user_id),
                    tool_name=str(tool_name),
                    count=int(count),
                    elapsed_ms=int(elapsed_ms),
                    created_at=when,
                )
            )
        return rows
