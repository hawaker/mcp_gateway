"""Wren NL→SQL client (mockable; Task 4 WrenClient style)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WrenAskResult:
    """NL→SQL outcome."""

    status: str = "finished"
    sql: str | None = None
    error_message: str | None = None
    error_code: str | None = None


@runtime_checkable
class WrenAskClient(Protocol):
    async def ask(
        self,
        *,
        question: str,
        mdl_hash: str,
        project_id: int,
    ) -> WrenAskResult: ...


class StubWrenAskClient:
    """In-process stub for tests."""

    def __init__(
        self,
        *,
        sql: str = "SELECT 1",
        status: str = "finished",
        error_message: str | None = None,
        error_code: str | None = None,
    ) -> None:
        self.sql = sql
        self.status = status
        self.error_message = error_message
        self.error_code = error_code
        self.ask_calls = 0
        self.last_question: str | None = None

    async def ask(
        self,
        *,
        question: str,
        mdl_hash: str,
        project_id: int,
    ) -> WrenAskResult:
        self.ask_calls += 1
        self.last_question = question
        _ = mdl_hash, project_id
        return WrenAskResult(
            status=self.status,
            sql=self.sql if self.status == "finished" else None,
            error_message=self.error_message,
            error_code=self.error_code,
        )


class SettingsWrenAskClient:
    """Production client: HTTP Wren AI or in-process facade ask."""

    async def ask(
        self,
        *,
        question: str,
        mdl_hash: str,
        project_id: int,
    ) -> WrenAskResult:
        from app.config.setting import settings
        from app.modules.genbi.ai.http_client import http_ai_configured, http_ask

        _ = settings.GENBI_WREN_ENGINE_ENDPOINT

        if http_ai_configured():
            try:
                result = await http_ask(
                    question=question,
                    mdl_hash=mdl_hash,
                    project_id=str(project_id),
                )
            except Exception as exc:
                logger.exception("HTTP Wren ask failed project=%s", project_id)
                return WrenAskResult(
                    status="failed",
                    error_message=str(exc) or "问数失败",
                    error_code="ASK_FAILED",
                )
            return self._from_result(result)

        try:
            from app.modules.genbi.ai import facade as genbi_ai

            query_id = await genbi_ai.submit_ask(
                query=question,
                mdl_hash=mdl_hash,
                project_id=str(project_id),
            )
            result = await genbi_ai.get_ask_result(query_id)
            return self._from_result(result)
        except Exception as exc:
            logger.exception("in-process Wren ask failed project=%s", project_id)
            return WrenAskResult(
                status="failed",
                error_message=(
                    "Wren 问数尚未可用：请配置 GENBI_WREN_AI_ENDPOINT 或安装 GenBI AI 依赖 "
                    f"({exc})"
                ),
                error_code="ASK_FAILED",
            )

    @staticmethod
    def _from_result(result: dict) -> WrenAskResult:
        from app.modules.genbi.ai.facade import extract_sql_from_ask_result

        status = (result.get("status") or "failed").lower()
        if status != "finished":
            err = result.get("error") if isinstance(result.get("error"), dict) else {}
            return WrenAskResult(
                status="failed",
                error_message=(err.get("message") if isinstance(err, dict) else None)
                or "问数失败",
                error_code=(err.get("code") if isinstance(err, dict) else None) or "ASK_FAILED",
            )
        sql = extract_sql_from_ask_result(result)
        if not sql:
            return WrenAskResult(
                status="failed",
                error_message="问数未返回 SQL",
                error_code="ASK_FAILED",
            )
        return WrenAskResult(status="finished", sql=sql)


def get_wren_ask_client() -> WrenAskClient:
    return SettingsWrenAskClient()
