# 鉴权自定义请求 Header / Body 类型 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让鉴权方法「自定义请求」可用键值对编辑 Header 与 Query，可选 Body 类型（none/json/form）并按类型编辑 Body；取值规则只保留响应取值。

**Architecture:** 在 `mcp_biz_auth_config` 增加 `headers` / `query` / `body_type` / `body` 列；schema 校验 custom；`AuthClient._login_request` 对 custom 只读新字段，basic 仍读 `rule`；Alembic 迁移旧 `rule` 请求段；前端用 `KeyValueRows` + FaForm 插槽。

**Tech Stack:** FastAPI / SQLAlchemy / Pydantic / Alembic、httpx、pytest、Vue 3、Element Plus、现有 `FaForm` 具名插槽。

## Global Constraints

- Spec：`docs/superpowers/specs/2026-10-26-auth-custom-request-headers-body-design.md`
- 仅 `method === custom` 使用新字段；basic / fixed / interactive 不改 UI；basic 登录仍读 `rule.query|json|form`
- Body 类型只支持 `none` | `json` | `form`
- Header UI 仅键值对行，不要 JSON 双模式
- 占位符：`{{system.xxx}}` / `{{user.uid}}` / `{{user.attr.xxx}}`；鉴权登录不依赖 `{{token}}`
- 提交信息用英文 `feat:` / `test:` / `docs:` 前缀
- 迁移 `down_revision`：以 `cd backend && uv run alembic heads` 当前 tip 为准（工作区 tip 预期为 `9a7ebe570526`）

---

## File Structure

```
backend/app/modules/mcp_gateway/auth/
  model.py              # 新列
  schema.py             # 字段 + custom 校验 + lift 辅助
  service.py            # create/update 落库；非 custom 清空新字段
  client.py             # custom 登录拼装读新字段；读时 lift 兜底
  migrate_rule.py       # NEW: rule → 新字段纯函数（迁移与读时共用）

backend/app/alembic/versions/
  2026_10_26_XXXX_<rev>_auth_custom_request_shape.py

backend/tests/mcp_gateway/
  test_auth_custom_request_shape.py   # NEW: schema / lift
  test_auth_config.py                 # create/detail 含新字段
  test_auth_refresh.py                # custom 登录改用新字段；basic 仍用 rule

frontend/web/src/views/module_mcp_gateway/components/
  KeyValueRows.vue                    # NEW: 键值对行编辑

frontend/web/src/api/module_mcp_gateway/auth.ts
frontend/web/src/views/module_mcp_gateway/auth/index.vue
frontend/web/src/views/module_mcp_gateway/components/placeholderHelpContent.ts
```

---

### Task 1: `lift_custom_request_from_rule` 与 schema 校验

**Files:**
- Create: `backend/app/modules/mcp_gateway/auth/migrate_rule.py`
- Modify: `backend/app/modules/mcp_gateway/auth/schema.py`
- Create: `backend/tests/mcp_gateway/test_auth_custom_request_shape.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `BodyType = Literal["none", "json", "form"]`
  - `def lift_custom_request_from_rule(rule: dict[str, Any]) -> tuple[dict[str, str] | None, dict[str, str] | None, BodyType, dict[str, Any] | None, dict[str, Any]]`
    - 返回 `(headers, query, body_type, body, rule_without_request_keys)`
    - 若有 `form` → body_type=`form`，body=form map；否则若有 `json` → `json`；否则 `none` / `None`
    - 从 rule 副本删除 `query`/`json`/`form`/`headers`
  - `def ensure_custom_request_fields(method, headers, query, body_type, body) -> None` — custom 时校验；非 custom 直接 return
  - Create/Update/Out schema 增加可选字段：`headers: dict[str, str] | None`、`query: dict[str, str] | None`、`body_type: BodyType | None`、`body: dict[str, Any] | None`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/mcp_gateway/test_auth_custom_request_shape.py`：

