# 自定义鉴权多变量 captures Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** custom 鉴权从响应抽取多个命名变量写入 Redis 变量包，REST 用 `{{auth.xxx}}` 引用；删除 `{{token}}`。

**Architecture:** `TokenBundle` 改为 `{ vars, expires_at }`；`extract_captures` 按 rule.captures 填充 vars；AuthClient 渲染与业务注入改为整包 vars；REST assemble 用 `token_var` 生成 `{{auth.<token_var>}}`；前端 custom 表单式 captures 行编辑器。

**Tech Stack:** FastAPI、SQLAlchemy/Alembic、Redis、pytest、Vue 3 / Element Plus。

## Global Constraints

- Spec：`docs/superpowers/specs/2026-10-26-auth-captures-design.md`
- 仅 custom 配置多 captures；fixed/basic/interactive 仍单 token → `vars.access_token`
- 删除 `{{token}}`，无兼容别名；统一 `{{auth.键}}`
- `access_token` 非强制；整包固定 TTL，响应 expires_* 可选覆盖
- 旧 Redis JSON（仅 access_token）读时升为 vars；写入只写新格式
- 旧 custom rule（仅 token_from/token_name）读时升为单条 captures
- 测试：`cd backend && python -m pytest tests/mcp_gateway/<file>.py -v`

---

## File Structure

```
backend/app/modules/mcp_gateway/
  auth/extract.py          TokenBundle.vars + extract_captures / extract_token→vars
  auth/client.py           登录用 captures；渲染 {{auth.*}}；业务请求传 vars
  token_cache/store.py     dump/load 新格式；CachedBizToken 展示适配
  token_cache/schema.py    列表字段
  rest_tool/render.py      {{auth.x}}，去掉 token
  rest_tool/assemble.py    token_var → {{auth.*}}
  rest_tool/model.py       token_var 列
  rest_tool/schema.py      token_var
  rest_tool/service.py     字段白名单
  alembic/versions/<rev>_rest_tool_token_var.py
frontend/web/src/
  views/module_mcp_gateway/auth/index.vue
  views/module_mcp_gateway/rest_tool/index.vue
  views/module_mcp_gateway/token_cache/index.vue
  views/module_mcp_gateway/components/placeholderHelpContent.ts
  api/module_mcp_gateway/rest_tool.ts
  api/module_mcp_gateway/token_cache.ts
backend/tests/mcp_gateway/
  test_auth_extract.py / test_auth_captures.py (new or extend)
  test_token_cache.py
  test_auth_refresh.py
  test_rest_tool.py
```

---

### Task 1: TokenBundle + extract_captures

**Files:**
- Modify: `backend/app/modules/mcp_gateway/auth/extract.py`
- Modify: `backend/tests/mcp_gateway/test_auth_extract.py`
- Create or extend: `backend/tests/mcp_gateway/test_auth_captures.py`

**Interfaces:**
- Consumes: 现有 `_extract_value`、`_expires_at`
- Produces:
  - `TokenBundle(vars: dict[str, str], expires_at: datetime)`  
    - 兼容属性：`@property access_token -> vars.get("access_token") or ""`；`token_type` 固定 `"Bearer"` 或从 rule 忽略（不进 vars）
  - `extract_captures(*, body, headers, rule) -> TokenBundle`
  - `extract_token(...)` 改为内部调用单 token 路径后 `vars={"access_token": token}`（供 fixed/basic/interactive）
  - `normalize_captures(rule) -> list[dict]`：若有 `captures` 用它；否则从 `token_from`/`token_name` 升成一条 `access_token`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/mcp_gateway/test_auth_captures.py`：

```python
from datetime import UTC, datetime, timedelta

from app.modules.mcp_gateway.auth.extract import TokenBundle, extract_captures, normalize_captures


def test_normalize_legacy_token_fields_to_captures():
    assert normalize_captures({"token_from": "json", "token_name": "data.token"}) == [
        {"name": "access_token", "from": "json", "path": "data.token"}
    ]


