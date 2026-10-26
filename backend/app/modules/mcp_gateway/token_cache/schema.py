from datetime import datetime

from pydantic import BaseModel, Field


class BizTokenCacheOutSchema(BaseModel):
    """一条已缓存的业务鉴权变量包，给后台查看。"""

    user_id: int = Field(description="业务用户ID")
    system_id: int = Field(description="业务系统ID")
    vars: dict[str, str] = Field(description="鉴权变量")
    var_keys: list[str] = Field(description="变量键名")
    access_token: str = Field(description="vars.access_token 摘要，可能为空")
    expires_at: datetime = Field(description="过期时间")
    token_type: str = Field(description="令牌类型")
    expired: bool = Field(description="是否已过期")
