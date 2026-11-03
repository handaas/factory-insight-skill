# 广东服装工厂寻源

- 用户需求：请在广东省检索主营服装的工厂。
- 决策用途：服装供应商长名单建立
- 本轮结果：**本轮检查通过**
- 实际工具调用：1；失败 0
- 章节覆盖率：100%（不代表证据质量）

## 预期业务检查（不自动宣称通过）

- 检索模式且至少一个地区
- keyword-type 为主营产品
- 地址解析为嵌套地区列表
- 不把搜索结果当作已审核供应商

## 本轮自动检查发现


## 使用局限

- 搜索只提供候选线索
- 主营产品标签和实际当前产能需复核

## 证据与复现

- [审计结果](result.json)
- [工具调用、结果形态与响应摘要哈希](calls.json)
- [JSON](report.json) / [HTML](report.html) / [Markdown](report.md)

```bash
python3 factory-insight-skill/scripts/compose_report.py --search '服装' --keyword-type '主营产品' --address '广东省' --page-size 10 --output factory-insight-skill/output/04-apparel-guangdong/report.json --report-output factory-insight-skill/output/04-apparel-guangdong/report.html
```

## 逐场景业务复核

本轮真实产物的全部清单检查均有当前字段证据，且报告保留样本/缺失/关系边界。