def test_extract_captures_multiple_without_access_token():
    body = '{"a": "1", "b": "2"}'
    bundle = extract_captures(
        body=body,
        headers={},
        rule={
            "captures": [
                {"name": "tenant_id", "from": "json", "path": "a"},
                {"name": "session", "from": "json", "path": "b"},
            ],
            "expires_seconds": 60,
        },
    )
    assert bundle.vars == {"tenant_id": "1", "session": "2"}
    assert bundle.access_token == ""
    assert bundle.expires_at > datetime.now(UTC)


def test_extract_captures_requires_at_least_one():
    import pytest
    from app.modules.mcp_gateway.auth.extract import TokenExtractError

    with pytest.raises(TokenExtractError):
        extract_captures(body="{}", headers={}, rule={"captures": [], "expires_seconds": 30})
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && python -m pytest tests/mcp_gateway/test_auth_captures.py -v
```

Expected: FAIL（缺符号或旧 TokenBundle）

- [ ] **Step 3: 实现 extract**

在 `extract.py`：

1. 改 `TokenBundle`：

```python
@dataclass(frozen=True, slots=True)
class TokenBundle:
    vars: dict[str, str]
    expires_at: datetime

    @property
    def access_token(self) -> str:
        return self.vars.get("access_token") or ""

    @property
    def token_type(self) -> str:
        return "Bearer"
```

2. 实现 `normalize_captures` / `extract_captures`（循环 captures，复用 `_extract_value`；header 仍 strip Bearer；校验 name 正则 `^[A-Za-z0-9_]+$`、唯一、非空值）。

3. 改 `extract_token`：抽完后 `return TokenBundle(vars={"access_token": token}, expires_at=...,)`（去掉 token_type 构造参数）。

4. 修 `test_auth_extract.py` 里所有 `TokenBundle(access_token=..., expires_at=..., token_type=...)` 为新构造，或继续用 `extract_token` 断言 `bundle.access_token`。

- [ ] **Step 4: 跑测试通过**

```bash
cd backend && python -m pytest tests/mcp_gateway/test_auth_extract.py tests/mcp_gateway/test_auth_captures.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/mcp_gateway/auth/extract.py \
  backend/tests/mcp_gateway/test_auth_extract.py \
  backend/tests/mcp_gateway/test_auth_captures.py
git commit -m "$(cat <<'EOF'
feat: extract multiple auth captures into TokenBundle.vars

