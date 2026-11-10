# 本轮已有数据就绪检查

检查时间：2026-10-20T10:24:32.227989+00:00。只读既有输入、哈希、字段与脚本，未联网、未补数、未执行趋势原型或账户、未重绘旧证据。本报告是本子任务唯一新增文件。已按 README → HANDOFF → RESEARCH_CONSENSUS → NEXT_RESEARCH_TASKS → RESEARCH → DATA_SOURCES 顺序读取，并读取 AGENTS 和 REPRODUCIBILITY。用户最新授权量价机制研究优先于旧计划中的风险预算安排。

## 结论

可直接以原14条独立OHLCV作为本轮输入，共27,674条原始保存行、27,655条合格价格观察。覆盖15个固定案例的12个唯一标的，以及2条通信主题代理；加入黄金GOLD复查后是18个固定窗口，仍然只有14个唯一标的。无需重跑准备脚本。

14个CSV哈希逐一与既有manifest一致；manifest记录的65个依赖在其原绝对路径全部存在且哈希一致，映射到本工作区后存在的45个文件也全部一致。12个交集标的与事件结构保存信号的完整日期索引一致，close/volume以rtol=atol=1e-12比较逐日无差异。两通信代理不在原27条事件结构信号中。

## 输入入口与口径

- 统一CSV目录：`/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-boundary-response-20261020/inputs/`。每个标的是`{symbol}.csv`。
- 源、权益调整、病例覆盖及CSV哈希：`/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-boundary-response-20261020/inputs/manifest.json`与各`{symbol}.source.json`。
- 独立价格观察规则与明确剔除日期：`/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-boundary-response-20261020/inputs/observation-mask-addendum.json`。
- 18窗口：`/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-boundary-response-20261020/protocol-v0.json`的`cases`，或`/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-tail-cost-20261020/inputs/case-catalog.json`。
- 输入manifest的`cases`只有17项（15+2通信），额外GOLD在实验protocol的18项中；不要拿输入manifest的17当成全部固定窗口。
- 原15窗口：`/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/results/pv-event-structure-20261020/protocol.json`的`cases`。
- 原27条保存信号：`/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/results/pv-event-structure-20261020/{symbol}-signals.csv`。

统一核心字段为`date, open, high, low, close, volume`；追溯字段包括`raw_open/raw_high/raw_low/raw_close/raw_volume, adjustment_factor, volume_factor, cash_signal_adjustment, split_ratio, observed_bar, synthetic_event_bar, source_anomaly`及旧诊断标志。具体CSV仍应按列名读，不能依赖列位置。日期唯一且有序；不得补齐日历或前填量。

