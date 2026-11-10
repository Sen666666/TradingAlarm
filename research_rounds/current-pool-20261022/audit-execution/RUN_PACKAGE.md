# 首轮10账户历史执行包

2026-10-23。`history_runner.py` 已实现共享冻结输入的真实日循环、逐单整股成交、会计及 B0 年度调仓。仅合成数据技术验证；真实经济账户仍为 **0**。数据池和经济协议没有因本交付自动结项或冻结。完整 A/H 同源行业历史仍有缺口，由 root 作有限可行性裁决，不靠继续扩大执行框架绕过。

研究身份固定为 `current_pool_historical_development`：按 2026-10-22 今日存续股票、公司总市值、港股通及行业快照选池，再读取历史量价。它有当前存续及分类选择偏差，不能称无偏历史全市场或未见检验。发行人规范键用经验证的 `company_cap_source_symbol` 映射到 `PoolLine.issuer_id`，不能把 A/H 两证券当两家公司。

## 可执行入口及固定行为

```sh
python3 research_rounds/current-pool-20261022/code/run_first10.py describe
python3 research_rounds/current-pool-20261022/code/run_first10.py validate \
  --data-closeout /absolute/path/data-closeout.json \
  --economic-protocol-frozen /absolute/path/economic-protocol-frozen.json
python3 research_rounds/current-pool-20261022/code/run_first10.py run \
  --package /absolute/path/run-package.json \
  --output /absolute/path/NEW-result-directory
```

`describe/validate` 不运行账户。`run` 必须同时通过下述哈希、数据结项与经济冻结限制；现有目录拒绝覆盖。它不下载数据、不重新计算信号、不修改算法，也不创建外部委托。

固定 T0/T1/S0 各 base、cost2、delay1，加 B0_base 共10账户，各 CNY100万元。每个共同收盘截点只调用一次共享 `Bundle.at_decision`，三个策略继续调用原准入函数；真实预约失败后有限候选补位。状态只在收盘可知，下一实际可执行事件成交；退出锁存不因随后恢复而撤回。cost2 只改变明示费用/滑点组件，delay1 跳过首次实际可成交事件。账户起点可落在首共同收盘前，结束时点必须恰好是最后共同收盘截点；日历还须延伸到该截点之后。结尾持仓估值，不强制清仓。

每事件先交收，再处理当日公司行动及已到期支付；开盘按卖出、交收、B0追加原年度目标预约、买入、交收的顺序执行。公司行动生效日按本地午夜入账，未知支付日只记应收。交易日延迟按后续市场日期，不能把另一市场当日较晚开盘算为 T+1。

B0 起点及每年首共同截点冻结同池每发行人90%净值等额目标，按真实整手形成买卖差额；不使用策略的6槽/行业限制。先卖后买，受实际现金及90%总投入剩余额限制；不足一手留现金，年内不按市值每日再平衡、不把低开节余重算成更多股数。A/H 同公司按稳定证券 ID 选择一条，尚未清空旧线路时不重复买另一条。停牌/未交收只能等待原年度目标。

## 输入依赖与收据

`run-package.json` 为 `schema_version:1, mode:"frozen_first10_historical"`，含带时区 `start/end`，以及以下每项 `{path,sha256}`：

`scope, data_closeout, economic_protocol_frozen, economic_protocol, bridge_manifest, prepared_manifest, market_rules, fx_quotes`。

路径相对 package 所在目录或绝对路径，SHA256 必须真实匹配。`prepared_manifest` 必须是桥真正读取的 `manifest.json`，不能认证同目录另一个文件后执行未认证文件。

按以下无循环顺序制作证据，不能伪造布尔开关代替：

1. 数据池收据先绑定原始量价、选择、行业、权益等审查产物，`kind=data_closeout, status=data_pool_closed, round_id=current-pool-20261022, scope_date=2026-10-22`，另含 `scope_sha256,recorded_at,artifacts`。`artifacts` 是相对收据路径到实际 SHA256 的映射，时间带时区。
2. `bridge_manifest.data_pool_closeout` 指向该同一收据。桥及共享 prepared state 按 [INPUT_MANIFEST.md](INPUT_MANIFEST.md) 生成，保留所有 unknown/阻塞条目、源哈希、冻结算法路径及哈希。技术样本永久不能用于经济账户。
3. 之后制作经济协议与市场规则；经济冻结收据 `kind=economic_protocol_frozen,status=frozen`，绑定相同 round/scope，`artifacts` 必须明确绑定**实际使用的 protocol、market_rules、bridge_manifest、prepared_manifest、FX文件**。无需让先出的数据收据反向引用后出的桥或 state，避免循环哈希。

经济协议本体必须含 `status=frozen, algorithm_changes:0, account_start, account_end`；日期须与 package 一致。`code_sha256` 必须绑定 `history_runner.py, sector_account.py, current_fixed_pool.py, run_first10.py, b0_rebalance.py, market_rules.py`。桥及原 numeric/participation/data_utils/admission 已由桥清单和 prepared 清单绑定并核对真实导入路径。

## 有限市场规则输入

`market_rules` 提供：

