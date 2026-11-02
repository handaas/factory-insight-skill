---
name: factory-insight-report
description: "Use for generating a professional factory-insight big-data report (工厂信息分析报告) from the HandaaS factory-insight MCP — covering 工厂概况与风险、工厂产能（产线/人员/设备/质检）、工厂产品统计、工厂检索明细. Trigger when users ask for “工厂信息分析报告”, “工厂分析报告”, “查一家公司的工厂”, “工厂产能分析”, “工厂概况”, “供应商产能评估”, “工厂检索”, or “企业工厂画像”. Infer the canonical enterprise name (auto-fuzzy-completing a keyword), pick the right MCP tools, and produce HTML + Markdown + JSON reports automatically. Supports two modes: enterprise (按企业主体查工厂详情) and search (按关键词+地区检索工厂). MCP 服务名称触发词：工厂运营透析。"
---

# 工厂信息分析报告

## 用户契约

把“工厂信息分析报告”作为面向用户的调用短语。`factory-insight-report` 仅为内部包名。

当本 skill 处于激活状态：

1. 不要向用户索要 product_id、MCP 工具名、API 字段、内部参数或凭证信息；只接受企业名称、统一社会信用代码、注册号、企业 ID（企业模式）或工厂检索关键词与地区（检索模式）。
2. 接受自然目标，例如“查一下某某公司的工厂”“评估这家供应商的产能”“给我一份工厂概况报告”“在广东省找做某某产品的工厂”。
3. 当用户只给关键词（企业模式）时，自动调用关键词模糊查询补全企业全称，再查工厂详情。
4. 账期风险仅原样标为上游指标，不扩写为付款条款、回款压力、资金占用、履约表现或长期合作适配等交易事实。
5. 摘要和数据口径只列实际非空章节；平台身份、认证名称和单一“其他”类目只作为字段/信息线索，不泛称生产实力，也不外推产能、准入、质量或周期韧性。
6. 优先使用 MCP 连接（`FACTORY_INSIGHT_MCP_URL` Remote MCP 或本地 `handaas-mcp-server/factory-insight-mcp-server`）；不要让用户处理签名或凭证。
7. 同时产出 HTML（可分享交付）、Markdown（知识库 / wiki）、JSON（系统集成）三类产物。
8. 报告正文必须是专业研究报告风格：只见工厂事实与结构化数据，绝不出现工具名、入参、product_id、内部字段或空表。
9. 绝不打印 `secret_id`、`secret_key`、签名、token 或原始签名请求。
10. 默认 dry-run；真实付费 / 凭证调用需用户明确要求且 MCP 连接配置完整。
11. 数据为空时明确说明数据范围 / 口径，不渲染空表、不臆造事实。


- MCP 返回的嵌套 JSON 字符串（如金额 `{"coinType":"人民币","value":430000000.0}`、地址 `{"city":"杭州市",...}`）必须解析为可读文本（如"4.30 亿 人民币"、"浙江省杭州市"），绝不在报告正文、表格或指标中输出原始 JSON 字符串。
- 报告所有章节标题、指标卡标签必须用中文；`core_analysis.sections` 的 `title` 字段必须中文，不可显示英文 key（如 `holders`、`investments`）。
- 指标值必须可读化：金额格式为"X 亿/万 + 币种"，地址拼接省市区，比率显示百分号。详见 `references/report-output.md` 的「数据格式约束」。

## 付费调用纪律（先规划后查询）

每次真实调用均按接口/页计费，必须先规划再查询，不得默认全量拉取：