- **pass** 检索模式且至少一个地区：该项由当前调用参数、报告同名字段、样本与局限说明共同核对。 当前冻结快照：{"technical_status":"passed","successful_data_calls":1,"calls":[{"tool":"factory_insight_factory_search","status":"data","rows":10,"total":49967,"args":{"matchKeyword":"服装","keywordType":"主营产品","pageIndex":1,"pageSize":10,"address":[["广东省"]]}}],"subject":{"enterprise":"服装","matchKeyword":"服装","keywordType":"主营产品","match_raw":"服装","resolved":true,"resolve_reason":"工厂检索模式：按关键词直查","mode":"search","address":[["广东省"]]},"metrics":[{"label":"检索结果","value":"49967","hint":"工厂检索命中数"}],"core_counts":{"sections":4,"product_stats":0,"search_records":10,"management_certs":0},"core_samples":{"search_records":[{"企业名称":"比音勒芬服饰股份有限公司","主营产品":"家装、包(袋、建材、饰品、体育用、皮革日用品、皮革、纺织、手套、皮革及皮革制品、服饰配件、塑料、木制、服装辅料、日用器皿及日用杂货、金属日用杂品、服装、皮箱、日用杂品综合","注册资本":"570707084.0 人民币","成立日期":"2003-01-02","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}},{"企业名称":"搜于特集团股份有限公司","主营产品":"时尚商务男装、时尚夹克、时尚淑女装、时尚风衣、时尚休闲装、时尚牛仔裤、蕾丝边外套、单件短外套、服装、浪漫校园装、时尚羽绒服","注册资本":"3051878231.0 人民币","成立日期":"2005-12-05","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}}]},"quality":{"total_sections":1,"populated_sections":1,"empty_sections":0,"coverage_pct":100},"limit":"地区条件由上游执行；若单条记录未返回地区/地址字段，报告会明确标注不可逐条独立复核。检索结果不等同于已审核供应商。","html_bytes":1070901,"markdown_bytes":15394}
- **pass** keyword-type 为主营产品：该项由当前调用参数、报告同名字段、样本与局限说明共同核对。 当前冻结快照：{"technical_status":"passed","successful_data_calls":1,"calls":[{"tool":"factory_insight_factory_search","status":"data","rows":10,"total":49967,"args":{"matchKeyword":"服装","keywordType":"主营产品","pageIndex":1,"pageSize":10,"address":[["广东省"]]}}],"subject":{"enterprise":"服装","matchKeyword":"服装","keywordType":"主营产品","match_raw":"服装","resolved":true,"resolve_reason":"工厂检索模式：按关键词直查","mode":"search","address":[["广东省"]]},"metrics":[{"label":"检索结果","value":"49967","hint":"工厂检索命中数"}],"core_counts":{"sections":4,"product_stats":0,"search_records":10,"management_certs":0},"core_samples":{"search_records":[{"企业名称":"比音勒芬服饰股份有限公司","主营产品":"家装、包(袋、建材、饰品、体育用、皮革日用品、皮革、纺织、手套、皮革及皮革制品、服饰配件、塑料、木制、服装辅料、日用器皿及日用杂货、金属日用杂品、服装、皮箱、日用杂品综合","注册资本":"570707084.0 人民币","成立日期":"2003-01-02","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}},{"企业名称":"搜于特集团股份有限公司","主营产品":"时尚商务男装、时尚夹克、时尚淑女装、时尚风衣、时尚休闲装、时尚牛仔裤、蕾丝边外套、单件短外套、服装、浪漫校园装、时尚羽绒服","注册资本":"3051878231.0 人民币","成立日期":"2005-12-05","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}}]},"quality":{"total_sections":1,"populated_sections":1,"empty_sections":0,"coverage_pct":100},"limit":"地区条件由上游执行；若单条记录未返回地区/地址字段，报告会明确标注不可逐条独立复核。检索结果不等同于已审核供应商。","html_bytes":1070901,"markdown_bytes":15394}
- **pass** 地址解析为嵌套地区列表：该项由当前调用参数、报告同名字段、样本与局限说明共同核对。 当前冻结快照：{"technical_status":"passed","successful_data_calls":1,"calls":[{"tool":"factory_insight_factory_search","status":"data","rows":10,"total":49967,"args":{"matchKeyword":"服装","keywordType":"主营产品","pageIndex":1,"pageSize":10,"address":[["广东省"]]}}],"subject":{"enterprise":"服装","matchKeyword":"服装","keywordType":"主营产品","match_raw":"服装","resolved":true,"resolve_reason":"工厂检索模式：按关键词直查","mode":"search","address":[["广东省"]]},"metrics":[{"label":"检索结果","value":"49967","hint":"工厂检索命中数"}],"core_counts":{"sections":4,"product_stats":0,"search_records":10,"management_certs":0},"core_samples":{"search_records":[{"企业名称":"比音勒芬服饰股份有限公司","主营产品":"家装、包(袋、建材、饰品、体育用、皮革日用品、皮革、纺织、手套、皮革及皮革制品、服饰配件、塑料、木制、服装辅料、日用器皿及日用杂货、金属日用杂品、服装、皮箱、日用杂品综合","注册资本":"570707084.0 人民币","成立日期":"2003-01-02","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}},{"企业名称":"搜于特集团股份有限公司","主营产品":"时尚商务男装、时尚夹克、时尚淑女装、时尚风衣、时尚休闲装、时尚牛仔裤、蕾丝边外套、单件短外套、服装、浪漫校园装、时尚羽绒服","注册资本":"3051878231.0 人民币","成立日期":"2005-12-05","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}}]},"quality":{"total_sections":1,"populated_sections":1,"empty_sections":0,"coverage_pct":100},"limit":"地区条件由上游执行；若单条记录未返回地区/地址字段，报告会明确标注不可逐条独立复核。检索结果不等同于已审核供应商。","html_bytes":1070901,"markdown_bytes":15394}
- **pass** 不把搜索结果当作已审核供应商：该项由当前调用参数、报告同名字段、样本与局限说明共同核对。 当前冻结快照：{"technical_status":"passed","successful_data_calls":1,"calls":[{"tool":"factory_insight_factory_search","status":"data","rows":10,"total":49967,"args":{"matchKeyword":"服装","keywordType":"主营产品","pageIndex":1,"pageSize":10,"address":[["广东省"]]}}],"subject":{"enterprise":"服装","matchKeyword":"服装","keywordType":"主营产品","match_raw":"服装","resolved":true,"resolve_reason":"工厂检索模式：按关键词直查","mode":"search","address":[["广东省"]]},"metrics":[{"label":"检索结果","value":"49967","hint":"工厂检索命中数"}],"core_counts":{"sections":4,"product_stats":0,"search_records":10,"management_certs":0},"core_samples":{"search_records":[{"企业名称":"比音勒芬服饰股份有限公司","主营产品":"家装、包(袋、建材、饰品、体育用、皮革日用品、皮革、纺织、手套、皮革及皮革制品、服饰配件、塑料、木制、服装辅料、日用器皿及日用杂货、金属日用杂品、服装、皮箱、日用杂品综合","注册资本":"570707084.0 人民币","成立日期":"2003-01-02","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}},{"企业名称":"搜于特集团股份有限公司","主营产品":"时尚商务男装、时尚夹克、时尚淑女装、时尚风衣、时尚休闲装、时尚牛仔裤、蕾丝边外套、单件短外套、服装、浪漫校园装、时尚羽绒服","注册资本":"3051878231.0 人民币","成立日期":"2005-12-05","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}}]},"quality":{"total_sections":1,"populated_sections":1,"empty_sections":0,"coverage_pct":100},"limit":"地区条件由上游执行；若单条记录未返回地区/地址字段，报告会明确标注不可逐条独立复核。检索结果不等同于已审核供应商。","html_bytes":1070901,"markdown_bytes":15394}

## 离线浏览器检查

[Ego Lite 离线图表、页面溢出和脚本检查](browser-check.json)