- `decision_cutoffs`：带时区的共同日线可用截点；`calendars:{A:[...],H:[...]}`：真实或明确冻结代理的开盘时间。每市场每本地日期只能一个开盘，不允许重复或把午后开盘作为新交易日。
- `venue_versions:{sid:[...]}`：历史证券所属 `SSE_MAIN/SSE_STAR/SZSE_MAIN/SZSE_CHINEXT/BSE/HKEX_MAIN/HKEX_GEM`。NEEQ 不允许作为 A 股成交；今日 `.BJ` 后缀不能回填历史挂牌日。可用 `venue_not_before` 保存源证据支持的交易所最早日期。
- `quantity_versions:{sid:[...]}`：每个版本的 `rule` 完整给出 `rule_id,buy_minimum,buy_step,sell_step,allow_full_exit_odd,fill_step`。整手提交与部分成交步长分开，不默认全池100股。
- `availability_versions:{sid:[...]}`：`buy_allowed/sell_allowed` 为布尔或 null。未知不开仓/不撮合，当前选池资格不能替代历史交易可用性。
- `fee_versions:{历史venue:[...]}`：版本内 `schedule:{schedule_id,components:[...]}`。严格按当日历史交易所选表，没有 A/H 宽泛 fallback。可选 `security_metadata:{sid:{par_value:...}}` 用于明确的面值计费，面值缺失不能改乘成交价。

版本统一 `from` 含、`to` 不含（可 null）、`source_id,basis`。真实规则使用 `basis=official_rule,verification_status=verified`；研究代理使用 `basis=explicit_research_proxy,proxy_id`，且该 ID 必须列入冻结协议 `approved_proxy_ids`。重叠区间报错，缺项保持未知。

费用组件字段：`name,rate,minimum_local,side,basis(order/fill),stress_rate,stress_minimum,maximum_local,rounding_unit,rounding_mode(ceil/nearest),stress_maximum,amount_basis(notional/shares/par_value)`。比例、金额可用十进制字符串。支持 HK 印花整元向上、分币取整、旧结算费上下限和沪早期面值过户费；固定每成交收费可显式用 `rate=0,minimum_local=固定金额,basis=fill`。同一委托跨费率变更时保留已累计旧费额，不按新率重算旧成交。

[audit-fees/fees.json](../audit-fees/fees.json) 是来源事实表，**不是可直接当作无缺口完整 FeeSchedule 的运行输入**。必须先按日期/venue/route 汇总上述组件，明确佣金及持有费用等未解项。南向组合费当前 unknown，不能因表为空视为0。统一研究费用假设由 root 冻结，本实现不自动选择。

FX文件为 `{"quotes":[{"currency":"HKD","cny_per_local":"...","known_at":"带时区时刻","source_id":"..."}]}`。只读取不晚于决策/成交时刻且未超过 `fx_max_age_days` 的资料；CNY 恒为1，不能未来回填。

## 必须明确冻结的执行代理

经济协议还须提供 `approved_proxy_ids,fx_max_age_days,participation_rate`，以及按 A/H 明示的 `daily_execution,sellable_lag_sessions,settlement_lag_sessions,dividend_net_factor,bonus_sellable_lag_sessions`。

`daily_execution[market]` 含 `price_limit_policy`（`external_columns/no_price_limits/conservative_hl_proxy`）、`reject_flat_day,slippage_bps,stress_slippage`。外部涨跌停字段缺失不能成交；保守高低价代理通过 `reject_flat_day` 排除全天一字行情，并不恢复真实委托队列。每日成交价来自实际原始 open 加已冻结滑点；容量是过去20个正量观察的参与上限再受当日成交量事后上限约束。当天 H/L/volume 的成交事后检查必须标作日线研究代理，不能混入开盘估值、候选排名或信号。

成交按当时已知参考 FX 锁定人民币应收应付，现金按指定交易日延后可用，标记 `known_trade_time_reference_locked_until_settlement`；不声称复原南向最终结算汇率。现金分红以生效日前持股及原币每旧股条款，乘显式 `dividend_net_factor` 计应收；真实支付字段缺失则一直不再投入，不猜付款日。整股送转的新增股份可卖日用真实字段或冻结交易日代理；分数权益、供股、实物分派等未适配会明确失败保存部分证据。

除权日停牌或本市场尚未开盘时，旧原价不能直接乘新股数。若冻结 `stale_action_mark_policy:"theoretical_ex_reference"`，仅把过时估值参考按每次 `(旧价−每旧股现金)/拆送比例` 转为当前股份单位，来源记 `derived_ex_reference` 并保留真实原价观察时刻。它可供资产估值/预算参考，**永远不用于 FillWindow 成交价**。现金应收另计，税差会减少净值。未冻结此政策则遇到该情形明确阻塞。

`allow_explicit_unknown_series:true` 只能许可共同覆盖缺口被明确保留，不能使未知状态变真、绕过来源断档或补造行业指数。`unavailable_from` 或明确 segment gap 期间，既有买卖单不成交；若持仓无法估值，整次运行以 `failed_partial_run` 结束并保留证据，不能把缺口跳过后声称完整绩效。

## 输出与验证

生产逐日账和决策分别流式输出 `daily.jsonl.gz/decisions.jsonl.gz`，另有各账户成交/会计日志/应收/结算、`B0_annual_targets.json,summary.json,provenance.json`。逐日账含原观察时间和估值来源。异常保留部分账、错误、输入哈希与已启动账户数；从不把未完成运行报告为10个成功结果。收益分布、周期归因与四阶段主观复盘由后续评价读取这些证据，不在此新增评价门槛或策略。

`test-runner-combined-attempt-02.txt`：82项合成测试通过（资格10、会计20、入口13、B0 14、循环/时钟/费用25）。覆盖共享输入与收盘后成交、费用/延迟拆解、6槽与B0全池差异、退出锁存、现金核对、跨年整股差额、开盘前因果估值、停牌除权、来源断档、历史venue收费、精确prepared文件、日历/T+1、流式账和结束状态一致性。早期日志及失败证据保留。独立审查发现的具体缺陷已修复，不把合成测试数量叫作历史账户次数。
