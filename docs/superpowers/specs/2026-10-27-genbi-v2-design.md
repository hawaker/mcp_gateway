# GenBI v2（ask_bi + 行列权限）设计

日期：2026-10-27  
状态：已批准（对话确认）  
范围：`plan.md` 二 v2 — GenBI 数据源、`ask_bi`、虚拟服务器行列权限

## 背景

v1 已完成 REST/上游 → MCP 网关。v2 要把 tiga-case（`tiga-case`）知识中心 → 系统设置 → 商业智能 的数据源与问数能力迁入本项目，并挂到 MCP 虚拟服务器上。

参考实现：`/Users/v/Documents/code/cloudladder/tiga-case`（连接 UI、`genbi_ask`、Wren、ACL、ibis）。

## 已定决策

| 项 | 选择 |
|----|------|
| 引擎 | 本仓完整迁入 Wren AI + ibis/engine + 建模/部署（非远程调 tiga） |
| 交付 | 按 plan 一次做完：连接 → ask_bi → 组选数据源 + 行列权限 |
| ACL 挂载 | 虚拟服务器；**组内全部业务用户/用户组共用同一套规则**（不按人拆） |
| 多数据源 | **每个「虚拟服务器 × 数据源」各一套 ACL** |
| 建模 UI | 对齐 tiga：连接 → setup → modeling → knowledge → capabilities → 部署 |
| 应用库 | `.env` 的 `DATABASE_TYPE` **不**做 MySQL；本仓元数据/向量用现有 **PostgreSQL + pgvector** |
| GenBI 外连 | 可连接类型 **对齐 tiga-case**（含 MySQL、MSSQL、Oracle、ClickHouse、云端类型等） |
| 向量配置 | **不**单独增加向量库；Wren 向量索引落当前业务 PG（pgvector） |

## 目标

### 做

- 新建 `genbi` 域：数据源连接、项目、MDL 建模/知识/能力、部署、ask 管线
- 数据源归属业务系统；包装 MCP 工具，默认名 `{业务系统英文编码}_ask_bi`
- 虚拟服务器在 REST / 上游之外可多选已部署数据源；至少一类工具或数据源
- 组内重名走 v1 人工别名
- 管理端 GenBI UI 对齐 tiga 壳，组件用本仓 frontend
- MCP `tools/call` → 成员校验 → 该组该源 ACL → Wren NL→SQL → 改写 → ibis 预览 → 返回
- 调用日志记录 ask_bi；默认不落 SQL/结果集明文
- compose/env 增加 Wren/ibis（或引擎）所需项；向量连现有 PG

### 不做

- 应用侧 `DATABASE_TYPE=mysql` 兼容
- 独立第二套向量库服务/配置
- 虚拟服务器内按人/按业务用户组拆不同 ACL
- 业务用户登录 GenBI 独立前台
- 远程 HTTP 调用外部 tiga GenBI 作为唯一引擎

## 方案

采用 **A**：在 `mcp_gateway` 旁建 `backend/app/modules/genbi/`，运行时由网关注册并执行 `ask_bi`；行列规则存「虚拟服务器 × 数据源」。

## 模块边界

| 部分 | 职责 |
|------|------|
| `modules/genbi/` | 连接、项目、建模元数据、部署、ACL 编译/改写、ask 执行、管理 API |
| `mcp_gateway/mcp_group` | 勾选数据源、每源 ACL 配置、别名/禁用 |
| `mcp_gateway/runtime` | `tools/list` / `tools/call` 对 ask_bi |
| `frontend/.../module_genbi` | 对齐 tiga 的 GenBI 管理壳 |
| `frontend/.../mcp_group` | 数据源多选 + 每源 ACL 编辑 |
| deploy / env | Wren AI、ibis/engine；`GENBI_*` 指向现有 PG（含 pgvector） |

权限码：`module_genbi:*`；组上数据源/ACL 仍落在 `module_mcp_gateway` 组管理权限下。业务用户不能调 GenBI 管理接口。

## 数据模型（概念）

1. **GenBI 数据源** — 属业务系统；字段对齐 tiga（`wren_type`、host、port、credentials、database、schema、`config` JSON 等）；密码等加密存。
2. **GenBI 项目** — 与数据源 1:1；承载模型/列/关系/指标/知识/部署记录与 `mdl_hash`。
3. **组–数据源关联** — 虚拟服务器多选已**成功部署**的数据源；可禁用；对外名默认 `{code}_ask_bi`，冲突则别名。
4. **组 × 源 ACL** — 行规则、列 `mask`/`deny`；**无 ACL 成员表**。能调用该组 MCP 的人共用此套。

未配置过 ACL：问数不做行列改写（无限制）。规则运算符/掩码形态对齐 tiga ACL。

## `ask_bi` 行为

- 入参：`question: string`（与 tiga `genbi_ask` 对齐；出参含 sql/columns/rows/summary/error 等）
- 前置：MCP token 有效；用户与组未禁用；该工具在组内启用；数据源/业务系统可用；项目有成功部署
- **不**走业务系统 REST 鉴权绑定与 token 刷新；库访问用数据源凭证
- 管线：Wren NL→SQL → 应用该组该源 ACL → ibis 预览（限行）→ 返回
- 失败码对齐 tiga 精神（如未部署、列拒绝、ASK 失败），中文或稳定 `code` 字段便于客户端处理

## 运维约束

- 应用数据库：仅 PostgreSQL（现有 `.env` / `DATABASE_TYPE`）
- 向量：现有实例上的 pgvector，不新增向量库配置项
- GenBI **外连**能力列表 = tiga-case 原能力（含连 MySQL 等业务库），与应用库类型无关

## 验收标准

1. 管理员可为业务系统新建 GenBI 数据源（类型覆盖 tiga 支持集），完成建模并部署成功  
2. 虚拟服务器勾选后，`tools/list` 出现 `{code}_ask_bi`（可别名）；可与 REST/上游并存  
3. 业务用户 MCP token 调用 `ask_bi` 能返回结果；未部署或未勾选则失败  
4. 「组 × 源」ACL 对该组所有调用者生效；另一数据源规则互不影响  
5. 组保存时至少一类（REST / 上游 / 数据源）；调用日志有 ask_bi 且默认无 SQL/结果集明文  
6. 不引入第二套向量库；应用库无需 MySQL `DATABASE_TYPE`

## 改动面（实现时）

- 新模块与迁移、菜单种子、前端 GenBI 壳  
- MCP 组与 runtime 扩展  
- deploy/env（Wren/ibis + 指向现有 PG）  
- 测试：连接/部署门禁、ask mock、组×源 ACL、list/call 集成  

详细任务分解见后续 `docs/superpowers/plans/` 实现计划（writing-plans）。
