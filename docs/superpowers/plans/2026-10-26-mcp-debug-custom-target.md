# MCP 调试「自定义」目标 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在管理员 MCP 调试页增加 `target=custom`，用自由 URL / Header / 传输方式出站调试任意 MCP，不写调用日志。

**Architecture:** 扩展现有 `DebugTargetSchema` 与 `DebugService._rpc`：新增 `_custom_rpc`，用注入的 `httpx` transport 对用户 URL 发 JSON-RPC（Streamable HTTP）或 GET SSE + POST endpoint（SSE）。遮罩来自自定义 Header 中的疑似凭证。前端调试页增加第三种目标与键值 Header 行。权限码与三接口路径不变。

**Tech Stack:** FastAPI、Pydantic、httpx、pytest、Vue 3 + Element Plus（`frontend/web`）

## Global Constraints

- URL 必须以 `http://` 或 `https://` 开头（复用 `require_http_url`）。
- `transport` 只能是 `streamable_http` 或 `sse`。
- 自定义目标不写 MCP 调用日志（与上游调试一致）。
- 不落库 URL / Header；不绑组 / 用户 / 上游。
- 不做 IP / 内网黑名单；依赖现有 `module_mcp_gateway:debug:*` 权限。
- 不新增权限码；不改 `/mcp/{group_id}` 运行时。
- 操作日志继续省略 debug 请求体（现有 `OperationLogRoute`）。
- 中文错误信息；超时约 30s。

**Spec:** `docs/superpowers/specs/2026-10-26-mcp-debug-custom-target-design.md`

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `backend/app/modules/mcp_gateway/runtime/debug.py` | Schema 扩展、`_custom_rpc`、出站 streamable/SSE、secrets 收集 |
| `backend/app/modules/mcp_gateway/runtime/debug_controller.py` | 把 `url` / `headers` 透传给 `DebugService` |
| `backend/tests/mcp_gateway/test_mcp_debug.py` | Schema + custom streamable/SSE/遮罩/无 call log |
| `frontend/web/src/api/module_mcp_gateway/debug.ts` | 类型增加 `custom` / `url` / `headers` |
| `frontend/web/src/views/module_mcp_gateway/debug/index.vue` | 「自定义」UI 与 `buildTarget` |

测试命令：

```bash
cd backend && python -m pytest tests/mcp_gateway/test_mcp_debug.py -v
```

---

### Task 1: Schema 与 custom Streamable HTTP

**Files:**
- Modify: `backend/app/modules/mcp_gateway/runtime/debug.py`
- Modify: `backend/app/modules/mcp_gateway/runtime/debug_controller.py`
- Modify: `backend/tests/mcp_gateway/test_mcp_debug.py`

**Interfaces:**
- Consumes: `require_http_url`、`_Exchange`、`_views`、`_borrow`、`_decode_response` / `_decode_bytes`
- Produces:
  - `DebugTargetSchema` 支持 `target="custom"`，字段 `url: str | None`、`headers: dict[str, str]`（默认 `{}`）、必填 `transport`
  - `DebugService.session|tools_list|tools_call` 接受 `url` / `headers` 并传入 `_rpc`
  - `_custom_header_secrets(headers: Mapping[str, str]) -> tuple[str, ...]`
  - `_merge_custom_headers(user: Mapping[str, str], *, for_sse_get: bool = False) -> dict[str, str]`

- [ ] **Step 1: 写失败测试（schema + streamable session / call / 无日志 / 遮罩）**

在 `backend/tests/mcp_gateway/test_mcp_debug.py` 追加：

