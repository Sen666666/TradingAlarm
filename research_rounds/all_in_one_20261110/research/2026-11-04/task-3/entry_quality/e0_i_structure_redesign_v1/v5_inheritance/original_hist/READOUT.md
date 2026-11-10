原2022—2024 No60 B账中，严格条件下找到2个“早CP层已退、后ADD仍留”的分层保护存续analog，**没有最终赢家例**。两个campaign最终净贡献分别为−692.5907634693、−2074.2869815689145元；它们不能包装成健康趋势或V5赢家继承验证。

先查13条已有详细链，再按1677个原campaign索引核2265层、788个真实模拟CP卖receipt/1081个CP卖parts。筛选要求：`CP1_add_protection`卖parts完成较早层退出；更晚ADD在该卖日前已经入场、并在该卖出后仍未平。只有2个事件候选，正终值campaign候选0。部分卖出而仍有原退出责任不叫继承。

| 股票/旧层→后ADD | 提出退出CLOSE | 原调整C | t−1旧层线 | t−1后ADD线 | 原CP代理卖/仍留 |
|---|---|---:|---:|---:|---|
| 杭州银行600926：1998→2037 | 2024-11-22 | 33.8903536024 | 33.9304352261 | 33.8884128738 | 11/25卖1998的900股；2037仍100股 |
| 虹软688088：1156→1213 | 2023-04-13 | 37.5783703931 | 38.1768862655 | 36.5763913969 | 4/14卖1156的380股；1213仍377股 |

两例均满足`C<=旧层旧线`而`C>后ADD旧线`，退出请求明确只列旧层。杭州原`audit[18806]`的layers=[1998]、`trades[3831]`在11/25 OPEN raw13.46/代理13.453270卖；虹软`audit[10288]`只列[1156]、`trades[2129]`在4/14 raw37.30/代理37.28135卖。后ADD在退出申请至卖出期间没有自己的退出请求；卖出日CLOSE原本股pending_sells已清，日终仍持后ADD。不能因申请CLOSE的symbol pending包含本股，就误判后ADD也被选中退出；具体层目标与卖后pending均已核。

杭州2037卖后线33.88841287383867，后来至12/24才因ACT_pause退出。两层原保存stock_structure均为`600926.SH|0|2024-09-23`，I_target从11/22至12/24一直1。11/22及11/25原E0 event均0、CP receipt均False；I_floor均33.19922032085739，rawC分别13.45/13.50。当日G1为−2，I持续不表示强势。

虹软1213卖后线36.57639139690156，后来4/18才因自身CP保护退出。两层原root均`688088.SH|0|2023-03-15`，I_target从4/13至4/18一直1。4/13及4/14原E0 event均0、CP receipt均False；I_floor均34.808690285857445，rawC分别37.04/36.47。当日G1为−3。

四层原成交role/pool均MOBILE/confirmed；这不是V5 probe身份，confirmed也不是V5 mature。原stock_structure仅旧E0入场root旁注；保存标签相同、I没有OFF，仍不能保证同一V3版本/generation。两股V3 mature及结构ID均写UNKNOWN/未映射，本任务没有新跑V3或生成candidate_id。

已知非例：海能达2017/2039均11/4申请CP退出、11/5卖，留下的是CORE1994；太保1904/1914/1931在10/9申请、10/10同退。它们均不能称后ADD健康继承。原模拟账receipt不是券商/交易所ACK；这里核的是原执行记录与pending清理事实。

证据入口：

- [TWO_ORIGINAL_LAYER_SURVIVAL_ANALOGS.json](TWO_ORIGINAL_LAYER_SURVIVAL_ANALOGS.json)：旧线/C/目标层/原卖单、原日终剩余股数与线、逐日I/E0/CP/旧root和全部源索引。
- [ORIGINAL_BUY_POOL_ROLE_JOURNALS.json](ORIGINAL_BUY_POOL_ROLE_JOURNALS.json)：四层原出生role/pool及journal索引。
- [COVERAGE_AND_SEARCH_RECEIPT.json](COVERAGE_AND_SEARCH_RECEIPT.json)：分母、筛选定义、source SHA与零新模型/账户声明。

未编辑V5主卡，未计算新股数、持仓路径、资金或收益。