1. 每一次业务/工具调用、每一页都可能收费。想算 total / 页数不是无限制取全量的授权。
2. 调用前先推导：需要哪些结论、需要哪些数据维度、工具与参数计划、必要页数与最大调用预算。total 未知时，第一个必要的明细页同时完成 total 发现并直接作为报告数据，绝不为此多付一次（首屏响应必须复用，不重复拉取）。
3. 企业模式详情工具（工厂概况 / 产能 / 产品统计）返回 KV/聚合结构，`references/mcp-tools-reference.md` 的按工具参数表不含 pageIndex/pageSize，因此按 schema 不设分页参数、各单次调用；仅工厂检索明细按 total 驱动翻页。`factory_insight_fuzzy_search` 只用于身份解析取首个命中（pageSize=1），不做翻页。
4. 在 schema 允许范围内用合理的大 pageSize（工厂检索 ≤10、模糊查询 ≤50），取得所需证据 / 样本即停，且不超出显式预算。更多调用必须有“缺失结论”的正当理由，不能只为填满章节。不得用样本分布冒充全量结论。
5. 复用当前任务 / 报告内的相同请求（含首屏规划数据）；不要为渲染重跑 compose/MCP，用已保存 JSON 本地重渲染。不自动重试、不重复拉取同一明细。任何补充查询必须先列缺口并复用已返回记录。
6. `total_pages` / `remaining_pages` 是按请求 pageSize 的估算；短而非空页面仍有剩余记录时在预算内继续。只有稳定有效的 total 等于实际扫描条数才算完整采集；错误、提前空页、重复页、total 变化/缺失、数量溢出均视为不完整。显式预算 / 样本停止即部分采集，绝不宣称全量。
7. 预算不足以支撑用户要求的关键结论时：先说明证据缺口与预计需要追加的调用数，再请求扩大授权（提高 `--max-pages`）；不静默降级结论，也不擅自扩大计费范围。

分页收集默认一次明细调用预算 `--max-pages 1`；工厂检索的 total、实际取数、完整性披露写入报告 `data_source.pagination`，报告级去重统计写入 `data_source.call_usage`。企业模式固定 3 次详情调用（概况/产能/产品统计）+ 1 次模糊解析（仅关键词时）；计划须明示每次业务调用的数量与维度，不因工具存在就全部调用。

## MCP 服务入口

- MCP 服务当前名称：工厂运营透析（连接仍使用原服务目录标识）。

- 上游 MCP 项目：`handaas-mcp-server/factory-insight-mcp-server`（位于 `HANDAAS_MCP_SERVER_ROOT` 或本仓库同级目录）。
- Remote MCP：设置环境变量 `FACTORY_INSIGHT_MCP_URL`（streamable-http），可选 `FACTORY_INSIGHT_MCP_TOKEN`。
- 本地 MCP：设置 `HANDAAS_MCP_SERVER_ROOT` 指向 `handaas-mcp-server` 仓库根目录；该 server 自己的 `.env` 提供 `INTEGRATOR_ID` / `SECRET_ID` / `SECRET_KEY`。
- 首次真实查询前，运行 `scripts/mcp_client.py ping` 与 `scripts/mcp_client.py list-tools` 验证连通。

## 按需加载 references

- 不清楚该 MCP 有哪些工具、参数、返回字段、何时调用：`references/mcp-tools-reference.md`。
- 报告结构、章节、质量底线、渲染工作流：`references/report-output.md`。

## 意图路由

| 用户意图 | 内部工作流 |
| --- | --- |
| 查一家公司的全维度工厂报告 | 企业模式：调工厂概况 + 工厂产能 + 工厂产品统计组装全量报告；`compose_report.py --enterprise ...` |
| 只要工厂概况 / 产能 / 产品统计 | 仅调对应工具，按统一骨架组装 |
| 按关键词+地区检索工厂（选品/找供应商） | 检索模式：`compose_report.py --search ... --address 广东省 --address 广东省,潮州市` |
| 只给关键词（不是全称，企业模式） | 先 `factory_insight_fuzzy_search` 补全全称，再查详情 |
| 只要 JSON / 只要 HTML / 只要 Markdown | 用 `--output`（JSON）或 `--report-output`（HTML+MD），或 `render_report.py` 重渲染 |
| 连接 / 工具不存在 / 传参错误 | `mcp_client.py ping` / `list-tools` 排查；报脱敏后的缺失项 |

## Golden path for 工厂信息分析报告