```python
def test_debug_target_schema_accepts_custom() -> None:
    from app.modules.mcp_gateway.runtime.debug import DebugTargetSchema
    from pydantic import ValidationError

    ok = DebugTargetSchema(
        target="custom",
        url="https://mcp.example.com/mcp",
        transport="streamable_http",
        headers={"Authorization": "Bearer secret-token"},
    )
    assert ok.url == "https://mcp.example.com/mcp"
    assert ok.headers["Authorization"] == "Bearer secret-token"

    with pytest.raises(ValidationError):
        DebugTargetSchema(target="custom", transport="streamable_http")
    with pytest.raises(ValidationError):
        DebugTargetSchema(target="custom", url="https://mcp.example.com/mcp")
    with pytest.raises(ValidationError):
        DebugTargetSchema(
            target="custom",
            url="ftp://mcp.example.com/mcp",
            transport="streamable_http",
        )


async def test_custom_debug_streamable_without_call_log(db) -> None:
    secret = "Bearer custom-debug-secret"

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://custom.example.com/mcp"
        assert request.headers.get("authorization") == secret
        body = json.loads(request.content.decode())
        method = body.get("method")
        if method == "initialize":
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "result": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "custom-mcp", "version": "1.0"},
                    },
                },
            )
        if method == "tools/list":
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "result": {"tools": [{"name": "ping", "inputSchema": {"type": "object"}}]},
                },
            )
        if method == "tools/call":
            assert body["params"]["name"] == "ping"
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "result": {"content": [{"type": "text", "text": "pong"}]},
                },
            )
        return httpx.Response(500, text=f"unexpected {method}")

    service = _service(db, ExpiringRedis(), httpx.MockTransport(handler))
    common = dict(
        target="custom",
        url="https://custom.example.com/mcp",
        transport="streamable_http",
        headers={"Authorization": secret},
    )

    session = await service.session(**common)
    assert session.server_info["name"] == "custom-mcp"
    assert "custom-debug-secret" not in _blob(session.network)
    assert _MASK in _blob(session.network)

    listed = await service.tools_list(**common)
    assert [item["name"] for item in listed.tools] == ["ping"]

    called = await service.tools_call(**common, name="ping", arguments={})
    assert called.result_text == "pong"
    assert await _rows(db) == []

    revealed = await service.session(**common, reveal=True)
    assert "custom-debug-secret" in _blob(revealed.network)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/mcp_gateway/test_mcp_debug.py::test_debug_target_schema_accepts_custom tests/mcp_gateway/test_mcp_debug.py::test_custom_debug_streamable_without_call_log -v`

Expected: FAIL（`target` 仍只允许 group/upstream，或 `url` 参数未被接受）

- [ ] **Step 3: 扩展 Schema**

在 `debug.py` 的 `DebugTargetSchema`：

```python
class DebugTargetSchema(BaseModel):
    target: str = Field(description="group、upstream 或 custom")
    group_id: int | None = Field(default=None, description="MCP 组 ID")
    user_id: int | None = Field(default=None, description="业务用户 ID")
    transport: str | None = Field(default=None, description="streamable_http 或 sse")
    upstream_id: int | None = Field(default=None, description="上游 MCP ID")
    url: str | None = Field(default=None, description="自定义 MCP URL")
    headers: dict[str, str] = Field(default_factory=dict, description="自定义请求头")
    reveal: bool = Field(default=False, description="为真时不遮住 token")

    @model_validator(mode="after")
    def _check(self) -> DebugTargetSchema:
        if self.target == "group":
            if self.group_id is None or self.user_id is None:
                raise ValueError("调试 MCP 组需要 group_id 和 user_id")
            if self.transport not in _TRANSPORTS:
                raise ValueError("传输只能是 streamable_http 或 sse")
            return self
        if self.target == "upstream":
            if self.upstream_id is None:
                raise ValueError("调试上游需要 upstream_id")
            return self
        if self.target == "custom":
            if not self.url:
                raise ValueError("调试自定义目标需要 url")
            require_http_url(self.url)
            if self.transport not in _TRANSPORTS:
                raise ValueError("传输只能是 streamable_http 或 sse")
            return self
        raise ValueError("target 只能是 group、upstream 或 custom")
```

- [ ] **Step 4: 实现 secrets / header 合并 / `_custom_rpc`（先 streamable）**

