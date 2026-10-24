from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CallLogAggregateSchema(BaseModel):
    """按用户和工具汇总。只有次数和耗时，没有请求体或响应体。"""

    model_config = ConfigDict(from_attributes=True)

    user_id: int = Field(description="业务用户ID")
    tool_name: str = Field(description="工具名称")
    count: int = Field(description="调用次数")
    elapsed_ms: int = Field(description="耗时毫秒")
    created_at: datetime = Field(description="最近一次调用时间")