```python
import pytest
from pydantic import ValidationError

from app.modules.mcp_gateway.auth.migrate_rule import lift_custom_request_from_rule
from app.modules.mcp_gateway.auth.schema import AuthConfigCreateSchema


def test_lift_prefers_form_over_json_and_strips_request_keys() -> None:
    rule = {
        "query": {"q": "{{user.uid}}"},
        "json": {"a": "1"},
        "form": {"b": "2"},
        "headers": {"X-App": "{{system.app}}"},
        "token_from": "json",
        "token_name": "token",
    }
    headers, query, body_type, body, cleaned = lift_custom_request_from_rule(rule)
    assert headers == {"X-App": "{{system.app}}"}
    assert query == {"q": "{{user.uid}}"}
    assert body_type == "form"
    assert body == {"b": "2"}
    assert cleaned == {"token_from": "json", "token_name": "token"}
    assert "query" not in cleaned


def test_lift_none_when_no_body_sections() -> None:
    headers, query, body_type, body, cleaned = lift_custom_request_from_rule({"token_from": "text"})
    assert headers is None
    assert query is None
    assert body_type == "none"
    assert body is None
    assert cleaned == {"token_from": "text"}


def test_create_custom_rejects_json_body_type_with_null_body() -> None:
    with pytest.raises((ValidationError, ValueError)):
        AuthConfigCreateSchema(
            system_id=1,
            method="custom",
            url="https://oa.example.com/login",
            rule={"token_from": "json", "token_name": "t"},
            http_method="POST",
            body_type="json",
            body=None,
        )


def test_create_custom_accepts_none_body() -> None:
    data = AuthConfigCreateSchema(
        system_id=1,
        method="custom",
        url="https://oa.example.com/login",
        rule={"token_from": "json", "token_name": "t"},
        http_method="POST",
        body_type="none",
        body=None,
        headers={"X-Key": "{{user.uid}}"},
        query={"id": "{{user.uid}}"},
    )
    assert data.body_type == "none"
    assert data.headers == {"X-Key": "{{user.uid}}"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/mcp_gateway/test_auth_custom_request_shape.py -v`

Expected: FAIL（模块或字段不存在）

- [ ] **Step 3: 实现 migrate_rule + schema**

`migrate_rule.py`：

```python
from typing import Any, Literal

BodyType = Literal["none", "json", "form"]
_REQUEST_KEYS = ("query", "json", "form", "headers")


def _str_map(raw: Any) -> dict[str, str] | None:
    if not isinstance(raw, dict) or not raw:
        return None
    return {str(k): "" if v is None else str(v) for k, v in raw.items() if str(k).strip()}


def lift_custom_request_from_rule(
    rule: dict[str, Any],
) -> tuple[dict[str, str] | None, dict[str, str] | None, BodyType, dict[str, Any] | None, dict[str, Any]]:
    cleaned = {k: v for k, v in rule.items() if k not in _REQUEST_KEYS}
    headers = _str_map(rule.get("headers"))
    query = _str_map(rule.get("query"))
    form = _str_map(rule.get("form"))
    raw_json = rule.get("json")
    if form is not None:
        return headers, query, "form", form, cleaned
    if isinstance(raw_json, dict):
        return headers, query, "json", dict(raw_json), cleaned
    return headers, query, "none", None, cleaned
```

在 `schema.py`：

- 增加 `BodyType`（可从 migrate_rule 再导出，或本地 Literal 与之一致）
- Create/Update/Out 增加四个字段（Update 全可选；Create 的 `body_type` 对 custom 默认可用 `None`，在 validator 里：custom 且未传则视为 `none`）
- `model_validator` 调用 `ensure_custom_request_fields`：
  - 非 custom：return
  - custom：`body_type` 缺省按 `none`
  - `none` → body 必须 `None` 或 `{}`（规范成 `None`）
  - `json` → body 必须为 `dict`（非 list）
  - `form` → body 必须为 `dict`，值转为 str
  - headers/query 若提供须为 `dict[str,str]`（空 key 拒绝）

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/mcp_gateway/test_auth_custom_request_shape.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/mcp_gateway/auth/migrate_rule.py \
  backend/app/modules/mcp_gateway/auth/schema.py \
  backend/tests/mcp_gateway/test_auth_custom_request_shape.py
