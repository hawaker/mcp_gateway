"""从上游响应里取出 access_token，并把相对地址接到业务系统 base_url 上。

不发登录请求，不写 Redis，不执行管理员提交的脚本。
"""

import json
import pickle
import re
import select
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs

# 正则只看这么多正文，避免超长输入把匹配拖死。
REGEX_MAX_INPUT_LENGTH = 8192
# 匹配超过此时长就杀掉子进程。CPython 停不掉正在跑的 re.search。
REGEX_MATCH_TIMEOUT_SECONDS = 0.2
# 子进程起来再发这个字节，超时只计算其后的匹配，不算解释器启动。
_REGEX_READY = b"R"
_REGEX_STARTUP_TIMEOUT_SECONDS = 2.0

# 子进程只跑 re.search，不导入应用。先发就绪字节，再读模式和正文。
_REGEX_MATCH_SCRIPT = """\
import pickle
import re
import sys

sys.stdout.buffer.write(b"R")
sys.stdout.buffer.flush()
pattern, text = pickle.load(sys.stdin.buffer)
try:
    match = re.search(pattern, text)
except Exception as exc:
    pickle.dump(("error", type(exc).__name__), sys.stdout.buffer)
else:
    if match is None or match.lastindex is None:
        pickle.dump(("miss", None), sys.stdout.buffer)
    else:
        pickle.dump(("ok", match.group(1)), sys.stdout.buffer)
sys.stdout.buffer.flush()
"""

_BEARER_PREFIX = "Bearer "


class TokenExtractError(ValueError):
    """响应里没有按规则取出可用的 token 或有效期。"""


@dataclass(frozen=True, slots=True)
class TokenBundle:
    access_token: str
    expires_at: datetime
    token_type: str


def resolve_url(base_url: str, url: str) -> str:
    """http:// 或 https:// 原样使用，其余接到 base_url 上，保留 base 的路径。"""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    base = base_url[:-1] if base_url.endswith("/") else base_url
    relative = url if url.startswith("/") else f"/{url}"
    return f"{base}{relative}"


def extract_token(*, body: str, headers: Mapping[str, str], rule: Mapping[str, Any]) -> TokenBundle:
    source = str(rule.get("token_from") or "")
    token = _extract_value(
        body,
        headers,
        source,
        _optional_str(rule.get("token_name")),
        _optional_str(rule.get("cookie_name")),
    )
    if source == "header":
        token = _strip_bearer(token)
    if source != "text":
        token = token.strip()
    if not token:
        raise TokenExtractError("没有取到 token")
    token_type = str(rule.get("token_type") or "Bearer")
    return TokenBundle(access_token=token, expires_at=_expires_at(body, headers, rule), token_type=token_type)


def _expires_at(body: str, headers: Mapping[str, str], rule: Mapping[str, Any]) -> datetime:
    now = datetime.now(UTC)
    source = _optional_str(rule.get("expires_from"))
    raw: str | None = None
    if source:
        try:
            raw = _extract_value(
                body,
                headers,
                source,
                _optional_str(rule.get("expires_name")),
                _optional_str(rule.get("expires_cookie_name")) or _optional_str(rule.get("cookie_name")),
            )
        except TokenExtractError:
            raw = None
    if raw is None or not raw.strip():
        seconds = rule.get("expires_seconds")
        if seconds is None:
            raise TokenExtractError("缺少有效期")
        return now + timedelta(seconds=float(seconds))
    unit = _optional_str(rule.get("expires_unit")) or "seconds"
    if unit == "seconds":
        return now + timedelta(seconds=float(raw))
    if unit == "absolute":
        return _parse_absolute(raw)
    raise TokenExtractError("有效期单位无效")


def _extract_value(
    body: str,
    headers: Mapping[str, str],
    source: str,
    name: str | None,
    cookie_name: str | None,
) -> str:
    if source == "header":
        if not name:
            raise TokenExtractError("缺少响应头名称")
        raw = _header_value(headers, name)
        if name.lower() == "set-cookie":
            if not cookie_name:
                raise TokenExtractError("Set-Cookie 需要 cookie 名")
            return _cookie_value(raw, cookie_name)
        return raw
    if source == "json":
        if not name:
            raise TokenExtractError("缺少 JSON 路径")
        return _json_path(body, name)
    if source == "form":
        if not name:
            raise TokenExtractError("缺少表单字段名")
        return _form_field(body, name)
    if source == "text":
        if body == "":
            raise TokenExtractError("正文为空")
        return body
    if source == "regex":
        if not name:
            raise TokenExtractError("缺少正则")
        return _regex_group(name, body)
    raise TokenExtractError("不支持的取值来源")


