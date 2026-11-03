# “吉利”名称候选消歧

- 用户需求：请按工厂名称检索浙江省含“吉利”的候选，比较实际企业名称和主营产品，识别同名但业务不同的记录；不要归入吉利汽车集团。
- 决策用途：支持名称检索后的主体消歧，而不是集团归属判断。
- 本轮结果：**本轮检查通过**
- 实际工具调用：1；失败 0
- 章节覆盖率：100%（不代表证据质量）

## 预期业务检查（不自动宣称通过）

- search_records 至少有两条实际返回记录
- 至少两条记录同时具备非空企业名称和主营产品
- 至少两条候选的主营产品文本存在可辨别差异
- 名称命中必须来自实际企业名称字段，不能只依赖请求关键词
- 不得把所有候选归属于同一集团

## 本轮自动检查发现


## 使用局限

- 记录地址缺失时不能验证浙江过滤效果
- 名称相似不证明股权或品牌关系

## 证据与复现

- [审计结果](result.json)
- [工具调用、结果形态与响应摘要哈希](calls.json)
- [JSON](report.json) / [HTML](report.html) / [Markdown](report.md)

```bash
python3 factory-insight-skill/scripts/compose_report.py --search '吉利' --keyword-type '工厂名称' --address '浙江省' --page-size 8 --output factory-insight-skill/output/10-jili-name-candidate-disambiguation/report.json --report-output factory-insight-skill/output/10-jili-name-candidate-disambiguation/report.html
```

## 逐场景业务复核

本轮真实产物的全部清单检查均有当前字段证据，且报告保留样本/缺失/关系边界。

