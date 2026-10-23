from datetime import datetime

from pydantic import BaseModel, Field


class BizTokenCacheOutSchema(BaseModel):
    """一条已缓存的业务 token，给后台查看。"""

    user_id: int = Field(description="业务用户ID")
    system_id: int = Field(description="业务系统ID")
    access_token: str = Field(description="访问令牌")
    expires_at: datetime = Field(description="过期时间")
    token_type: str = Field(description="令牌类型")
    expired: bool = Field(description="是否已过期")
