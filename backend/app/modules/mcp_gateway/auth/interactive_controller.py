"""终端用户打开的验证页和回调。不走管理员权限，响应里不放业务 token。

callback 必须写在 /{nonce} 前面，否则 callback 会被当成 nonce。
"""

import html
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from app.modules.mcp_gateway.auth.extract import TokenExtractError, extract_token
from app.modules.mcp_gateway.auth.interactive import InteractiveAuth, load_enabled_interactive_config
from app.modules.mcp_gateway.auth.model import AuthConfigModel
from app.modules.mcp_gateway.token_cache.store import TokenCache

InteractiveAuthRouter = APIRouter(prefix="/auth/interactive", tags=["交互式验证"])


def _html(message: str, status_code: int, *, verify_url: str | None = None) -> HTMLResponse:
    body = f"<p>{html.escape(message)}</p>"
    if verify_url:
        href = html.escape(verify_url, quote=True)
        body += f'<p><a href="{href}">打开验证页面</a></p>'
    page = f"<!DOCTYPE html><html><body>{body}</body></html>"
    # 第二个参数是 HTTP 状态，用位置传递，避免业务代码里的关键字传参。
    return HTMLResponse(page, status_code)


def _opener(request: Request) -> str | None:
    """样本测试用 X-Test-User 表示打开链接的人。浏览器和 OA 回调不会带这个头。"""
    raw = request.headers.get("X-Test-User")
    if raw is None:
        return None
    text = raw.strip()
    return text or None


def _owns(opener: str | None, user_id: int) -> bool:
    """头缺失时，不可猜测的 nonce 就是凭证。头在且对不上才拒绝。"""
    if opener is None:
        return True
    return opener == str(user_id)


async def _enabled_config(request: Request, system_id: int) -> AuthConfigModel | None:
    """测试把规则放在 app.state 上，这样不必在库里插入系统行。生产环境改查库。"""
    override: dict[int, AuthConfigModel] | None = getattr(request.app.state, "interactive_configs", None)
    if override is not None:
        row = override.get(system_id)
        if row is None or not row.enabled or row.method != "interactive":
            return None
        return row
    return await load_enabled_interactive_config(system_id)


async def _callback_body(request: Request) -> str:
    """GET 回调通常没有正文。查询串交给 extract_token，form 规则才能读到浏览器带回来的字段。"""
    raw = await request.body()
    text = raw.decode("utf-8", errors="replace")
    if text:
        return text
    return str(request.url.query)


@InteractiveAuthRouter.get("/callback", summary="交互式验证回调")
async def interactive_callback(
    request: Request,
    nonce: Annotated[str | None, Query(description="验证链接上的 nonce")] = None,
) -> HTMLResponse:
    if not nonce:
        return _html("验证链接已失效", 404)
    found = await InteractiveAuth(request.app.state.redis).read(nonce)
    if found is None:
        return _html("验证链接已失效", 404)
    user_id, system_id = found
    if not _owns(_opener(request), user_id):
        return _html("这个验证链接不属于当前用户", 403)
    config = await _enabled_config(request, system_id)
    if config is None:
        return _html("没有启用的交互式鉴权", 400)
    try:
        bundle = extract_token(body=await _callback_body(request), headers=dict(request.headers), rule=config.rule or {})
    except TokenExtractError:
        return _html("没有拿到可用的业务凭证", 400)
    await TokenCache(request.app.state.redis).put(user_id, system_id, bundle)
    await InteractiveAuth(request.app.state.redis).consume(nonce)
    return _html("验证已完成，可以回到客户端重试", 200)


@InteractiveAuthRouter.get("/{nonce}", summary="打开交互式验证页")
async def open_interactive_link(request: Request, nonce: str) -> HTMLResponse:
    found = await InteractiveAuth(request.app.state.redis).read(nonce)
    if found is None:
        return _html("验证链接已失效", 404)
    user_id, system_id = found
    if not _owns(_opener(request), user_id):
        return _html("这个验证链接不属于当前用户", 403)
    config = await _enabled_config(request, system_id)
    verify_url = config.url if config is not None else None
    return _html("请完成业务系统验证", 200, verify_url=verify_url)