git commit -m "$(cat <<'EOF'
feat: validate custom auth request headers and body type

EOF
)"
```

---

### Task 2: Model 列 + Alembic 数据迁移

**Files:**
- Modify: `backend/app/modules/mcp_gateway/auth/model.py`
- Create: `backend/app/alembic/versions/2026_10_26_<HHMM>_<rev>_auth_custom_request_shape.py`

**Interfaces:**
- Consumes: `lift_custom_request_from_rule`
- Produces: `AuthConfigModel.headers|query|body_type|body` 可映射列

- [ ] **Step 1: 扩展 model**

在 `AuthConfigModel` 增加（`password_encrypted` 旁）：

```python
headers: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="自定义请求头")
query: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="自定义 Query")
body_type: Mapped[str | None] = mapped_column(String(16), nullable=True, comment="自定义 Body 类型")
body: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="自定义 Body")
```

- [ ] **Step 2: 生成并手写数据迁移**

```bash
cd backend && uv run alembic heads   # 记下 tip revision
uv run alembic revision -m "auth_custom_request_shape"
```

`upgrade` 要点：

1. `batch_alter_table('mcp_biz_auth_config')` 增加四列（JSON / String(16) 可空）
2. 用 `op.get_bind()` + `sa.text("SELECT id, method, rule FROM mcp_biz_auth_config")` 遍历；对 `method == 'custom'` 调用 `lift_custom_request_from_rule`，`UPDATE` 写回四列 + 清理后的 `rule`（注意 JSON 序列化：`json.dumps` 或 dialect 绑定）

`downgrade`：把四列内容写回 `rule`（headers/query/json|form），再 drop 列。

`down_revision` = Step 开头记下的 tip。

- [ ] **Step 3: 本地升级（dev DB）**

Run: `cd backend && uv run alembic upgrade head`

Expected: 无错误

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/mcp_gateway/auth/model.py \
  backend/app/alembic/versions/*auth_custom_request_shape*.py
git commit -m "$(cat <<'EOF'
feat: add auth custom request shape columns and migrate rule

EOF
)"
```

---

### Task 3: Service 持久化 + 配置测试

**Files:**
- Modify: `backend/app/modules/mcp_gateway/auth/service.py`
- Modify: `backend/tests/mcp_gateway/test_auth_config.py`

**Interfaces:**
- Consumes: schema 四字段；`ensure_custom_request_fields`
- Produces: create/update 写入四列；非 custom 时强制 `headers=query=body=body_type=None`

- [ ] **Step 1: 写失败测试**

在 `test_auth_config.py` 追加：

```python
async def test_custom_auth_persists_request_shape(db) -> None:
    system = await _system(db, "oa-custom-shape")
    service = AuthConfigService(_auth(), db)
    created = await service.create(
        AuthConfigCreateSchema(
            system_id=system.id,
            method="custom",
            enabled=True,
            url="https://oa.example.com/login",
            rule={"token_from": "json", "token_name": "token"},
            http_method="POST",
            headers={"X-App": "{{system.client_id}}"},
            query={"uid": "{{user.uid}}"},
            body_type="json",
            body={"dept": "{{user.attr.dept}}"},
        )
    )
    assert created.headers == {"X-App": "{{system.client_id}}"}
    assert created.query == {"uid": "{{user.uid}}"}
    assert created.body_type == "json"
    assert created.body == {"dept": "{{user.attr.dept}}"}
    assert "query" not in created.rule

    row = await db.get(AuthConfigModel, created.id)
    assert row is not None
    assert row.body_type == "json"
    assert row.headers == {"X-App": "{{system.client_id}}"}


async def test_fixed_auth_clears_request_shape_fields(db) -> None:
    system = await _system(db, "oa-fixed-clear")
    service = AuthConfigService(_auth(), db)
    created = await service.create(
        AuthConfigCreateSchema(
            system_id=system.id,
            method="fixed",
            enabled=True,
            url="https://oa.example.com/login",
            rule={},
            headers={"X": "1"},
            body_type="json",
            body={"a": 1},
        )
    )
    assert created.headers is None
    assert created.body_type is None
    assert created.body is None
```