同文件追加：

```python
_SECRET_HEADER_MARKERS = ("token", "secret", "key", "password")


def _custom_header_secrets(headers: Mapping[str, str]) -> tuple[str, ...]:
    secrets: list[str] = []
    for name, value in headers.items():
        if not value:
            continue
        lowered = name.lower()
        if lowered == "authorization" or any(marker in lowered for marker in _SECRET_HEADER_MARKERS):
            secrets.append(value)
    return tuple(dict.fromkeys(secrets))


def _merge_custom_headers(
    user: Mapping[str, str],
    *,
    for_sse_get: bool = False,
) -> dict[str, str]:
    merged = {str(k): str(v) for k, v in user.items() if k}
    if for_sse_get:
        merged.setdefault("Accept", "text/event-stream")
    else:
        merged.setdefault("Content-Type", "application/json")
        merged.setdefault("Accept", "application/json, text/event-stream")
    return merged
```

在 `DebugService` 的 `session` / `tools_list` / `tools_call` 增加参数 `url: str | None = None`、`headers: Mapping[str, str] | None = None`，构造 Schema 时传入 `url=url`、`headers=dict(headers or {})`。

`_rpc` 改为：

```python
async def _rpc(self, data: DebugTargetSchema, method: str, params: dict[str, Any]) -> _Exchange:
    if data.target == "group":
        assert data.group_id is not None and data.user_id is not None and data.transport is not None
        return await self._group_rpc(data.group_id, data.user_id, data.transport, method, params)
    if data.target == "upstream":
        assert data.upstream_id is not None
        return await self._upstream_rpc(data.upstream_id, method, params)
    assert data.url is not None and data.transport is not None
    return await self._custom_rpc(data.url, data.headers, data.transport, method, params)
```

新增：

```python
async def _custom_rpc(
    self,
    url: str,
    headers: Mapping[str, str],
    transport: str,
    method: str,
    params: dict[str, Any],
) -> _Exchange:
    target_url = require_http_url(url)
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    if transport == "streamable_http":
        exchange = await self._custom_streamable(target_url, headers, payload)
    elif transport == "sse":
        exchange = await self._custom_sse(target_url, headers, payload)
    else:
        raise CustomException(msg="传输只能是 streamable_http 或 sse")
    secrets = _custom_header_secrets(headers)
    return _Exchange(
        status=exchange.status,
        request_headers=exchange.request_headers,
        request_body=exchange.request_body,
        response_body=exchange.response_body,
        secrets=secrets,
    )


async def _custom_streamable(
    self,
    url: str,
    headers: Mapping[str, str],
    payload: dict[str, Any],
) -> _Exchange:
    sent = _merge_custom_headers(headers)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    client = httpx.AsyncClient(transport=_borrow(self.transport), timeout=30.0)
    try:
        response = await client.post(url, content=body, headers=sent)
        return _Exchange(
            status=response.status_code,
            request_headers=dict(sent),
            request_body=payload,
            response_body=_decode_response(response),
            secrets=(),
        )
    finally:
        await client.aclose()


async def _custom_sse(
    self,
    url: str,
    headers: Mapping[str, str],
    payload: dict[str, Any],
) -> _Exchange:
    raise CustomException(msg="自定义 SSE 尚未实现")  # Task 2 替换
```

- [ ] **Step 5: Controller 透传**

`debug_controller.py` 三处调用改为传入：

```python
url=data.url,
headers=data.headers,
```

`session` / `tools_list` / `tools_call` 均加这两行。

- [ ] **Step 6: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/mcp_gateway/test_mcp_debug.py::test_debug_target_schema_accepts_custom tests/mcp_gateway/test_mcp_debug.py::test_custom_debug_streamable_without_call_log tests/mcp_gateway/test_mcp_debug.py::test_upstream_debug_uses_credential_without_call_log -v`

Expected: PASS（含既有上游回归）

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/mcp_gateway/runtime/debug.py \
  backend/app/modules/mcp_gateway/runtime/debug_controller.py \
  backend/tests/mcp_gateway/test_mcp_debug.py
git commit -m "$(cat <<'EOF'
feat: add custom streamable MCP debug target

EOF
)"
```

