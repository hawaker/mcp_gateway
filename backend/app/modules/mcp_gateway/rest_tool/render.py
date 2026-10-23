"""占位符只认系统参数、用户标识和业务 token。调用参数放在 args 里，不能覆盖它们。"""

import re
from collections.abc import Mapping
from typing import Any

# 只认这四种。调用参数里的同名值不参与替换。
_PLACEHOLDER = re.compile(r"\{\{(?:system\.(?P<system>[A-Za-z0-9_]+)|user\.uid|user\.attr\.(?P<attr>[A-Za-z0-9_]+)|token)\}\}")


def build_context(
    *,
    system_params: Mapping[str, Any],
    uid: str,
    attrs: Mapping[str, Any],
    token: str,
    arguments: Mapping[str, Any],
) -> dict[str, Any]:
    """业务 token 始终用传入的 token。arguments 原样放在 args，即使里面也有 token。"""
    return {
        "system": dict(system_params),
        "user": {"uid": uid, "attr": dict(attrs)},
        "token": token,
        "args": dict(arguments),
    }


def render_placeholders(template: str, ctx: Mapping[str, Any]) -> str:
    """替换 {{system.xxx}}、{{user.uid}}、{{user.attr.xxx}}、{{token}}。不读 ctx['args']。"""
    return _PLACEHOLDER.sub(lambda match: _replace(match, ctx), template)


def _replace(match: re.Match[str], ctx: Mapping[str, Any]) -> str:
    system_key = match.group("system")
    if system_key is not None:
        system = ctx.get("system") or {}
        if not isinstance(system, Mapping) or system_key not in system:
            return match.group(0)
        return _as_text(system[system_key])
    attr_key = match.group("attr")
    if attr_key is not None:
        user = ctx.get("user") or {}
        attrs = user.get("attr") if isinstance(user, Mapping) else None
        if not isinstance(attrs, Mapping) or attr_key not in attrs:
            return match.group(0)
        return _as_text(attrs[attr_key])
    if match.group(0) == "{{user.uid}}":
        user = ctx.get("user") or {}
        if not isinstance(user, Mapping) or user.get("uid") is None:
            return match.group(0)
        return _as_text(user.get("uid"))
    if match.group(0) == "{{token}}":
        if ctx.get("token") is None:
            return match.group(0)
        return _as_text(ctx.get("token"))
    return match.group(0)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