- **pass** search_records 至少有两条实际返回记录：search_records有8条名称实际含‘吉利’；宁波市镇海吉利标准件厂主营汽车标准件/紧固件，浙江吉利装璜材料有限公司主营铝塑板/幕墙铝单板，产品文本差异明确，报告仅作候选样本且未归为同一集团。 当前冻结快照：{"technical_status":"passed","successful_data_calls":1,"calls":[{"tool":"factory_insight_factory_search","status":"data","rows":8,"total":200,"args":{"matchKeyword":"吉利","keywordType":"工厂名称","pageIndex":1,"pageSize":8,"address":[["浙江省"]]}}],"subject":{"enterprise":"吉利","matchKeyword":"吉利","keywordType":"工厂名称","match_raw":"吉利","resolved":true,"resolve_reason":"工厂检索模式：按关键词直查","mode":"search","address":[["浙江省"]]},"metrics":[{"label":"检索结果","value":"200","hint":"工厂检索命中数"}],"core_counts":{"sections":4,"product_stats":0,"search_records":8,"management_certs":0},"core_samples":{"search_records":[{"企业名称":"宁波市镇海吉利标准件厂","主营产品":"连接件、汽车配件、模具.材料、螺栓、汽车螺钉、汽车零部件、紧固件、垫圈、五金件.紧固件.焊接铰链、汽车标准件、汽车标准件螺钉、吉利汽配、汽配、螺母、螺钉","注册资本":"1680000.0 人民币","成立日期":"1999-04-23","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}},{"企业名称":"浙江吉利装璜材料有限公司","主营产品":"铝塑板、冲孔铝板、氟碳铝单板、铝板幕墙、雨棚铝板、铝单板、幕墙铝单板、蜂窝铝单板、石纹铝板、加强筋、冲孔铝单板","注册资本":"75000000.0 人民币","成立日期":"1997-08-12","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}}]},"quality":{"total_sections":1,"populated_sections":1,"empty_sections":0,"coverage_pct":100},"limit":"地区条件由上游执行；若单条记录未返回地区/地址字段，报告会明确标注不可逐条独立复核。检索结果不等同于已审核供应商。","html_bytes":1061362,"markdown_bytes":6009}
- **pass** 至少两条记录同时具备非空企业名称和主营产品：search_records有8条名称实际含‘吉利’；宁波市镇海吉利标准件厂主营汽车标准件/紧固件，浙江吉利装璜材料有限公司主营铝塑板/幕墙铝单板，产品文本差异明确，报告仅作候选样本且未归为同一集团。 当前冻结快照：{"technical_status":"passed","successful_data_calls":1,"calls":[{"tool":"factory_insight_factory_search","status":"data","rows":8,"total":200,"args":{"matchKeyword":"吉利","keywordType":"工厂名称","pageIndex":1,"pageSize":8,"address":[["浙江省"]]}}],"subject":{"enterprise":"吉利","matchKeyword":"吉利","keywordType":"工厂名称","match_raw":"吉利","resolved":true,"resolve_reason":"工厂检索模式：按关键词直查","mode":"search","address":[["浙江省"]]},"metrics":[{"label":"检索结果","value":"200","hint":"工厂检索命中数"}],"core_counts":{"sections":4,"product_stats":0,"search_records":8,"management_certs":0},"core_samples":{"search_records":[{"企业名称":"宁波市镇海吉利标准件厂","主营产品":"连接件、汽车配件、模具.材料、螺栓、汽车螺钉、汽车零部件、紧固件、垫圈、五金件.紧固件.焊接铰链、汽车标准件、汽车标准件螺钉、吉利汽配、汽配、螺母、螺钉","注册资本":"1680000.0 人民币","成立日期":"1999-04-23","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}},{"企业名称":"浙江吉利装璜材料有限公司","主营产品":"铝塑板、冲孔铝板、氟碳铝单板、铝板幕墙、雨棚铝板、铝单板、幕墙铝单板、蜂窝铝单板、石纹铝板、加强筋、冲孔铝单板","注册资本":"75000000.0 人民币","成立日期":"1997-08-12","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}}]},"quality":{"total_sections":1,"populated_sections":1,"empty_sections":0,"coverage_pct":100},"limit":"地区条件由上游执行；若单条记录未返回地区/地址字段，报告会明确标注不可逐条独立复核。检索结果不等同于已审核供应商。","html_bytes":1061362,"markdown_bytes":6009}
- **pass** 至少两条候选的主营产品文本存在可辨别差异：search_records有8条名称实际含‘吉利’；宁波市镇海吉利标准件厂主营汽车标准件/紧固件，浙江吉利装璜材料有限公司主营铝塑板/幕墙铝单板，产品文本差异明确，报告仅作候选样本且未归为同一集团。 当前冻结快照：{"technical_status":"passed","successful_data_calls":1,"calls":[{"tool":"factory_insight_factory_search","status":"data","rows":8,"total":200,"args":{"matchKeyword":"吉利","keywordType":"工厂名称","pageIndex":1,"pageSize":8,"address":[["浙江省"]]}}],"subject":{"enterprise":"吉利","matchKeyword":"吉利","keywordType":"工厂名称","match_raw":"吉利","resolved":true,"resolve_reason":"工厂检索模式：按关键词直查","mode":"search","address":[["浙江省"]]},"metrics":[{"label":"检索结果","value":"200","hint":"工厂检索命中数"}],"core_counts":{"sections":4,"product_stats":0,"search_records":8,"management_certs":0},"core_samples":{"search_records":[{"企业名称":"宁波市镇海吉利标准件厂","主营产品":"连接件、汽车配件、模具.材料、螺栓、汽车螺钉、汽车零部件、紧固件、垫圈、五金件.紧固件.焊接铰链、汽车标准件、汽车标准件螺钉、吉利汽配、汽配、螺母、螺钉","注册资本":"1680000.0 人民币","成立日期":"1999-04-23","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}},{"企业名称":"浙江吉利装璜材料有限公司","主营产品":"铝塑板、冲孔铝板、氟碳铝单板、铝板幕墙、雨棚铝板、铝单板、幕墙铝单板、蜂窝铝单板、石纹铝板、加强筋、冲孔铝单板","注册资本":"75000000.0 人民币","成立日期":"1997-08-12","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}}]},"quality":{"total_sections":1,"populated_sections":1,"empty_sections":0,"coverage_pct":100},"limit":"地区条件由上游执行；若单条记录未返回地区/地址字段，报告会明确标注不可逐条独立复核。检索结果不等同于已审核供应商。","html_bytes":1061362,"markdown_bytes":6009}
- **pass** 名称命中必须来自实际企业名称字段，不能只依赖请求关键词：search_records有8条名称实际含‘吉利’；宁波市镇海吉利标准件厂主营汽车标准件/紧固件，浙江吉利装璜材料有限公司主营铝塑板/幕墙铝单板，产品文本差异明确，报告仅作候选样本且未归为同一集团。 当前冻结快照：{"technical_status":"passed","successful_data_calls":1,"calls":[{"tool":"factory_insight_factory_search","status":"data","rows":8,"total":200,"args":{"matchKeyword":"吉利","keywordType":"工厂名称","pageIndex":1,"pageSize":8,"address":[["浙江省"]]}}],"subject":{"enterprise":"吉利","matchKeyword":"吉利","keywordType":"工厂名称","match_raw":"吉利","resolved":true,"resolve_reason":"工厂检索模式：按关键词直查","mode":"search","address":[["浙江省"]]},"metrics":[{"label":"检索结果","value":"200","hint":"工厂检索命中数"}],"core_counts":{"sections":4,"product_stats":0,"search_records":8,"management_certs":0},"core_samples":{"search_records":[{"企业名称":"宁波市镇海吉利标准件厂","主营产品":"连接件、汽车配件、模具.材料、螺栓、汽车螺钉、汽车零部件、紧固件、垫圈、五金件.紧固件.焊接铰链、汽车标准件、汽车标准件螺钉、吉利汽配、汽配、螺母、螺钉","注册资本":"1680000.0 人民币","成立日期":"1999-04-23","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}},{"企业名称":"浙江吉利装璜材料有限公司","主营产品":"铝塑板、冲孔铝板、氟碳铝单板、铝板幕墙、雨棚铝板、铝单板、幕墙铝单板、蜂窝铝单板、石纹铝板、加强筋、冲孔铝单板","注册资本":"75000000.0 人民币","成立日期":"1997-08-12","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}}]},"quality":{"total_sections":1,"populated_sections":1,"empty_sections":0,"coverage_pct":100},"limit":"地区条件由上游执行；若单条记录未返回地区/地址字段，报告会明确标注不可逐条独立复核。检索结果不等同于已审核供应商。","html_bytes":1061362,"markdown_bytes":6009}
- **pass** 不得把所有候选归属于同一集团：search_records有8条名称实际含‘吉利’；宁波市镇海吉利标准件厂主营汽车标准件/紧固件，浙江吉利装璜材料有限公司主营铝塑板/幕墙铝单板，产品文本差异明确，报告仅作候选样本且未归为同一集团。 当前冻结快照：{"technical_status":"passed","successful_data_calls":1,"calls":[{"tool":"factory_insight_factory_search","status":"data","rows":8,"total":200,"args":{"matchKeyword":"吉利","keywordType":"工厂名称","pageIndex":1,"pageSize":8,"address":[["浙江省"]]}}],"subject":{"enterprise":"吉利","matchKeyword":"吉利","keywordType":"工厂名称","match_raw":"吉利","resolved":true,"resolve_reason":"工厂检索模式：按关键词直查","mode":"search","address":[["浙江省"]]},"metrics":[{"label":"检索结果","value":"200","hint":"工厂检索命中数"}],"core_counts":{"sections":4,"product_stats":0,"search_records":8,"management_certs":0},"core_samples":{"search_records":[{"企业名称":"宁波市镇海吉利标准件厂","主营产品":"连接件、汽车配件、模具.材料、螺栓、汽车螺钉、汽车零部件、紧固件、垫圈、五金件.紧固件.焊接铰链、汽车标准件、汽车标准件螺钉、吉利汽配、汽配、螺母、螺钉","注册资本":"1680000.0 人民币","成立日期":"1999-04-23","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}},{"企业名称":"浙江吉利装璜材料有限公司","主营产品":"铝塑板、冲孔铝板、氟碳铝单板、铝板幕墙、雨棚铝板、铝单板、幕墙铝单板、蜂窝铝单板、石纹铝板、加强筋、冲孔铝单板","注册资本":"75000000.0 人民币","成立日期":"1997-08-12","地区/地址":"上游未返回（不可逐条复核）","地址来源字段":{}}]},"quality":{"total_sections":1,"populated_sections":1,"empty_sections":0,"coverage_pct":100},"limit":"地区条件由上游执行；若单条记录未返回地区/地址字段，报告会明确标注不可逐条独立复核。检索结果不等同于已审核供应商。","html_bytes":1061362,"markdown_bytes":6009}

## 离线浏览器检查

[Ego Lite 离线图表、页面溢出和脚本检查](browser-check.json)