---

### Task 2: 自定义 SSE 出站

**Files:**
- Modify: `backend/app/modules/mcp_gateway/runtime/debug.py`
- Modify: `backend/tests/mcp_gateway/test_mcp_debug.py`

**Interfaces:**
- Consumes: Task 1 的 `_custom_rpc` / `_merge_custom_headers` / `_borrow`
- Produces: `_custom_sse(url, headers, payload) -> _Exchange`；相对 `endpoint` 用 `urllib.parse.urljoin` 相对原 `url` 解析

- [ ] **Step 1: 写失败测试**

```python
async def test_custom_debug_sse_initialize(db) -> None:
    """自定义 SSE：GET 拿 endpoint，POST 后收 message。"""
    secret = "sse-custom-token"
    posts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            assert str(request.url) == "https://sse.example.com/sse"
            assert request.headers.get("x-api-key") == secret
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=b"event: endpoint\ndata: /messages\n\n",
            )
        assert request.method == "POST"
        assert str(request.url) == "https://sse.example.com/messages"
        posts.append(request.content.decode())
        body = json.loads(request.content.decode())
        assert body["method"] == "initialize"
        message = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "serverInfo": {"name": "sse-custom", "version": "0.1"},
                },
            }
        ).encode()
        # MockTransport 对同一连接无法真正推送第二段 SSE；实现应在 POST 响应里带回 JSON，
        # 或在 GET 流关闭前已缓冲 message。本测试约定：若实现从 POST JSON 取结果亦可。
        return httpx.Response(200, json=json.loads(message))

    service = _service(db, ExpiringRedis(), httpx.MockTransport(handler))
    session = await service.session(
        target="custom",
        url="https://sse.example.com/sse",
        transport="sse",
        headers={"X-Api-Key": secret},
    )
    assert session.server_info["name"] == "sse-custom"
    assert secret not in _blob(session.network)
    assert posts, "应向 endpoint POST initialize"
```

说明：真实 MCP SSE 在 GET 流上推 `message`；`httpx.MockTransport` 很难模拟长连接推送。实现允许：

1. 优先：GET 流上读 `endpoint`，POST 后若 POST 响应已是 JSON-RPC 结果则直接用；
2. 若 POST 为 202 且 body 空，再尝试从 GET 流读 `message`（真实服务器路径）。

测试上面用 POST 直接返回 JSON，覆盖路径 (1)。另加一个纯单元级小测确认 `urljoin`：endpoint=`/messages` + base=`https://sse.example.com/sse` → `https://sse.example.com/messages`（可内嵌在同一测试的 assert URL 中，不必单独函数）。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/mcp_gateway/test_mcp_debug.py::test_custom_debug_sse_initialize -v`

Expected: FAIL with「自定义 SSE 尚未实现」或等价

- [ ] **Step 3: 实现 `_custom_sse`**

替换 Task 1 占位。建议结构（可用 `_OpenHttpSse` 小类，或 `client.stream` + 缓冲解析，与 `_OpenSse.next_event` 同类行解析）：

```python
async def _custom_sse(
    self,
    url: str,
    headers: Mapping[str, str],
    payload: dict[str, Any],
) -> _Exchange:
    from urllib.parse import urljoin

    get_headers = _merge_custom_headers(headers, for_sse_get=True)
    post_headers = _merge_custom_headers(headers)
    client = httpx.AsyncClient(transport=_borrow(self.transport), timeout=30.0)
    try:
        async with client.stream("GET", url, headers=get_headers) as stream:
            if stream.status_code != 200:
                body = await stream.aread()
                return _Exchange(
                    stream.status_code,
                    dict(get_headers),
                    payload,
                    _decode_bytes(body),
                    (),
                )
            event, endpoint = await _read_sse_event(stream)
            if event != "endpoint" or not endpoint:
                raise CustomException(msg="SSE 未返回 endpoint")
            post_url = urljoin(url, endpoint)
            posted = await client.post(post_url, headers=post_headers, json=payload)
            if posted.status_code not in {200, 202}:
                return _Exchange(
                    posted.status_code,
                    dict(post_headers),
                    payload,
                    _decode_response(posted),
                    (),
                )
            decoded = _decode_response(posted)
            if isinstance(decoded, dict) and ("result" in decoded or "error" in decoded):
                return _Exchange(posted.status_code, dict(post_headers), payload, decoded, ())
            message_event, message = await _read_sse_event(stream)
            if message_event != "message":
                raise CustomException(msg="SSE 未返回 message")
            try:
                body_any: Any = json.loads(message)
            except json.JSONDecodeError:
                body_any = message
            return _Exchange(posted.status_code, dict(post_headers), payload, body_any, ())
    finally:
        await client.aclose()