| 标的 | 完整起日 | 末日 | 保存行 | 合格价格行 | CSV SHA256 |
|---|---|---|---:|---:|---|
| USHJ518880 | 2018-07-17 | 2026-10-16 | 2000 | 2000 | `81b982157bc23296b3d7b46f4a909983e45441b7d5cf2839588723ef5ef36c2e` |
| USHJ512480 | 2019-06-12 | 2026-10-16 | 1781 | 1781 | `c1beba864692a65919f14246abcfc243b3e6012861c09640707ee295c2951394` |
| USHJ510300 | 2018-07-17 | 2026-10-16 | 2000 | 2000 | `d58bda48420e58f0ae3b263e43558f8871eafed0a7f888e33a2cfbd2a058ac06` |
| HK00002 | 2020-01-02 | 2026-10-16 | 1674 | 1671 | `3613fcdc18ff5f1238c7575a7610dcf1321415f34b523897fd650850b0fed0c3` |
| HK09618 | 2020-06-18 | 2026-10-16 | 1560 | 1557 | `891ebf91c808069a37d8ad1c743dd58617cd3642c596ae38b3ae451125c28e8d` |
| HK00700 | 2020-01-02 | 2026-10-16 | 1674 | 1671 | `4c9f32f947e755f86e8e39cebe7c734a4b13a457a88cacd314dd8fbc8d2c854d` |
| HK03033 | 2020-08-28 | 2026-10-16 | 1511 | 1507 | `ad7b0cb053c6374f904b0c6f995d518192a1df3083f4b80dfe62b25b21ec0937` |
| HK00101 | 2020-01-02 | 2026-10-16 | 1674 | 1671 | `4a206ade69d8ad38158660ae70cf3a9f635956ba6dae9d00c2d7ecf8998a131d` |
| HK03690 | 2020-04-27 | 2026-10-16 | 1596 | 1593 | `7d78e3bd0ff3bb2d76a6d0a100da0bf0efe5ee29660ad4a3f67b048b2cc06a98` |
| 600919.SH | 2023-09-06 | 2026-10-16 | 750 | 750 | `d7d364cc2ee655319fb0e31c9c45c6a626585744b7fc2096101601ab69d076eb` |
| 600059.SH | 2023-09-06 | 2026-10-16 | 750 | 750 | `68277e7f058a44d195dd4ba85a943c713d49f32c9a4152febe7137fb08ebabad` |
| 600917.SH | 2023-09-06 | 2026-10-16 | 750 | 750 | `200449e3a8c54b6c5134c05b03c024ed56c9d722c53e03e1ebfb5334136c30b6` |
| URFI881129 | 2007-08-01 | 2026-10-16 | 4666 | 4666 | `4ef6020bef8780840c2f2ae82cf3204e05b28c356713c1f73c81b1db425a281b` |
| UZZI000994 | 2005-01-04 | 2026-10-16 | 5288 | 5288 | `782663f3f234ce8e9c6694c1d85e7d198ade4b171f2ba144005660f63d1e9482` |

ETF三个标的来自既有Tencent独立OHLC及本地Eastmoney权益记录；按旧层累计总回报价格独立得到每日因子后，同乘四价，量按既有拆股比例调整。港股5只个股及HK03033来自既有Tencent源，个股权益沿用旧处理；3只A股来自同花顺USHA signal parquet且已核对原始JSON，其因子为理论除权价调整，不是现金总回报会计；2条通信指数来自同花顺canonical，不复权。具体原文件绝对路径及源哈希在上述manifest/source中，不需要重新构造价格。

总回报四价是收盘后的信号研究口径，不能作为已知可成交开盘报价。原始量单位没有统一认证，不比较不同资产原始量高低；同标的相对量可使用。ETF拆股量调整沿用旧处理，不将原始量与调整量交叉使用。通信是指数聚合量，不是截图中未知代码ETF，也无历史成分完整性保证。

## 价格时钟和异常（必须保持）

- 独立规则：四价有限为正且H/L包含O/C、observed_bar=true、非synthetic_event_bar、非明确源异常、非已核实占位日。旧`valid/geometry_valid`曾联合要求正量，不能作为一般价格时钟。
- volume有限且正表示已知量证据；未知/零量不能自动赋予“缩量”含义，也不能单靠量缺失删除原本有效价格。此冻结集清理价格异常后每行恰好都有正量，不推广这个巧合。
- HK00002/HK09618/HK00700/HK03033/HK00101/HK03690各剔除2023-07-17、2023-09-01、2023-09-08：原源零量、OHLC等于前收，并且另一份保存同花顺源无该日。是已核实供应商占位，不是一般volume=0过滤。
- HK03033还剔除2020-08-28（IPO开盘/最高价源异常）。它不在固定窗口内，但涉及全历史预热时钟；原close+volume基座可能保留该日。原基座优先读取原保存信号按日期对齐；若重算并改变时钟，必须单列数据变化，不能归为量的贡献。
- USHJ512480 2024-10-08正量且H=L，保留价格观察，range_defined=false；不得补造振幅、除以零或默认收盘位置为0.5。
- 旧检查发现URFI881129缺2013-01-11、UZZI000994缺2019-04-02，与保存沪深300日历比较所得；固定通信窗口未见这两个缺日。全体无>14日历天内部跳跃，不等于所有单日完整性已认证。

## 18个固定窗口