def _header_value(headers: Mapping[str, str], name: str) -> str:
    if name in headers:
        return str(headers[name])
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return str(value)
    raise TokenExtractError(f"缺少响应头 {name}")


def _cookie_value(header_value: str, cookie_name: str) -> str:
    parts = re.split(r",(?=\s*[^;,\s]+=)", header_value)
    for part in parts:
        pair = part.split(";", 1)[0].strip()
        if "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        if key.strip() == cookie_name:
            return value.strip()
    raise TokenExtractError(f"Set-Cookie 中没有 {cookie_name}")


def _json_path(body: str, path: str) -> str:
    try:
        current: Any = json.loads(body)
    except json.JSONDecodeError as exc:
        raise TokenExtractError("响应正文不是 JSON") from exc
    for part in path.split("."):
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError) as exc:
                raise TokenExtractError("JSON 路径不存在") from exc
        elif isinstance(current, dict):
            if part not in current:
                raise TokenExtractError("JSON 路径不存在")
            current = current[part]
        else:
            raise TokenExtractError("JSON 路径不存在")
    if current is None or isinstance(current, (dict, list, bool)):
        raise TokenExtractError("JSON 取值不是标量")
    if isinstance(current, str):
        return current
    return str(current)


def _form_field(body: str, name: str) -> str:
    parsed = parse_qs(body, keep_blank_values=True)
    values = parsed.get(name)
    if not values or values[0] == "":
        raise TokenExtractError(f"表单中没有 {name}")
    return values[0]


def _regex_group(pattern: str, text: str) -> str:
    value = _regex_search(pattern, text)
    if not value:
        raise TokenExtractError("正则未取到 token")
    return value


def _regex_search(pattern: str, text: str) -> str | None:
    bounded = text[:REGEX_MAX_INPUT_LENGTH]
    try:
        re.compile(pattern)
    except re.error as exc:
        raise TokenExtractError("正则无效") from exc

    proc = subprocess.Popen(  # noqa: S603 — 解释器路径来自当前进程，参数是固定脚本，不走 shell
        [sys.executable, "-c", _REGEX_MATCH_SCRIPT],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    try:
        if proc.stdout is None or proc.stdin is None:
            raise TokenExtractError("正则无效")
        if not _wait_readable(proc.stdout, _REGEX_STARTUP_TIMEOUT_SECONDS):
            raise TokenExtractError("正则匹配超时")
        if proc.stdout.read(1) != _REGEX_READY:
            raise TokenExtractError("正则无效")
        proc.stdin.write(pickle.dumps((pattern, bounded)))
        proc.stdin.close()
        if not _wait_readable(proc.stdout, REGEX_MATCH_TIMEOUT_SECONDS):
            raise TokenExtractError("正则匹配超时")
        kind, value = pickle.load(proc.stdout)
    except (EOFError, pickle.UnpicklingError, OSError) as exc:
        raise TokenExtractError("正则无效") from exc
    finally:
        _finish_match_process(proc)
    if kind == "error":
        raise TokenExtractError("正则无效")
    if kind != "ok" or not isinstance(value, str) or value == "":
        return None
    return value


def _wait_readable(stream: Any, timeout: float) -> bool:
    readable, _, _ = select.select([stream], [], [], timeout)
    return bool(readable)


def _finish_match_process(proc: subprocess.Popen[bytes]) -> None:
    """超时或取值结束后收掉子进程，不留还在跑的 re.search。"""
    if proc.poll() is None:
        try:
            proc.terminate()
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=1)
    else:
        proc.wait(timeout=1)
    for stream in (proc.stdin, proc.stdout, proc.stderr):
        if stream is not None and not stream.closed:
            stream.close()


def _parse_absolute(value: str) -> datetime:
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise TokenExtractError("绝对时间无效") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _strip_bearer(value: str) -> str:
    if value.startswith(_BEARER_PREFIX):
        return value[len(_BEARER_PREFIX) :]
    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