EOF
)"
```

---

### Task 2: Redis 变量包读写

**Files:**
- Modify: `backend/app/modules/mcp_gateway/token_cache/store.py`
- Modify: `backend/app/modules/mcp_gateway/token_cache/schema.py`
- Modify: `backend/app/modules/mcp_gateway/token_cache/controller.py`
- Modify: `backend/tests/mcp_gateway/test_token_cache.py`

**Interfaces:**
- Consumes: `TokenBundle.vars` / `expires_at`
- Produces:
  - `_dump` → `{"vars": {...}, "expires_at": iso}`
  - `_load`：若有 `vars` 用它；若仅有旧 `access_token` 则升为 `vars={"access_token": ...}`
  - `CachedBizToken`：增加 `vars: dict[str, str]`；`access_token` 可保留为摘要字段 `vars.get("access_token","")`

- [ ] **Step 1: 写失败测试**

```python
async def test_put_get_roundtrip_vars(cache):
    bundle = TokenBundle(
        vars={"access_token": "t1", "tenant_id": "9"},
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    await cache.put(1, 2, bundle)
    got = await cache.get(1, 2)
    assert got is not None
    assert got.vars == {"access_token": "t1", "tenant_id": "9"}


async def test_load_legacy_access_token_json(cache, redis):
    key = "mcp:biz-token:3:4"
    await redis.set(
        key,
        '{"access_token":"legacy","expires_at":"2099-01-01T00:00:00+00:00","token_type":"Bearer"}',
    )
    got = await cache.get(3, 4)
    assert got is not None
    assert got.vars == {"access_token": "legacy"}
```

（按现有 `test_token_cache.py` fixture 命名调整。）

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && python -m pytest tests/mcp_gateway/test_token_cache.py -v
```

- [ ] **Step 3: 实现 store**

更新 `_dump` / `_load` / `_row` / schema 列表字段（例如返回 `var_keys` 或完整 `vars` 遮罩由前端做）。controller 把 `vars` 键名或遮罩值返回。

- [ ] **Step 4: 跑测通过 + Commit**

```bash
cd backend && python -m pytest tests/mcp_gateway/test_token_cache.py -v
git add backend/app/modules/mcp_gateway/token_cache/ \
  backend/tests/mcp_gateway/test_token_cache.py
git commit -m "$(cat <<'EOF'
feat: store auth variable packs in Redis token cache

EOF
)"
```

---

### Task 3: AuthClient 登录 captures + `{{auth.*}}` 渲染

**Files:**
- Modify: `backend/app/modules/mcp_gateway/auth/client.py`
- Modify: `backend/tests/mcp_gateway/test_auth_refresh.py`
- Modify: `backend/tests/mcp_gateway/test_interactive_auth.py`（TokenBundle 构造）
- 其它引用 `TokenBundle(access_token=` 的测试一并改

**Interfaces:**
- Consumes: `extract_captures` / `extract_token` / `normalize_captures`
- Produces:
  - `_login()`：`method=="custom"` 用 `extract_captures`；否则 `extract_token`（结果已是 vars.access_token）
  - `_PLACEHOLDER` 改为含 `auth.(?P<auth>[A-Za-z0-9_]+)`，**去掉** `token`
  - `_replace` / `_render_text(..., auth_vars: Mapping[str,str] | None)`：登录时 `auth_vars=None`；业务请求传 `bundle.vars`
  - `_send_business(..., auth_vars: Mapping[str, str])`：不再传单个 token 字符串
  - `call` / interactive 路径改用 `bundle.vars`

- [ ] **Step 1: 更新/新增失败测试**

在 `test_auth_refresh.py`（或新文件）覆盖：

1. custom captures 两个字段，业务 Header `X-Tenant: {{auth.tenant_id}}`、`Authorization: Bearer {{auth.access_token}}` 均替换  
2. 登录 JSON 里写 `{{auth.access_token}}` **不得**被替换（仍原文）  
3. 模板里 `{{token}}` **不被**识别为占位符（保留原文 `{{token}}`）  
4. 401 后整包重登，新 vars 用于第二次请求  

把现有 `"Authorization": "Bearer {{token}}"` 全部改为 `{{auth.access_token}}`。

- [ ] **Step 2: 跑测确认相关失败**

```bash
cd backend && python -m pytest tests/mcp_gateway/test_auth_refresh.py -v
```

- [ ] **Step 3: 实现 client 改动**

要点：

```python
_PLACEHOLDER = re.compile(
    r"\{\{(?:system\.(?P<system>[A-Za-z0-9_]+)|user\.uid|user\.attr\.(?P<attr>[A-Za-z0-9_]+)|auth\.(?P<auth>[A-Za-z0-9_]+))\}\}"
)
```

`_login`：

```python
response = await self._request(...)
rule = self.auth.rule or {}
if self.auth.method == "custom":
    return extract_captures(body=response.text, headers=dict(response.headers), rule=rule)
return extract_token(body=response.text, headers=dict(response.headers), rule=rule)
```

业务发送用 `self._render_text(url, auth_vars=vars)` 等。

- [ ] **Step 4: 全量相关测通过**

```bash
cd backend && python -m pytest tests/mcp_gateway/test_auth_refresh.py tests/mcp_gateway/test_interactive_auth.py tests/mcp_gateway/test_auth_custom_request_shape.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/mcp_gateway/auth/client.py backend/tests/mcp_gateway/
git commit -m "$(cat <<'EOF'
feat: render {{auth.*}} from cached vars; custom multi-capture login

EOF
)"
```

---

### Task 4: REST assemble `token_var` + render.py + 迁移

**Files:**
- Modify: `backend/app/modules/mcp_gateway/rest_tool/assemble.py`
- Modify: `backend/app/modules/mcp_gateway/rest_tool/render.py`
- Modify: `backend/app/modules/mcp_gateway/rest_tool/model.py`
- Modify: `backend/app/modules/mcp_gateway/rest_tool/schema.py`
- Modify: `backend/app/modules/mcp_gateway/rest_tool/service.py`（`_WRITABLE` 加 `token_var`）
- Create: `backend/app/alembic/versions/<rev>_mcp_rest_tool_token_var.py`
- Modify: `backend/tests/mcp_gateway/test_rest_tool.py`

**Interfaces:**
- Consumes: `{{auth.键}}` 语法（与 client 一致）
- Produces:
  - `_place_token`：注入模板 `{{auth.<token_var>}}`，`token_var` 默认 `access_token`；Authorization 仍可 `Bearer {{auth.access_token}}`
  - `build_context(..., auth_vars: Mapping[str,str])` 替代 `token: str`
  - `render_placeholders` 支持 `auth.`，删除 `token`
  - DB 列 `token_var` nullable String(128)，默认逻辑在应用层 `"access_token"`

- [ ] **Step 1: 失败测试**

```python
def test_place_token_uses_auth_var():
    from app.modules.mcp_gateway.rest_tool.assemble import assemble_rest_request
    prepared = assemble_rest_request(
        {"url": "/x", "request_type": "GET", "token_in": "header", "token_name": "Authorization", "token_var": "session"},
        base_url="https://oa.example.com",
        arguments={},
    )
    assert prepared.headers["Authorization"] == "Bearer {{auth.session}}"


def test_render_auth_placeholder():
    from app.modules.mcp_gateway.rest_tool.render import build_context, render_placeholders
    ctx = build_context(system_params={}, uid="u", attrs={}, auth_vars={"session": "s1"}, arguments={})
    assert render_placeholders("S={{auth.session}} T={{token}}", ctx) == "S=s1 T={{token}}"
```

- [ ] **Step 2: 实现 + Alembic**

```python
# migration sketch
op.add_column("mcp_rest_tool", sa.Column("token_var", sa.String(128), nullable=True, comment="注入的 auth 变量名"))
```

更新 `assemble._place_token`、`render.py`、schema/model/service、测试里所有 `{{token}}` 期望。

- [ ] **Step 3: 跑测**

```bash
cd backend && python -m pytest tests/mcp_gateway/test_rest_tool.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/mcp_gateway/rest_tool/ \
  backend/app/alembic/versions/ \
  backend/tests/mcp_gateway/test_rest_tool.py
git commit -m "$(cat <<'EOF'
feat: inject REST credentials via {{auth.*}} and token_var

EOF
)"
```

---

### Task 5: 鉴权前端 captures 表单

**Files:**
- Modify: `frontend/web/src/views/module_mcp_gateway/auth/index.vue`
- Modify: `frontend/web/src/api/module_mcp_gateway/auth.ts`（若 payload 组装在此）
- Modify: `frontend/web/src/views/module_mcp_gateway/components/placeholderHelpContent.ts`

**Interfaces:**
- Consumes: rule JSON；`AUTH_PLACEHOLDER_HELP`
- Produces: custom 下 `capturesRows: { name, from, path }[]` 编辑器；提交时写入 `rule.captures`；回显时从 rule 读出（含 legacy 升成一行）

- [ ] **Step 1: 在 custom 对话框增加行编辑 UI**

在 `FaForm` 旁或 `rule_text` 上方（仅 `method==='custom'`）：

- `ElTable` / 动态行：`name`、`from`（select：json/header/form/text/regex）、`path`
- 按钮：添加行、删除行  
- `expires_seconds` 可用 number 输入，写入 rule  

提交前：

```ts
rule.captures = capturesRows.filter(r => r.name.trim()).map(...)
// 校验至少一个 name
// 其余 query/json/form/expires_* 仍从 rule_text 合并，或 rule_text 为「高级」不含 captures
```

推荐：`rule_text` 继续编辑 query/json/form/expires_*；保存时 `JSON.parse(rule_text)` 后覆盖 `captures` 与表单的 `expires_seconds`。

非 custom：隐藏行编辑器，行为与现有一致（rule_text 含 token_from）。

- [ ] **Step 2: 更新 AUTH 变量说明**

`placeholderHelpContent.ts`：

- 删除 `{{token}}` 行  
- 增加 `{{auth.xxx}}`（说明：登录请求不可用；custom 的 captures 写入缓存后供 REST）  
- usage 写明 custom 用「捕获变量」表单  

- [ ] **Step 3: 手动验收**

打开新增鉴权 → 选 custom → 添加两行 captures → 保存 → 编辑回显。

- [ ] **Step 4: Commit**

```bash
git add frontend/web/src/views/module_mcp_gateway/auth/index.vue \
  frontend/web/src/views/module_mcp_gateway/components/placeholderHelpContent.ts \
  frontend/web/src/api/module_mcp_gateway/auth.ts
git commit -m "$(cat <<'EOF'
feat: add captures row editor for custom auth configs

EOF
)"
```

---

### Task 6: REST / 缓存管理前端 + 说明

**Files:**
- Modify: `frontend/web/src/views/module_mcp_gateway/rest_tool/index.vue`
- Modify: `frontend/web/src/api/module_mcp_gateway/rest_tool.ts`
- Modify: `frontend/web/src/views/module_mcp_gateway/components/placeholderHelpContent.ts`（REST 段）
- Modify: `frontend/web/src/views/module_mcp_gateway/token_cache/index.vue`
- Modify: `frontend/web/src/api/module_mcp_gateway/token_cache.ts`

**Interfaces:**
- Consumes: `token_var` API 字段；缓存列表 `vars` / `var_keys`
- Produces: 表单「注入变量名」；REST 说明无 `{{token}}`；缓存表显示键名摘要

- [ ] **Step 1: REST 表单**

- `RestToolForm` / payload 增加 `token_var`（默认 `"access_token"`）  
- 对话框增加表单项「注入变量名」  
- headers placeholder：`可用 {{auth.access_token}}、{{user.uid}}`  
- `REST_PLACEHOLDER_HELP` 全面改为 `{{auth.*}}`

- [ ] **Step 2: Token 缓存页**

列：`变量键`（`Object.keys(vars).join(", ")`）、`expires_at`；可选展开遮罩值。去掉单独依赖 `access_token` 列或改为「主变量」摘要。

- [ ] **Step 3: 全库扫尾**

```bash
rg '\{\{token\}\}' frontend/web/src/views/module_mcp_gateway backend/app/modules/mcp_gateway
```

Expected: 无业务占位符用法（测试里断言「保留原文 {{token}}」除外）。

- [ ] **Step 4: 回归测**

```bash
cd backend && python -m pytest tests/mcp_gateway/ -v --tb=line
```

- [ ] **Step 5: Commit**

```bash
git add frontend/web/src/views/module_mcp_gateway/rest_tool/ \
  frontend/web/src/views/module_mcp_gateway/token_cache/ \
  frontend/web/src/views/module_mcp_gateway/components/placeholderHelpContent.ts \
  frontend/web/src/api/module_mcp_gateway/
git commit -m "$(cat <<'EOF'
feat: wire token_var and {{auth.*}} docs in REST and cache UI

EOF
)"
```

---

## Spec Coverage

| Spec | Task |
|------|------|
| TokenBundle vars + captures extract | 1 |
| Redis 新格式 / 旧读升级 | 2 |
| custom 多捕获登录、`{{auth.*}}`、去 `{{token}}`、401 | 3 |
| REST token_var + render | 4 |
| captures 表单编辑器 | 5 |
| REST/缓存 UI + 说明 | 6 |
| fixed/basic/interactive → vars.access_token | 1+3 |
| 不做每变量 TTL / 不做 {{token}} 兼容 | 全计划 |

## Self-Review

- 无 TBD；`token_var` / `vars` / `captures` 命名前后一致  
- `{{token}}` 仅允许在「不被替换」的负向测试中出现  
- Alembic 仅加 `token_var`；rule.captures 在 JSON 内无需迁移