| ID | 标的 | 起日 | 末日 | 旧请求锚点 | 窗内合格价格行 |
|---|---|---|---|---|---:|
| S1 | USHJ518880 | 2025-01-01 | 2026-03-31 | 2025-09-01 | 299 |
| S2 | HK00002 | 2024-01-01 | 2025-03-31 | 2024-07-01 | 306 |
| F1 | USHJ512480 | 2024-08-01 | 2024-12-31 | 2024-09-30 | 102 |
| F2 | HK09618 | 2024-08-01 | 2024-12-31 | 2024-09-30 | 103 |
| R1 | HK00700 | 2025-01-01 | 2025-12-31 | 2025-05-01 | 246 |
| R2 | USHJ518880 | 2024-01-01 | 2024-12-31 | 2024-06-03 | 242 |
| B1 | USHJ512480 | 2026-04-01 | 2026-10-16 | 2026-07-01 | 132 |
| B2 | HK03033 | 2022-01-01 | 2022-12-31 | 2022-04-01 | 246 |
| C1 | USHJ510300 | 2023-01-01 | 2023-12-31 | 2023-07-03 | 242 |
| C2 | HK00101 | 2023-01-01 | 2023-12-31 | 2023-07-03 | 243 |
| W1 | HK03033 | 2023-01-01 | 2023-12-31 | 2023-07-03 | 243 |
| W2 | HK03690 | 2022-03-01 | 2022-12-31 | 2022-07-01 | 208 |
| S3 | 600919.SH | 2024-01-01 | 2024-12-31 | 2024-07-04 | 242 |
| C3 | 600059.SH | 2024-01-01 | 2024-12-31 | 2024-07-04 | 242 |
| C5 | 600917.SH | 2024-01-01 | 2024-12-31 | 2024-07-04 | 242 |
| COM1 | URFI881129 | 2025-10-01 | 2026-09-30 | 2026-08-03 | 241 |
| COM2 | UZZI000994 | 2025-10-01 | 2026-09-30 | 2026-08-03 | 241 |
| GOLD | USHJ518880 | 2026-01-01 | 2026-09-30 | 2026-04-01 | 181 |

这里锚点是上一轮观察协议的锚点，供复查追溯，不自动成为新算法输入。应在完整历史上预热后截取固定窗口画图，不把每个窗口重新初始化；旧边界观察器只展示锚点周边短窗，不能代替完整趋势轨迹检查。所有历史已见，分层显示或遮未来不改变开发数据身份。

## 27条冻结信号的覆盖差异

原27条共45,534行，字段：`date, confirmation, leg_direction, developing_extreme, confirmed_pivot, structure_floor, event, target, entered, exited, pivot_age, close, volume, price_target, momentum_target`。没有OHLC；不能由close伪造振幅/收盘位置。本轮14条OHLC与旧27条的交集是12条。

旧27条中以下15条不在本轮已核验OHLC准备集：`HK00005, HK00883, HK02800, HK02820, HK02845, HK03110, USHJ511010, USHJ512010, USHJ512400, USHJ512660, USHJ512690, USHJ512800, USHJ512980, USHJ515030, USHJ515220`。这表示没有该轮已准备OHLC，不表示仓库绝无原始源。当前无需扩充；若候选依赖OHLC，实证范围应诚实写14条/18窗，不能宣称27条同等覆盖。

