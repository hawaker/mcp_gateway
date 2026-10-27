"""Wren NL→SQL client (mockable; Task 4 WrenClient style)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


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
    """Production plug-in: until real Wren ask is wired, returns ASK_FAILED."""

    async def ask(
        self,
        *,
        question: str,
        mdl_hash: str,
        project_id: int,
    ) -> WrenAskResult:
        from app.config.setting import settings

        _ = settings.GENBI_WREN_ENGINE_ENDPOINT, question, mdl_hash, project_id
        return WrenAskResult(
            status="failed",
            error_message="Wren 问数尚未配置",
            error_code="ASK_FAILED",
        )


def get_wren_ask_client() -> WrenAskClient:
    return SettingsWrenAskClient()