async def _read_sse_event(stream: httpx.Response) -> tuple[str, str]:
    buffer = ""
    async for chunk in stream.aiter_text():
        buffer += chunk
        while "\n\n" in buffer:
            raw, buffer = buffer.split("\n\n", 1)
            event = "message"
            data: list[str] = []
            for line in raw.split("\n"):
                if line.startswith("event:"):
                    event = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data.append(line.split(":", 1)[1].lstrip())
            return event, "\n".join(data)
    raise CustomException(msg="SSE 流已关闭")
```

若 `aiter_text` 在 MockTransport 下一次吐完整 body，上述循环仍能解析第一个事件；POST 返回 JSON 时走短路，无需第二条 SSE。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/mcp_gateway/test_mcp_debug.py -v -k 'custom_debug or debug_target_schema'`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/mcp_gateway/runtime/debug.py \
  backend/tests/mcp_gateway/test_mcp_debug.py
git commit -m "$(cat <<'EOF'
feat: support SSE for custom MCP debug target

EOF
)"
```

---

### Task 3: 前端类型与调试页

**Files:**
- Modify: `frontend/web/src/api/module_mcp_gateway/debug.ts`
- Modify: `frontend/web/src/views/module_mcp_gateway/debug/index.vue`

**Interfaces:**
- Consumes: Task 1–2 后端字段 `url` / `headers` / `transport` / `target=custom`
- Produces: `McpDebugTargetKind` 含 `"custom"`；页面可连接自定义目标

- [ ] **Step 1: 扩展 API 类型**

`debug.ts`：

```typescript
export type McpDebugTargetKind = "group" | "upstream" | "custom";

export interface McpDebugTarget {
  target: McpDebugTargetKind;
  group_id?: number;
  user_id?: number;
  transport?: McpDebugTransport;
  upstream_id?: number;
  url?: string;
  headers?: Record<string, string>;
  reveal?: boolean;
}
```

- [ ] **Step 2: 更新调试页 UI 与 `buildTarget`**

在目标 Radio 增加：

```vue
<ElRadioButton value="custom">自定义</ElRadioButton>
```

将现有 `v-else`（上游）改为 `v-else-if="target === 'upstream'"`，并增加 `v-else-if="target === 'custom'"` 块：

```vue
<template v-else-if="target === 'custom'">
  <div class="mcp-debug__row">
    <span class="mcp-debug__label">URL</span>
    <ElInput v-model="customUrl" clearable placeholder="https://..." class="mcp-debug__control" />
  </div>
  <div class="mcp-debug__row">
    <span class="mcp-debug__label">传输</span>
    <ElRadioGroup v-model="transport">
      <ElRadioButton value="streamable_http">Streamable HTTP</ElRadioButton>
      <ElRadioButton value="sse">SSE</ElRadioButton>
    </ElRadioGroup>
  </div>
  <div class="mcp-debug__row mcp-debug__headers">
    <span class="mcp-debug__label">Header</span>
    <div class="flex flex-col gap-2 flex-1">
      <div v-for="(row, index) in headerRows" :key="index" class="flex gap-2 items-center flex-wrap">
        <ElInput v-model="row.key" placeholder="名称" class="mcp-debug__header-key" />
        <ElInput v-model="row.value" placeholder="值" class="mcp-debug__header-value" />
        <ElButton text type="danger" @click="headerRows.splice(index, 1)">删除</ElButton>
      </div>
      <ElButton plain @click="headerRows.push({ key: '', value: '' })">添加 Header</ElButton>
    </div>
  </div>
