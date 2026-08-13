# MCP 工具参考 — factory-insight-mcp-server

本 skill 连接的 MCP server：`handaas-mcp-server/factory-insight-mcp-server`（“工厂信息分析洞察”）。

> **重要**：工厂详情类工具（profile / capabilities / product_stats）入参为 `matchKeyword`（**企业全称** / 注册号 / 统一社会信用代码 / 企业 id）+ `keywordType`；
> `factory_insight_factory_search` 的 `matchKeyword` 为工厂名称 / 主营产品 / 产品名称 / 地理位置关键词，且 `address`（双层列表）为必填项。
> 当用户只给企业关键词时，必须先调关键词模糊查询补全全称。

## 通用约定

- `keywordType` 枚举（详情工具）：`name`（企业名称）/ `nameId`（企业 id）/ `regNumber`（注册号）/ `socialCreditCode`（统一社会信用代码）。
- `factory_insight_factory_search` 的 `keywordType` 枚举：`综合搜索` / `工厂名称` / `主营产品` / `产品名称`。
- 分页：`pageIndex` 从 1 开始；详情工具单页最多 50，`factory_insight_factory_search` 单页最多 10。
- `factory_insight_factory_search` 的 `address` 必填，格式为双层列表：`[["广东省"],["广东省","潮州市"]]`，每个子列表表示一个地区（省份或省市）。

---

## 工具清单

### 1. `factory_insight_fuzzy_search` — 关键词模糊查询企业

用途：根据企业名称 / 人名 / 品牌 / 产品 / 岗位等关键词模糊查询企业列表，用于补全企业全称。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `matchKeyword` | string | 是 | 匹配关键词 |
| `pageIndex` | int | 否 | 分页开始位置（默认 1） |
| `pageSize` | int | 否 | 单页最多 50 |

返回：`total` + 企业列表（`name`、`nameId`、`regCapitalValue`、`foundTime`、`operStatus`、`address`、`legalRepresentative`、`enterpriseType`、`catchReason` 命中原因等）。

product_id：`675cea1f0e009a9ea37edaa1`。

---

### 2. `factory_insight_factory_product_stats` — 工厂产品统计

用途：按工厂主体返回服务品牌数量、主营产品数量、产品标签、产品类目统计。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `matchKeyword` | string | 是 | 企业名称 / 注册号 / 统一社会信用代码 / 企业 id |
| `keywordType` | string | 否 | 主体类型：name / nameId / regNumber / socialCreditCode |

返回：`serviceBrandCount`（服务品牌数量）、`mainProductCount`（主营产品数量）、`tagNames`（产品标签 list）、`productCategoriesStatInfo`（类目统计 list of {name,value}）。

product_id：`6725e5b9ba65854594baebd2`。

---

### 3. `factory_insight_factory_capabilities` — 工厂产能

用途：按企业主体返回工厂生产实力与资质信息（生产线、人员、设备、质量管理、相关资质）。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `matchKeyword` | string | 是 | 企业名称 / 注册号 / 统一社会信用代码 / 企业 id |
| `keywordType` | string | 否 | 主体类型：name / nameId / regNumber / socialCreditCode |

返回：`assemblyLine`（生产流水线）、`boarderStaffNumber`（打版人数）、`isSupportProofing`（是否支持打样）、`inspectionStaffNumber`（检验人数）、`mainDeviceList`（设备列表，含 brand/equipName/equipNum 等）、`managementSystemCertification`（管理体系认证）、`monthlyProductionAmountValue`（月产值）、`companyTechnicList`（工厂工艺）、`patentCertificateImageList`（相关资质）、`enterpriseCertification`（生产质量认证）。

product_id：`66aa4eac4bb1f40b86c46ee6`。

---

### 4. `factory_insight_factory_search` — 工厂检索

用途：按工厂名称 / 主营产品 / 产品名称 / 地理位置关键词 + 地区检索符合条件的工厂列表（地区必填）。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `matchKeyword` | string | 是 | 工厂名称 / 主营产品 / 产品名称 / 地理位置关键词 |
| `keywordType` | string | 是 | 综合搜索 / 工厂名称 / 主营产品 / 产品名称 |
| `pageIndex` | int | 否 | 从 1 开始（默认 1） |
| `pageSize` | int | 否 | 单页最多 10（默认 10） |
| `address` | list of list | 是 | 双层列表，例如 `[["广东省"],["广东省","潮州市"]]` |

返回（`resultList` + `total`）：每条含 `name`（企业名称）、`mainProducts`（主营产品 list）、`regCapital`（注册资本 dict）、`foundTime`（成立日期）、`nameId`（企业 id）。

product_id：`66aa4eac4bb1f40b86c46efe`。

---

### 5. `factory_insight_factory_profile` — 工厂概况/风险

用途：按企业主体返回工厂概况与风险评估。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `matchKeyword` | string | 是 | 企业名称 / 注册号 / 统一社会信用代码 / 企业 id |
| `keywordType` | string | 否 | 主体类型：name / nameId / regNumber / socialCreditCode |

返回：`name`（企业名称）、`foundTime`（成立时间）、`factoryScale`（工厂规模）、`factoryAddress`（工厂地址 dict：province/city/district/value）、`regCapital`（注册资本 dict：coinType/value）、`factoryTypeList`（工厂类型 list）、`monthlyProductionAmountValue`（月产值）、`accountPeriodRisk`（账期风险）、`nameId`。

product_id：`66aa4eac4bb1f40b86c46f0b`。

---

## 推荐调用顺序（报告编排）

1. （若仅有关键词，企业模式）`factory_insight_fuzzy_search` → 取 `name` 作为全称。
2. 企业模式：
   1. `factory_insight_factory_profile` → 工厂概况/风险。
   2. `factory_insight_factory_capabilities` → 产能指标。
   3. `factory_insight_factory_product_stats` → 产品统计。
3. 检索模式：`factory_insight_factory_search` → 工厂列表（matchKeyword + keywordType + address）。

> 企业模式单次报告通常调用 3-4 个工具；检索模式只调用 `factory_insight_factory_search`。
