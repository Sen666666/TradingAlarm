# No60 原运行市值输入的时间语义与证据边界

结论：现存加载链和代码明确把 **2026-10-24 观测的固定市值选择快照**用于历史研究；`SelectionFact.read(clock)`直接返回固定值，不按历史决策日切换市值，也不因观测晚于决策而拒读。不能将其称为历史时点市值资格。与此同时，原运行没有直接冻结这条链的市值叶文件，也没有保存逐值市值输入；本次不能补造这种运行证据。

## 1. 原 run 直接保存、此次可核实的绑定

- `entry_quality/trend_exit_controls_v1/runs/BASELINE/2022_2024/`实际窗口为2022-01-01至2024-12-31；`strong/`为2025-07-01至2026-06-30。两者各固定1709只股票、90个行业。
- 两份 `RUN_METADATA.json` 的38项 `source_freeze` 与当前文件全部吻合；`checkpoint.json`保存同一份冻结表。两条checkpoint实际SHA均与生成时 `checkpoint.provenance.json`一致。
- 生成时身份收据绑定真实交易类 `native_adapter.Runner`、`native_rank.Runner.planning`、`joint_v3.Runner.opening`及动态 `route` 的代码身份。详见 `RUN_BINDINGS.json`。
- **38项未直接包含** `current_pool_bridge.py`、`current_fixed_pool.py`、`inputs-v2/input-manifest.json`、`selection.json`；身份收据也没有保存加载后的cap reader/selection对象或市值数值。

两条 `pair/B.json.gz` 全文本均无 `company_cap_cny`、`SelectionFact`、`SelectionEvidence`、`snapshot_id`、`observed_at`、`selection.json`、`PoolLine`。两条checkpoint仅用 `pickletools.genops`解析opcode，未反序列化、未导入策略；分别65,317,869和26,772,614个opcode，上述字符串参数均0次。`launch_v3.py:63–67`明确排除runner的bundle/market/facts，并排除account的market/facts。故没有可直接恢复的原市值/选择证据dump。Book中`intents[].cap`为数量上限，不能冒充公司市值。

## 2. 当前传递引用：可复核，但不是补出的原逐值dump

实际冻结的入口 `run_control.py:14–25`调用两窗口输入加载器；strong的 `launch_v3.py:35`、长窗口的 `loader_2024.py:47`均调用 `J.M.context(...)`。当前 `wire.py:9`把M加载为 `mainline-I-quarter-2025Q3-20261031/adapter.py`；该文件`:59`读取 `BP.C.OLD/'inputs-v2/input-manifest.json'`。`common.py:7,15`给出OLD目录和bundle读取函数。

该manifest为：

`/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/inputs-v2/input-manifest.json`

- 当前SHA256：`eba972e5d1292e2872b2f1e47abe5b5b589d557e8b6e3616724d65ad43381d41`。
- `selection.path`指向 `a-share-selection-e0-20261024/inputs-v2/selection.json`。
- 引用SHA及实际当前SHA均为 **`3b0dac60526ff042b24e3a436638d6ef5a631a52f62f0c9daeb57e644633ca99`**。
- `current_pool_bridge.py:52–58,416–421`先核引用SHA，再构造`SelectionEvidence`和`PoolLine`。`package.json`不是此context入口；其bridge_manifest引用只作独立旁证，当前内容SHA相同。
- selection的`observed_at=2026-10-24T21:56:29+08:00`，`cap_observed_date=2026-10-24`，`roster_asof=2026-10-22`，`market_timestamp_unknown=true`；原文件自己注明current survivors/current cap/current industry，非PIT。

当前selection共1711行，1709个已知市值严格大于100亿元、2个未知；两条原run保存的1709 fixed IDs均恰好等于当前该文件的1709已知合格ID。这是原固定身份与当前引用文件的一致性，**不能单独认证原运行每一次读取的市值数值**。没有使用本轮新的canonical/current-cap join反推原run。

## 3. 代码时间语义与具体原文件值

- `current_fixed_pool.py:159`：`company_cap_cny=SelectionFact('company_cap_cny', line.company_cap_cny, evidence)`。
- 同文件`:99–101`：`read(self, clock, *, for_execution=False)`不检查clock，直接`return self.value`。注释明确这是保留真实observed_at、不回填时间的研究假设。
- `sector_stock_admission.py:197,203`：读取该值，以`cap > 10_000_000_000`作为资格硬门；未知保留未知。
- `engine.py:36–45`的I packet把固定line构造成Security，修改的是趋势/I_buy字段，不把市值替换为历史序列。

预先指定四例，直接从上述selection与其原始cap snapshot读取：

| 证券 | selection公司市值（元） | raw3541450 | raw请求202观测时间（+08） |
|---|---:|---:|---|
| 600000.SH | 317404640000 | 相同 | 2026-10-24 21:55:17 |
| 000620.SZ | 16617237000 | 相同 | 2026-10-24 21:55:54 |
| 300085.SZ | 19524478000 | 相同 | 2026-10-24 21:56:12 |
| 002583.SZ | 14694445000 | 相同 | 2026-10-24 21:56:06 |

四例raw均`market_timestamp=null`、`historical_point_in_time=false`；collector币种标签仍为`not_certified_by_collector`。selection的CNY/company-total解释与原始数值来源已保留，不能由此认定历史市值真实值或供应商市场时间。完整字段、来源文件SHA在 `CURRENT_REFERENCE_CHAIN.json`。

剩余缺口只有运行取证层：原run未直接freeze的加载器/manifest/市值叶文件及未保存的逐值读取，无法由现存账户dump逐条补证。此缺口不改变现存源码“固定2026快照历史研究”的明确语义，也不能被当前一致的引用SHA消除。本次零账户、零模型重算、零联网、零策略修改。

所有必要源码原文、路径及行号见 `SOURCE_EXCERPTS.txt`；完整证据分层收据见 `RUN_BINDINGS.json`、`CURRENT_REFERENCE_CHAIN.json`、`SAVED_DUMP_SCAN.json`和 `SOURCE_INVENTORY.json`。