- [ ] **Step 2: 跑测试确认失败或字段未清**

Run: `cd backend && uv run pytest tests/mcp_gateway/test_auth_config.py::test_custom_auth_persists_request_shape tests/mcp_gateway/test_auth_config.py::test_fixed_auth_clears_request_shape_fields -v`

- [ ] **Step 3: 改 service**

在 `_create_payload` 与 `update` 落库前：

```python
def _normalize_request_shape(method: str, payload: dict) -> dict:
    if method != "custom":
        payload["headers"] = None
        payload["query"] = None
        payload["body_type"] = None
        payload["body"] = None
        return payload
    if payload.get("body_type") is None:
        payload["body_type"] = "none"
    if payload.get("body_type") == "none":
        payload["body"] = None
    return payload
```

create：`payload = _normalize_request_shape(data.method, self._create_payload(data))`  
update：合并 method 后对 `payload` 调用同一函数（仅当 submitted 含这些键或 method 变更时规范化；最简单：每次 update 用合并后的 method + 合并后的四字段再 normalize 写回）。

- [ ] **Step 4: 跑测试通过**

Run: `cd backend && uv run pytest tests/mcp_gateway/test_auth_config.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/mcp_gateway/auth/service.py backend/tests/mcp_gateway/test_auth_config.py
git commit -m "$(cat <<'EOF'
feat: persist custom auth request shape on create and update

EOF
)"
```

---

### Task 4: 登录拼装改读新字段 + 刷新测试

**Files:**
- Modify: `backend/app/modules/mcp_gateway/auth/client.py`
- Modify: `backend/tests/mcp_gateway/test_auth_refresh.py`

**Interfaces:**
- Consumes: `auth.headers` / `auth.query` / `auth.body_type` / `auth.body`；`lift_custom_request_from_rule` 读时兜底
- Produces: custom 登录 kwargs 含 `headers` / `params` / `json`|`data`

- [ ] **Step 1: 扩展 `_auth` 助手并改写 custom 测试**

在 `test_auth_refresh.py` 的 `_auth(...)` 增加参数：

```python
headers: dict[str, Any] | None = None,
query: dict[str, Any] | None = None,
body_type: str | None = None,
body: dict[str, Any] | None = None,
```

并传入 `AuthConfigModel(...)`。

将 `test_custom_login_puts_placeholders_where_the_config_says` 改为：

- `place == "query"` → `query=_TEMPLATE`, `body_type="none"`, rule 仅 `_TOKEN_RULE`
- `place == "json"` → `body_type="json"`, `body=_TEMPLATE`
- `place == "form"` → `body_type="form"`, `body=_TEMPLATE`

另增：

```python
async def test_custom_login_sends_configured_headers() -> None:
    redis = ExpiringRedis()
    upstream = _Upstream(redis, [200])
    client, _cache = _client(
        httpx.MockTransport(upstream.handler),
        redis,
        auth=_auth(
            method="custom",
            url="https://auth.example.com/login",
            http_method="POST",
            headers={"X-Uid": "{{user.uid}}", "X-App": "{{system.client_id}}"},
            body_type="json",
            body={"uid": "{{user.uid}}"},
            rule=dict(_TOKEN_RULE),
        ),
    )
    response = await client.call(USER_ID, SYSTEM_ID, **_business_call())
    assert response.status_code == 200
    login = upstream.logins[0]
    assert login.headers.get("x-uid") == "zhangsan"
    assert login.headers.get("x-app") == "oa-app"
    assert json.loads(login.content) == {"uid": "zhangsan"}
```

保留 `test_basic_login_uses_the_system_account_not_the_person` 仍把 json 放在 `rule` 里。

再增读时兜底（可选同一文件）：

