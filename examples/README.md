# factory-insight-skill：已验收示例

本目录只展示 **4 个完全通过的真实正向场景**（最低要求4例）。

每例均为真实、非空、非缓存调用；技术检查、独立业务检查和离线浏览器检查全部通过。报告保持原实测字节，不把空数据、报错处理或仅生成页面计作通过。

| 场景 | 真实使用需求 | 报告 |
|---|---|---|
| [广东服装工厂寻源](04-apparel-guangdong/README.md) | 请在广东省检索主营服装的工厂。 | [HTML](04-apparel-guangdong/report.html) / [MD](04-apparel-guangdong/report.md) / [JSON](04-apparel-guangdong/report.json) |
| [多地区工业机器人工厂](06-robotics-multiregion/README.md) | 请同时在广东省和江苏省苏州市查找工业机器人相关工厂。 | [HTML](06-robotics-multiregion/report.html) / [MD](06-robotics-multiregion/report.md) / [JSON](06-robotics-multiregion/report.json) |
| [潮州陶瓷候选产品核查](09-chaozhou-ceramic-product-candidates/README.md) | 请按主营产品检索广东省潮州市的陶瓷工厂候选，列出实际返回的企业名称、主营产品和登记辅助字段；地区只作为查询条件，不声称逐条地址已验证。 | [HTML](09-chaozhou-ceramic-product-candidates/report.html) / [MD](09-chaozhou-ceramic-product-candidates/report.md) / [JSON](09-chaozhou-ceramic-product-candidates/report.json) |
| [“吉利”名称候选消歧](10-jili-name-candidate-disambiguation/README.md) | 请按工厂名称检索浙江省含“吉利”的候选，比较实际企业名称和主营产品，识别同名但业务不同的记录；不要归入吉利汽车集团。 | [HTML](10-jili-name-candidate-disambiguation/report.html) / [MD](10-jili-name-candidate-disambiguation/report.md) / [JSON](10-jili-name-candidate-disambiguation/report.json) |

- [逐例验收结果](results.json) · [业务复核](review.json) · [证据摘要](evidence-index.json)
- [完整测试记录](../test-records/live-replaced-20261027/README.md)仅用于审计，不属于可展示示例。
- 当前数据与结论限于原查询时点及公开样本；覆盖率不代表准确率或低风险。
