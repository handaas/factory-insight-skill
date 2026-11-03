# 潮州陶瓷候选产品核查

- 用户需求：请按主营产品检索广东省潮州市的陶瓷工厂候选，列出实际返回的企业名称、主营产品和登记辅助字段；地区只作为查询条件，不声称逐条地址已验证。
- 决策用途：建立可按主营产品人工复核的陶瓷候选表。
- 本轮结果：**本轮检查通过**
- 实际工具调用：1；失败 0
- 章节覆盖率：100%（不代表证据质量）

## 预期业务检查（不自动宣称通过）

- search_records 至少有两条实际返回记录
- 至少两条记录同时具备非空企业名称和主营产品
- 每条计入候选的记录还应具备成立日期或注册资本至少一项
- 候选相关性必须由主营产品文本支持，不能只用命中总数或 address 参数
- 报告明确记录地址缺失时无法逐条验证地区效果

## 本轮自动检查发现


## 使用局限

- 地址过滤效果不能从缺失的记录地址独立复核
- 候选不等于已验厂或具备产能

## 证据与复现

- [审计结果](result.json)
- [工具调用、结果形态与响应摘要哈希](calls.json)
- [JSON](report.json) / [HTML](report.html) / [Markdown](report.md)

```bash
python3 factory-insight-skill/scripts/compose_report.py --search '陶瓷' --keyword-type '主营产品' --address '广东省,潮州市' --page-size 10 --output factory-insight-skill/output/09-chaozhou-ceramic-product-candidates/report.json --report-output factory-insight-skill/output/09-chaozhou-ceramic-product-candidates/report.html
```

## 逐场景业务复核

本轮真实产物的全部清单检查均有当前字段证据，且报告保留样本/缺失/关系边界。