| 保存信号 | 行数 | 起日 | 末日 | 本轮OHLC覆盖 | SHA256 |
|---|---:|---|---|---|---|
| 600059.SH | 750 | 2023-09-06 | 2026-10-16 | 有 | `88077ec4d8b600e7bc9c6b7343af07f0280ad9e59632b3ae24c6e2cff1271451` |
| 600917.SH | 750 | 2023-09-06 | 2026-10-16 | 有 | `f34a33a3b2e95b5926621e71e5404e08544318e4088f2e296556eb0f8990157a` |
| 600919.SH | 750 | 2023-09-06 | 2026-10-16 | 有 | `5acd4e4421b8772e659f5a4d50ed440c7ae369234dde8c373c6d611dacbc6027` |
| HK00002 | 1674 | 2020-01-02 | 2026-10-16 | 有 | `4f91c2cfccfcfd58da06f6ea7fad918fcd46ca5d882d9d8de4a6f0d433abb26c` |
| HK00005 | 1674 | 2020-01-02 | 2026-10-16 | 无 | `03982df8fcb862269b6eba806a5c6426d5e1f6bfa6f667b9c4fb1f238bf0c5a0` |
| HK00101 | 1674 | 2020-01-02 | 2026-10-16 | 有 | `28435e33f94cd46fe99d066d6d1034fecaf9ebb2b8db44e92d69e810980c1836` |
| HK00700 | 1674 | 2020-01-02 | 2026-10-16 | 有 | `5727f527474bb735a21edd3fbce5428e434a86d97d675e798c05ea07b1dffdf0` |
| HK00883 | 1674 | 2020-01-02 | 2026-10-16 | 无 | `49dadb76e0511b705e1b6f13870c8455c5fa2fae34e81a3f5eb98869dc1b5d03` |
| HK02800 | 2000 | 2018-09-04 | 2026-10-16 | 无 | `599b47d18939b7d86d8151b0c346ed1e8d1be6057d81f596e625b6a9a6bb4391` |
| HK02820 | 1784 | 2019-07-25 | 2026-10-16 | 无 | `dfb12106e3b32db547ac2c97ea4bd06ea50985d0a52edc5c66e4ad4be1c3feed` |
| HK02845 | 1663 | 2020-01-17 | 2026-10-16 | 无 | `76fa282e4a51894ee97dcffcbaded7d736f538e786ebc336e55c915618373e77` |
| HK03033 | 1511 | 2020-08-28 | 2026-10-16 | 有 | `289ce858006bf90b4e58a075a208397d42aaf89378145e561ce5e1b57720df7f` |
| HK03110 | 2000 | 2018-09-04 | 2026-10-16 | 无 | `00d22dea2e6943cb542f54cbb3fb8d9175c7a8e08a955c02fc0653c5bfe50add` |
| HK03690 | 1596 | 2020-04-27 | 2026-10-16 | 有 | `7afaef3bd02ad6cc9632cacc003af4f12ea4733436c738fed1c8e79d3276ceb2` |
| HK09618 | 1560 | 2020-06-18 | 2026-10-16 | 有 | `aa0b87e57b944d5c8af8dbab6a24691894cd8ab2d8aee7603fd27666270ca0a9` |
| USHJ510300 | 2000 | 2018-07-17 | 2026-10-16 | 有 | `e66d9cbfea510436792ec3f92d3e9380f0fa72f2cfb4b07ae647b800b499c20d` |
| USHJ511010 | 2000 | 2018-07-17 | 2026-10-16 | 无 | `f18d373bccc2d85687977f27e97cba4429633daa16771fcb1d3b4d92098bc2d7` |
| USHJ512010 | 2000 | 2018-07-16 | 2026-10-16 | 无 | `0876fa1e4d6199aad7829a2c9d7f3724e24d9794fc04effb36bc640fa7a4e6e5` |
| USHJ512400 | 2000 | 2018-07-17 | 2026-10-16 | 无 | `f7951961a8d979170e81cc7fe002b4aed150da4064ee9a0b8c5ff40b48435660` |
| USHJ512480 | 1781 | 2019-06-12 | 2026-10-16 | 有 | `a6e472553926e7af13973ecad4204fd649a0c324afa3b06c3c9241ccee318301` |
| USHJ512660 | 2000 | 2018-07-17 | 2026-10-16 | 无 | `9a2634c8fd9aade07d6b2cdf2d06159fc8887104add246e45d0ddb2174c63f1b` |
| USHJ512690 | 1807 | 2019-05-06 | 2026-10-16 | 无 | `0f61581bb05e180fa64879bfc6307e33d94e7eeea508ca8bb46ba045f23973dc` |
| USHJ512800 | 2000 | 2018-07-17 | 2026-10-16 | 无 | `39bce751e25c995ad09103d7fc038580ab4f0001582063cca0bbdaf709122e8b` |
| USHJ512980 | 2000 | 2018-07-17 | 2026-10-16 | 无 | `77db250b04bb5bd2d442028ffe97873570b912359f096ff4745d61e1d1a34be4` |
| USHJ515030 | 1605 | 2020-03-04 | 2026-10-16 | 无 | `5834ecfe2fcab1e018d0285de34892f12d327eb820301dd391c527c2ce108300` |
| USHJ515220 | 1607 | 2020-03-02 | 2026-10-16 | 无 | `3241ed2fda8a1fd28090b2f2f97dc30ac730e8b20c2c16644f0870864ebdcee6` |
| USHJ518880 | 2000 | 2018-07-17 | 2026-10-16 | 有 | `d739e165ece137f7b0f14c786cf85a85e8e970980bb6d79124cf6223ec8cc5c4` |