1. **选择模式**：用户给企业名称→企业模式；用户给“找工厂/选品/按地区搜”→检索模式。
2. **解析企业全称**（企业模式）：若输入含“公司/集团/有限/院/厂/中心/事务所/合作社/合伙”等后缀视为全称；否则调 `factory_insight_fuzzy_search` 取首个命中。
3. **调用工厂工具**：
   - 企业模式：`factory_insight_factory_profile`（概况/风险）、`factory_insight_factory_capabilities`（产能）、`factory_insight_factory_product_stats`（产品统计）。入参为 `matchKeyword`（企业全称）+ `keywordType`。
   - 检索模式：`factory_insight_factory_search`（matchKeyword + keywordType + address[双层列表] + pageIndex + pageSize）。分页，默认 1 页预算；按 total 驱动、在 --max-pages 预算内翻页，超出预算披露未纳入条数而非宣称全量。
4. **组装统一报告**：企业模式包含概况/产能/产品；检索模式在 --max-pages（默认 1）预算内按 total 翻页、超出预算披露未纳入条数；企业模式详情工具按 schema 不设分页参数。保留上游公开地区/地址字段；若单条未返回则明确“不可逐条复核”，不套用企业能力摘要。
5. **渲染三件套**：`compose_report.py --enterprise ... --output ... --report-output ...` 直接产出 JSON + HTML + Markdown；或 `render_report.py --input ... --output ...` 重渲染。
6. **返回路径**：返回 JSON、HTML、Markdown 文件路径，以及企业全称映射与数据口径。

## 脚本速查

```bash
# 校验连接配置（脱敏）
python scripts/validate_config.py --allow-placeholders

# 连通性自测
python scripts/mcp_client.py ping
python scripts/mcp_client.py list-tools

# 干跑（不调真实 API，用样例数据组装报告骨架）
python scripts/compose_report.py \
  --enterprise "示例科技有限公司" \
  --dry-run \
  --output output/factory.json \
  --report-output output/factory.html

# 真实查询 + 渲染（企业模式，需 MCP 连接就绪）
python scripts/compose_report.py \
  --enterprise "示例科技有限公司" \
  --output output/factory.json \
  --report-output output/factory.html

# 工厂检索模式（按关键词+地区找工厂）
python scripts/compose_report.py \
  --search "服装" --keyword-type 主营产品 \
  --address 广东省 --address 广东省,潮州市 \
  --output output/factory_search.json \
  --report-output output/factory_search.html

# 工厂检索翻页预算（默认 1：只取第 1 页并复用首屏 total，超出部分在 data_source.pagination 披露未纳入条数）
python scripts/compose_report.py \
  --search "服装" --keyword-type 主营产品 \
  --address 广东省 \
  --page-size 10 --max-pages 2 \
  --output output/factory_search.json

# 手动调单个工具
python scripts/mcp_client.py call-tool \
  --tool factory_insight_factory_profile \
  --arguments-json '{"matchKeyword": "示例科技有限公司", "keywordType": "name"}'

# 重渲染已有 JSON
python scripts/render_report.py --input output/factory.json --output output/factory.html
python scripts/render_report.py --input output/factory.json --output output/factory.md
```

## 输出字段

- `subject`：企业全称、匹配关键词、主体类型、是否自动补全（检索模式额外含 mode/address）。
- `abstract` / `summary`：封面摘要与详细摘要。
- `metrics`：工厂规模、生产线数、月产值、服务品牌数、主营产品数、检索结果数等指标卡。
- `caliber`：匹配对象、匹配方式、数据范围、产品、局限。
- `core_analysis`：工厂概况（KV）、工厂产能（KV）、工厂产品统计（表）、工厂检索明细（表）。
- `representative_records`：代表性工厂记录（企业名称 / 主营产品 / 注册资本 / 成立日期）。
- `insights`：结构化解读（工厂规模 / 生产实力 / 产品布局 / 资质认证）。
- `data_source`：MCP server、数据产品、生成时间、是否 dry-run、分页（`pagination`，检索模式）、计费调用统计（`call_usage`，真实调用）。

若 API 调用失败，明确报出缺失的配置 / 缺失的工具 / MCP 错误 / 参数校验错误 / 上游网络错误，给出 dry-run 命令或配置步骤，绝不暴露密钥。