- **pass** search_records 至少有两条实际返回记录：search_records为10/3746；潮州三环与广东四通均同时有企业名称、含陶瓷的主营产品、成立日期和注册资本。报告逐条地址均标‘上游未返回（不可逐条复核）’，未把address请求回显当地区证据。 当前冻结快照：{"technical_status":"passed","successful_data_calls":1,"calls":[{"tool":"factory_insight_factory_search","status":"data","rows":10,"total":3746,"args":{"matchKeyword":"陶瓷","keywordType":"主营产品","pageIndex":1,"pageSize":10,"address":[["广东省","潮州市"]]}}],"subject":{"enterprise":"陶瓷","matchKeyword":"陶瓷","keywordType":"主营产品","match_raw":"陶瓷","resolved":true,"resolve_reason":"工厂检索模式：按关键词直查","mode":"search","address":[["广东省","潮州市"]]},"metrics":[{"label":"检索结果","value":"3746","hint":"工厂检索命中数"}],"core_counts":{"sections":4,"product_stats":0,"search_records":10,"management_certs":0},"core_samples":{"search_records":[{"企业名称":"潮州三环(集团)股份有限公司","主营产品":"电子陶瓷元件、电阻器与电位器、固定电阻器、氧化物陶瓷、振荡器、电阻器、氧化铝陶瓷基板、连接器、光通讯","注册资本":"1916497371.0 人民币","成立日期":"1992-12-10","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}},{"企业名称":"广东四通集团股份有限公司","主营产品":"建材、陶瓷制品、管件、纸制品 不含印、仿古家具、工艺陶瓷、四通、卫生洁具、家装、日用瓷","注册资本":"320016000.0 人民币","成立日期":"1997-08-29","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}}]},"quality":{"total_sections":1,"populated_sections":1,"empty_sections":0,"coverage_pct":100},"limit":"地区条件由上游执行；若单条记录未返回地区/地址字段，报告会明确标注不可逐条独立复核。检索结果不等同于已审核供应商。","html_bytes":1062808,"markdown_bytes":7203}
- **pass** 至少两条记录同时具备非空企业名称和主营产品：search_records为10/3746；潮州三环与广东四通均同时有企业名称、含陶瓷的主营产品、成立日期和注册资本。报告逐条地址均标‘上游未返回（不可逐条复核）’，未把address请求回显当地区证据。 当前冻结快照：{"technical_status":"passed","successful_data_calls":1,"calls":[{"tool":"factory_insight_factory_search","status":"data","rows":10,"total":3746,"args":{"matchKeyword":"陶瓷","keywordType":"主营产品","pageIndex":1,"pageSize":10,"address":[["广东省","潮州市"]]}}],"subject":{"enterprise":"陶瓷","matchKeyword":"陶瓷","keywordType":"主营产品","match_raw":"陶瓷","resolved":true,"resolve_reason":"工厂检索模式：按关键词直查","mode":"search","address":[["广东省","潮州市"]]},"metrics":[{"label":"检索结果","value":"3746","hint":"工厂检索命中数"}],"core_counts":{"sections":4,"product_stats":0,"search_records":10,"management_certs":0},"core_samples":{"search_records":[{"企业名称":"潮州三环(集团)股份有限公司","主营产品":"电子陶瓷元件、电阻器与电位器、固定电阻器、氧化物陶瓷、振荡器、电阻器、氧化铝陶瓷基板、连接器、光通讯","注册资本":"1916497371.0 人民币","成立日期":"1992-12-10","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}},{"企业名称":"广东四通集团股份有限公司","主营产品":"建材、陶瓷制品、管件、纸制品 不含印、仿古家具、工艺陶瓷、四通、卫生洁具、家装、日用瓷","注册资本":"320016000.0 人民币","成立日期":"1997-08-29","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}}]},"quality":{"total_sections":1,"populated_sections":1,"empty_sections":0,"coverage_pct":100},"limit":"地区条件由上游执行；若单条记录未返回地区/地址字段，报告会明确标注不可逐条独立复核。检索结果不等同于已审核供应商。","html_bytes":1062808,"markdown_bytes":7203}
- **pass** 每条计入候选的记录还应具备成立日期或注册资本至少一项：search_records为10/3746；潮州三环与广东四通均同时有企业名称、含陶瓷的主营产品、成立日期和注册资本。报告逐条地址均标‘上游未返回（不可逐条复核）’，未把address请求回显当地区证据。 当前冻结快照：{"technical_status":"passed","successful_data_calls":1,"calls":[{"tool":"factory_insight_factory_search","status":"data","rows":10,"total":3746,"args":{"matchKeyword":"陶瓷","keywordType":"主营产品","pageIndex":1,"pageSize":10,"address":[["广东省","潮州市"]]}}],"subject":{"enterprise":"陶瓷","matchKeyword":"陶瓷","keywordType":"主营产品","match_raw":"陶瓷","resolved":true,"resolve_reason":"工厂检索模式：按关键词直查","mode":"search","address":[["广东省","潮州市"]]},"metrics":[{"label":"检索结果","value":"3746","hint":"工厂检索命中数"}],"core_counts":{"sections":4,"product_stats":0,"search_records":10,"management_certs":0},"core_samples":{"search_records":[{"企业名称":"潮州三环(集团)股份有限公司","主营产品":"电子陶瓷元件、电阻器与电位器、固定电阻器、氧化物陶瓷、振荡器、电阻器、氧化铝陶瓷基板、连接器、光通讯","注册资本":"1916497371.0 人民币","成立日期":"1992-12-10","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}},{"企业名称":"广东四通集团股份有限公司","主营产品":"建材、陶瓷制品、管件、纸制品 不含印、仿古家具、工艺陶瓷、四通、卫生洁具、家装、日用瓷","注册资本":"320016000.0 人民币","成立日期":"1997-08-29","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}}]},"quality":{"total_sections":1,"populated_sections":1,"empty_sections":0,"coverage_pct":100},"limit":"地区条件由上游执行；若单条记录未返回地区/地址字段，报告会明确标注不可逐条独立复核。检索结果不等同于已审核供应商。","html_bytes":1062808,"markdown_bytes":7203}
- **pass** 候选相关性必须由主营产品文本支持，不能只用命中总数或 address 参数：search_records为10/3746；潮州三环与广东四通均同时有企业名称、含陶瓷的主营产品、成立日期和注册资本。报告逐条地址均标‘上游未返回（不可逐条复核）’，未把address请求回显当地区证据。 当前冻结快照：{"technical_status":"passed","successful_data_calls":1,"calls":[{"tool":"factory_insight_factory_search","status":"data","rows":10,"total":3746,"args":{"matchKeyword":"陶瓷","keywordType":"主营产品","pageIndex":1,"pageSize":10,"address":[["广东省","潮州市"]]}}],"subject":{"enterprise":"陶瓷","matchKeyword":"陶瓷","keywordType":"主营产品","match_raw":"陶瓷","resolved":true,"resolve_reason":"工厂检索模式：按关键词直查","mode":"search","address":[["广东省","潮州市"]]},"metrics":[{"label":"检索结果","value":"3746","hint":"工厂检索命中数"}],"core_counts":{"sections":4,"product_stats":0,"search_records":10,"management_certs":0},"core_samples":{"search_records":[{"企业名称":"潮州三环(集团)股份有限公司","主营产品":"电子陶瓷元件、电阻器与电位器、固定电阻器、氧化物陶瓷、振荡器、电阻器、氧化铝陶瓷基板、连接器、光通讯","注册资本":"1916497371.0 人民币","成立日期":"1992-12-10","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}},{"企业名称":"广东四通集团股份有限公司","主营产品":"建材、陶瓷制品、管件、纸制品 不含印、仿古家具、工艺陶瓷、四通、卫生洁具、家装、日用瓷","注册资本":"320016000.0 人民币","成立日期":"1997-08-29","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}}]},"quality":{"total_sections":1,"populated_sections":1,"empty_sections":0,"coverage_pct":100},"limit":"地区条件由上游执行；若单条记录未返回地区/地址字段，报告会明确标注不可逐条独立复核。检索结果不等同于已审核供应商。","html_bytes":1062808,"markdown_bytes":7203}
- **pass** 报告明确记录地址缺失时无法逐条验证地区效果：search_records为10/3746；潮州三环与广东四通均同时有企业名称、含陶瓷的主营产品、成立日期和注册资本。报告逐条地址均标‘上游未返回（不可逐条复核）’，未把address请求回显当地区证据。 当前冻结快照：{"technical_status":"passed","successful_data_calls":1,"calls":[{"tool":"factory_insight_factory_search","status":"data","rows":10,"total":3746,"args":{"matchKeyword":"陶瓷","keywordType":"主营产品","pageIndex":1,"pageSize":10,"address":[["广东省","潮州市"]]}}],"subject":{"enterprise":"陶瓷","matchKeyword":"陶瓷","keywordType":"主营产品","match_raw":"陶瓷","resolved":true,"resolve_reason":"工厂检索模式：按关键词直查","mode":"search","address":[["广东省","潮州市"]]},"metrics":[{"label":"检索结果","value":"3746","hint":"工厂检索命中数"}],"core_counts":{"sections":4,"product_stats":0,"search_records":10,"management_certs":0},"core_samples":{"search_records":[{"企业名称":"潮州三环(集团)股份有限公司","主营产品":"电子陶瓷元件、电阻器与电位器、固定电阻器、氧化物陶瓷、振荡器、电阻器、氧化铝陶瓷基板、连接器、光通讯","注册资本":"1916497371.0 人民币","成立日期":"1992-12-10","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}},{"企业名称":"广东四通集团股份有限公司","主营产品":"建材、陶瓷制品、管件、纸制品 不含印、仿古家具、工艺陶瓷、四通、卫生洁具、家装、日用瓷","注册资本":"320016000.0 人民币","成立日期":"1997-08-29","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}}]},"quality":{"total_sections":1,"populated_sections":1,"empty_sections":0,"coverage_pct":100},"limit":"地区条件由上游执行；若单条记录未返回地区/地址字段，报告会明确标注不可逐条独立复核。检索结果不等同于已审核供应商。","html_bytes":1062808,"markdown_bytes":7203}

## 离线浏览器检查

[Ego Lite 离线图表、页面溢出和脚本检查](browser-check.json)