## 可复用环境与绘图入口

- Python：`/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python`，3.13.7；pandas 3.0.1、NumPy 2.4.3、Matplotlib 3.11.2。正式repos旧venv链接不保证可用。无需安装依赖。
- 使用`PYTHONDONTWRITEBYTECODE=1`避免写旧代码目录；绘图建议`MPLCONFIGDIR=/private/tmp/pv-mpl XDG_CACHE_HOME=/private/tmp/pv-cache`，避免不可写用户缓存导致字体错误。
- `/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-boundary-response-20261020/code/boundary_study.py`的`eligible_prices`（第36行）是可安全import的独立时钟函数；需显式传addendum对应symbol的exclude_price_dates。`draw_view`（第281行）含OHLC蜡烛、对数价格轴、量柱和前缀坐标裁剪，可参考绘图部件；其固定边界逻辑不是新机制。
- 原`run_event_structure.py`顶层导入账户runner，不应作为仅轨迹研究的import入口。纯`trend_event_structure.py`或tail-cost的`baseline_event_structure.py`只依赖NumPy/pandas，可独立加载。旧`verify_baseline.py`拒绝覆盖且目标固定，不直接重跑；复核应在本轮独立输出。
- 不运行prepare_ohlcv.py、旧boundary main或旧账户runner；新图和新因果检查全部保存本轮目录，保留旧图及失败。

## 关键冻结哈希

| 文件 | SHA256 |
|---|---|
| `research_rounds/pv-boundary-response-20261020/inputs/manifest.json` | `ae0d86a0762a2347be7d0f4705e4ad6406f7115a88120773d37536a20a1bb9d4` |
| `research_rounds/pv-boundary-response-20261020/inputs/freeze.json` | `cc0c8ec1ff53be9eb40440841eea56969ab4b75721492e629c5e64c65c3731e5` |
| `research_rounds/pv-boundary-response-20261020/inputs/observation-mask-addendum.json` | `386457b7e5e13c60e84334cb62803ca872caf7fea07c44cf05d7955f2d4ddd94` |
| `research_rounds/pv-boundary-response-20261020/protocol-v0.json` | `c5c26436bbbf54c478bcf0d1621ec78fa2e4ad5b182a6771203faff5223e240d` |
| `research_rounds/pv-boundary-response-20261020/code/boundary_study.py` | `85617d4b1424272704f8b1fdf43359ff3c320ecaef1ac63b0f5a7c0733947221` |
| `TradingAlarm/research/results/pv-event-structure-20261020/protocol.json` | `23f3b015e834e38ff2376fa961fc5c73e34ad2ecfa2b7f8a7f27164364099b0b` |
| `TradingAlarm/research/results/pv-event-structure-20261020/code/trend_event_structure.py` | `b61e889e684305cbb45223e0e2dd8da324e8e8d0a2d201794e2749eb9441540e` |
| `TradingAlarm/research/results/pv-event-structure-20261020/trajectory-manifest.json` | `c563adc50b5f46db5c2bf1b52ef6dd7cd68f1246ff7104c3086726f8dcc194d5` |
| `research_rounds/pv-tail-cost-20261020/inputs/source-manifest.json` | `9999b53ab1b467b1908e1115892bb91d973034418474ff15a7b41baa074a503a` |

本次仅重查文件身份、字段、日期索引和观察筛选；没有重跑原权息前缀验证、没有重算任何模型，也没有把旧27次纯数据前缀检查冒充本轮新机制因果检查。已有source/manifest保留原准备过程及其限制。