```python
async def test_custom_login_lifts_legacy_rule_request_sections() -> None:
    redis = ExpiringRedis()
    upstream = _Upstream(redis, [200])
    rule = dict(_TOKEN_RULE)
    rule["json"] = {"uid": "{{user.uid}}"}
    client, _cache = _client(
        httpx.MockTransport(upstream.handler),
        redis,
        auth=_auth(method="custom", url="https://auth.example.com/login", http_method="POST", rule=rule),
        # headers/query/body_type/body 全默认 None → 触发 lift
    )
    response = await client.call(USER_ID, SYSTEM_ID, **_business_call())
    assert response.status_code == 200
    assert json.loads(upstream.logins[0].content) == {"uid": "zhangsan"}
```

- [ ] **Step 2: 跑测试确认 custom 旧路径失败**

Run: `cd backend && uv run pytest tests/mcp_gateway/test_auth_refresh.py -k custom -v`

Expected: 改写后的测试 FAIL（仍只读 rule）

- [ ] **Step 3: 改 `_login_request`**

替换 custom/basic 共用段为：

```python
kwargs: dict[str, Any] = {}
if self.auth.method == "custom":
    headers, query, body_type, body = self._custom_request_shape()
    if headers:
        kwargs["headers"] = self._render_mapping(headers, token=None)
    if query:
        kwargs["params"] = self._render_mapping(query, token=None)
    if body_type == "form" and body is not None:
        kwargs["data"] = self._render_mapping(body, token=None)
    elif body_type == "json" and body is not None:
        kwargs["json"] = self._render_value(body, token=None)
elif self.auth.method == "basic":
    query = self._section("query")
    json_body = self._section("json")
    form = self._section("form")
    if query is not None:
        kwargs["params"] = self._render_mapping(query, token=None)
    if form is not None:
        kwargs["data"] = self._render_mapping(form, token=None)
    elif json_body is not None:
        kwargs["json"] = self._render_value(json_body, token=None)
    kwargs["auth"] = httpx.BasicAuth(
        self.auth.username or "",
        CryptoUtil.decrypt_or_keep(self.auth.password_encrypted),
    )
http_method = str(self.auth.http_method or "GET").upper()
return http_method, url, kwargs
```

新增：

```python
def _custom_request_shape(self) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str, dict[str, Any] | None]:
    headers = self.auth.headers if isinstance(self.auth.headers, dict) else None
    query = self.auth.query if isinstance(self.auth.query, dict) else None
    body_type = self.auth.body_type
    body = self.auth.body if isinstance(self.auth.body, dict) else None
    empty = not headers and not query and body_type is None and body is None
    if empty:
        h, q, bt, b, _ = lift_custom_request_from_rule(self.auth.rule or {})
        return h, q, bt, b
    return headers, query, body_type or "none", body
```

从 `migrate_rule` import `lift_custom_request_from_rule`。

- [ ] **Step 4: 跑全部 auth refresh 测试**

Run: `cd backend && uv run pytest tests/mcp_gateway/test_auth_refresh.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/mcp_gateway/auth/client.py backend/tests/mcp_gateway/test_auth_refresh.py
git commit -m "$(cat <<'EOF'
feat: send custom auth headers query and typed body on login

EOF
)"
```

---

### Task 5: 前端 API、KeyValueRows、鉴权表单

**Files:**
- Create: `frontend/web/src/views/module_mcp_gateway/components/KeyValueRows.vue`
- Modify: `frontend/web/src/api/module_mcp_gateway/auth.ts`
- Modify: `frontend/web/src/views/module_mcp_gateway/auth/index.vue`

**Interfaces:**
- Consumes: FaForm 具名插槽 `#headers_rows` / `#query_rows` / `#body_form_rows`；API 四字段
- Produces: 提交 payload 含 `headers`/`query`/`body_type`/`body`（仅 custom）

- [ ] **Step 1: KeyValueRows 组件**

创建 `KeyValueRows.vue`：