</template>
```

script 增加：

```typescript
const customUrl = ref("");
const headerRows = ref<{ key: string; value: string }[]>([{ key: "", value: "" }]);

function buildCustomHeaders(): Record<string, string> {
  const out: Record<string, string> = {};
  for (const row of headerRows.value) {
    const key = row.key.trim();
    if (!key) continue;
    out[key] = row.value;
  }
  return out;
}
```

`buildTarget` 完整逻辑：

```typescript
function buildTarget(): McpDebugTarget | null {
  if (target.value === "group") {
    if (!groupId.value || !userId.value) {
      ElMessage.warning("请选择 MCP 组和业务用户");
      return null;
    }
    return {
      target: "group",
      group_id: groupId.value,
      user_id: userId.value,
      transport: transport.value,
      reveal: reveal.value,
    };
  }
  if (target.value === "upstream") {
    if (!upstreamId.value) {
      ElMessage.warning("请选择上游 MCP");
      return null;
    }
    return {
      target: "upstream",
      upstream_id: upstreamId.value,
      reveal: reveal.value,
    };
  }
  if (!customUrl.value.trim()) {
    ElMessage.warning("请填写 MCP URL");
    return null;
  }
  return {
    target: "custom",
    url: customUrl.value.trim(),
    headers: buildCustomHeaders(),
    transport: transport.value,
    reveal: reveal.value,
  };
}
```

`watch(target)` 保持清空连接态即可（不必清空 URL，方便来回切换）。

样式可加：

```css
.mcp-debug__header-key {
  min-width: 140px;
  max-width: 200px;
}
.mcp-debug__header-value {
  min-width: 200px;
  max-width: 360px;
}
```

- [ ] **Step 3: 手动验收清单（实现者勾选）**

1. 打开调试页，选「自定义」，填可达 MCP URL + Header，Streamable HTTP 连接成功并显示 serverInfo  
2. tools/list、tools/call 可用；默认 Network 遮 Authorization；勾选「显示 token」可见明文  
3. 切换 SSE（若有可达 SSE MCP）可连接  
4. 组 / 上游调试仍可用  
5. 自定义 tools/call 后调用日志列表无新记录  

- [ ] **Step 4: Commit**

```bash
git add frontend/web/src/api/module_mcp_gateway/debug.ts \
  frontend/web/src/views/module_mcp_gateway/debug/index.vue
git commit -m "$(cat <<'EOF'
feat: add custom target UI to MCP debug page

EOF
)"
```

---

## Spec coverage（自检）

| Spec 要求 | Task |
|-----------|------|
| `target=custom` + url/headers/transport | 1, 3 |
| Streamable HTTP + SSE | 1, 2 |
| 不写调用日志 | 1 |
| `require_http_url` / 仅 http(s) | 1 |
| Protocol/Network + reveal 遮罩 | 1 |
| 权限码不变、三接口复用 | 1（controller） |
| 前端键值 Header、清空连接态 | 3 |
| 组/上游行为不变 | 1 回归 + 3 手动 |
| 不做落库 / 黑名单 | 全任务 YAGNI |

无 TBD / 占位实现步骤（Task 1 的 `_custom_sse` 占位由 Task 2 在同文件内替换，测试门禁明确）。