```vue
<template>
  <div class="kv-rows">
    <div v-for="(row, index) in modelValue" :key="index" class="flex gap-2 items-center flex-wrap mb-2">
      <ElInput v-model="row.key" placeholder="名" class="!w-40" />
      <ElInput v-model="row.value" placeholder="值，可写 {{user.uid}}" class="!flex-1 min-w-40" />
      <ElButton text type="danger" @click="remove(index)">删除</ElButton>
    </div>
    <ElButton plain @click="add">{{ addLabel }}</ElButton>
  </div>
</template>

<script setup lang="ts">
export interface KvRow {
  key: string;
  value: string;
}

const props = withDefaults(
  defineProps<{ modelValue: KvRow[]; addLabel?: string }>(),
  { addLabel: "添加一行" },
);
const emit = defineEmits<{ "update:modelValue": [KvRow[]] }>();

function add() {
  emit("update:modelValue", [...props.modelValue, { key: "", value: "" }]);
}
function remove(index: number) {
  const next = props.modelValue.slice();
  next.splice(index, 1);
  emit("update:modelValue", next.length ? next : [{ key: "", value: "" }]);
}
</script>
```

导出工具函数（可同文件旁 `kv.ts` 或写在 `auth.ts`）：

```ts
export function rowsToRecord(rows: { key: string; value: string }[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const row of rows) {
    const k = row.key.trim();
    if (!k) continue;
    out[k] = row.value;
  }
  return out;
}
export function recordToRows(record?: Record<string, string> | null): { key: string; value: string }[] {
  const entries = Object.entries(record ?? {});
  if (!entries.length) return [{ key: "", value: "" }];
  return entries.map(([key, value]) => ({ key, value: String(value ?? "") }));
}
```

- [ ] **Step 2: 扩展 auth API**

`BizAuthTable` / `BizAuthForm` 增加：

```ts
headers?: Record<string, string> | null;
query?: Record<string, string> | null;
body_type?: "none" | "json" | "form" | null;
body?: Record<string, unknown> | null;
// form 侧辅助，不直接提交：
header_rows 不进类型也可只用页面 ref
body_text?: string; // json 编辑
```

`toPayload`：当 `method === "custom"`：

```ts
data.headers = body.headers ?? {};
data.query = body.query ?? {};
data.body_type = body.body_type ?? "none";
data.body = body.body_type === "none" ? null : body.body ?? null;
```

非 custom 不传这四项（或显式 null）。

页面在 submit 前把 rows / body_text 写入 `formData.headers` 等（在 `createApi`/`updateApi` 包装，或改 `toPayload` 接受 rows——推荐在 `index.vue` 的 submit 包装里同步到 formData 再调 API）。

- [ ] **Step 3: 改 auth/index.vue**

1. `import KeyValueRows`；`headerRows` / `queryRows` / `formBodyRows` refs
2. `createInitialForm` 增加 `body_type: "none"`, `body_text: "{}"`
3. `dialogFormItems`：custom 时在 HTTP 方法后插入：
   - `{ label: "请求头", key: "headers_rows", type: "input", span: 24 }`（靠插槽覆盖）
   - `{ label: "Query 参数", key: "query_rows", ... }`
   - `{ label: "Body 类型", key: "body_type", type: "select", options: [{label:"无",value:"none"},{label:"JSON",value:"json"},{label:"Form",value:"form"}] }`
   - `body_type==='json'` → `{ label: "Body", key: "body_text", type: "input", props: { type: "textarea", rows: 6 } }`
   - `body_type==='form'` → `{ label: "Body", key: "body_form_rows", type: "input", span: 24 }`
4. FaForm 插槽：

```vue
<FaForm ...>
  <template #headers_rows>
    <KeyValueRows v-model="headerRows" add-label="添加 Header" />
  </template>
  <template #query_rows>
    <KeyValueRows v-model="queryRows" add-label="添加 Query" />
  </template>
  <template #body_form_rows>
    <KeyValueRows v-model="formBodyRows" add-label="添加字段" />
  </template>
</FaForm>
```

5. `detailForForm`：回填 rows；`body_type`；json 时 `body_text = JSON.stringify(row.body ?? {}, null, 2)`
6. 提交前函数 `syncCustomRequestToForm()`：
   - `formData.headers = rowsToRecord(headerRows)`
   - `formData.query = rowsToRecord(queryRows)`
   - 若 json：`JSON.parse(body_text)` 校验为 object → `formData.body`
   - 若 form：`formData.body = rowsToRecord(formBodyRows)`
   - 若 none：`formData.body = null`
7. 方法切换 watch：进入 custom 默认 `body_type=none`；离开则清空 rows
8. 更新 `AUTH_GUIDES.custom.fills` / `when`：

```ts
when: "OA 登录不是固定的 uid POST，而是管理员配置的 HTTP 请求，参数可放在 Header、Query、JSON 或 Form。",
fills: "业务系统、请求地址、HTTP 方法、请求头、Query、Body 类型与 Body、取值规则。",
```

9. `RULE_PLACEHOLDER` 改为仅响应取值示例（去掉 query/json/form）

- [ ] **Step 4: 手动验收清单（本任务无自动化 UI 测试）**

- 新建 custom：填 Header / Query / JSON body，保存后编辑回显
- 切换 Body 类型 Form，键值对保存回显
- 切换到 fixed，保存后详情无残留 body_type

- [ ] **Step 5: Commit**

```bash
git add frontend/web/src/views/module_mcp_gateway/components/KeyValueRows.vue \
  frontend/web/src/api/module_mcp_gateway/auth.ts \
  frontend/web/src/views/module_mcp_gateway/auth/index.vue
git commit -m "$(cat <<'EOF'
feat: edit custom auth headers query and body type in form

EOF
)"
```

---

### Task 6: 占位符说明文案

**Files:**
- Modify: `frontend/web/src/views/module_mcp_gateway/components/placeholderHelpContent.ts`

**Interfaces:**
- Consumes: 无
- Produces: 更新后的 `AUTH_PLACEHOLDER_HELP.usage` / `examples`

- [ ] **Step 1: 改文案**

`usage` 改为：

```ts
usage: [
  "地址：URL 可写占位符。",
  "自定义请求：请求头、Query、Form 的值，以及 JSON Body 里的字符串，可写占位符。",
  "Basic：取值规则 JSON 里 query / json / form 对象的值可写占位符。",
  "fixed：系统自动 POST {uid_field: uid}，不必手写 {{user.uid}}。",
  "interactive：主要配验证页 URL 与回调取值规则；登录请求本身不走这些占位符换 token。",
],
```

`examples`：

```ts
examples: [
  {
    caption: "自定义请求：请求头 / Query / Body 与取值规则分开",
    code: `请求头: X-User = {{user.uid}}
Query: userId = {{user.uid}}
Body(JSON): { "dept": "{{user.attr.dept}}", "appKey": "{{system.app_key}}" }

取值规则:
{
  "token_from": "json",
  "token_name": "access_token",
  "expires_seconds": 3600
}`,
  },
],
```

- [ ] **Step 2: Commit**

```bash
git add frontend/web/src/views/module_mcp_gateway/components/placeholderHelpContent.ts
git commit -m "$(cat <<'EOF'
docs: update auth placeholder help for custom request fields

EOF
)"
```

---

### Task 7: 回归与收尾

**Files:** 无新文件

- [ ] **Step 1: 跑相关后端测试**

Run:

```bash
cd backend && uv run pytest tests/mcp_gateway/test_auth_custom_request_shape.py \
  tests/mcp_gateway/test_auth_config.py \
  tests/mcp_gateway/test_auth_refresh.py \
  tests/mcp_gateway/test_auth_extract.py \
  tests/mcp_gateway/test_oa_todo_acceptance.py -v
```

Expected: PASS

- [ ] **Step 2: 若有失败，修到全绿后再提交修复 commit**

- [ ] **Step 3: 确认无未提交的计划外改动**

Run: `git status`

---

## Spec coverage（自检）

| Spec 要求 | Task |
|-----------|------|
| headers/query/body_type/body 列与校验 | 1–3 |
| 仅 custom；basic 仍读 rule | 4 |
| 表单键值对 + body 类型编辑器 | 5 |
| 取值规则不含请求段；指南/占位符文案 | 5–6 |
| 迁移 + 读时 lift | 2、4 |
| 登录拼装与测试 | 4、7 |
| 不做 raw/multipart / basic UI | 全局约束 |

无 TBD。类型名 `body_type` / `BodyType` / `lift_custom_request_from_rule` 全计划一致。
