# 当前固定池：最小离线输入协议

2026-10-23编写，研究快照日仍固定2026-10-22。`code/current_pool_bridge.py`只准备信号及原准入输入，不联网、不取数、不运行账户。算法继续导入冻结`numeric.py`和`participation.py`，排序调用原`sector_stock_admission.rs_score`。原始全部当前股票与策略筛选事实分开保留；任何unknown不靠删除证券解决。

## 调用与就绪边界

1. `load_bundle(manifest, technical_sample=False)`检查清单/冻结代码与数据池收据，默认只建立声明，不把全部行情载入内存。生产必须存在哈希绑定的`data_pool_closeout`收据，`status=data_pool_closed`且scope_date匹配；这不是桥自己签发数据池结项。
2. `write_bundle(bundle, NEW_DIRECTORY)`逐证券生成signal、event、state/RS及量恢复memory parquet，逐项记录失败；输出目录已存在则拒绝覆盖。全证券结果存在，失败仍有series记录。`technical_sample=True`可做少数技术测试，但`signal_ready`永久为false、账户0次。
3. `load_prepared_states(bundle, prepared_directory)`只读共享的ready、target、RS、segment_id列，验证每个文件和源清单/桥代码哈希，10账户共用，不能每账户重算算法。
4. `bundle.at_decision(clock, market_buyable=...)`返回`DecisionInputs`：evidence、lines、historical、sectors。market_buyable必须对固定池每个ID给出原`admission.Fact`，由执行层提供真实或已冻结代理市场可用性。桥不猜南向交易日、手数、费用或支付日期。

signal_ready只表示本次声明信号全部准备成功，绝不认证经济账户、实盘可成交或公司行为账完整。存在不能处理的权益、断档和不合法资料，必须逐项给出blocked_reason。全池失败数可观测，不能只看成功证券。正式研究不能把技术样本接入账户。

## 清单结构（schema_version=1）

顶层字段：

- `scope_date: "2026-10-22"`；`research_basis: "current_pool_historical_development"`。
- `upstream_sha256`：键为`numeric, participation, data_utils, sector_stock_admission`，值为冻结源文件哈希。加载时同时检查导入文件的真实路径，避免导入其他同名模块。
- `data_pool_closeout: {path,sha256}`：生产所需结项收据；技术样本可以没有。
- `selection: {path,sha256}`；`series:[...]`；`sector_series:{sector_id:series_id}`。
- path可相对于清单目录，或用绝对路径；hash必须真实匹配。输出另保存桥源文件自身哈希。

selection JSON字段为`snapshot_id, observed_at`（带时区的真实快照时刻）、`source_id, lines`。每条line直接对应`current_fixed_pool.PoolLine`：`security_id,market(A/H),issuer_id,sector_id,company_cap_cny,current_stock,southbound_selected`。未知值用null，不发明发行人映射/市值。行业指数另在series中，股票line与stock series的集合必须完全一致。当前分类/资格作为研究设计，绝不伪造过去known_at。

每条series需要：

- `series_id,kind`（stock或sector_index）、`status`（ready或明确其他状态）。未ready可直接给`blocked_reason`，无需假文件。
- ready记录还需`raw:{path,sha256}, source_start, volume_unit:"shares"（行业指数可明确为source_index_units）, price_adjustment:"raw", currency`、`close_available_time`（当地完整日线可使用的时间，由协议明示）。
- raw支持parquet/csv及`{bars:[...]}` JSON。日期可为date或trade_date；OHLC、volume必须明确，股票量在上游转换为股；指数允许保留同一series的source_index_units，不作股票VWAP或跨指数绝对量比较。source_kind/path、amount、is_observed_bar、source_invalid、source_anomaly等保留；可选真实观察字段映射到原mask。原价用于后续执行，signal价格不得成交。
- `adjustment`：见下。源起点必须完全匹配，不能随意丢掉早段再称同一因果轨迹。原始日期不补齐，不制造上市前价格。
- 可选`segments:[{start,end,reason},...]`：仅用于明确核验的来源断档，覆盖每个原始行且不重叠。每段重新归一信号坐标并重新预热原算法和253观察RS，不将跨年缺口当一天变化。段间state为unknown，不能跨段沿用结构或RS。可选`unavailable_from`明示尾部来源从何日起不可用。分段不改变目标账户区间，影响区间仍在共同覆盖报告中保留。

默认无segments代表提供者已经审核为可连续使用的来源，不是桥根据“下载成功”自动认证。真实停牌与来源缺口不能仅凭日期差混同。证券没有新观察时，正常状态可保留，但RS observation_at仍为真实末观察日；原准入会拒绝陈旧排名。共同readiness要求股票与其固定行业映射都已预热，因此T0/T1/S0的可研究池一致。

## 信号复权与权益协议

支持两种股票信号坐标和行业指数：

- `unadjusted_index`只允许sector_index，不能给个股绕过权益。
- `theoretical_ex_price`采用原A股约定：事件前原收盘价与每股现金/新股比例计算理论除权价；因子只在事件日改变。
- `total_return`采用原HK准备的事件日收盘现金坐标：`factor *= split_ratio + cash/raw_close`。原约定不支持同日非零现金且拆股，仍显式拒绝，不能悄悄换公式。

股票adjustment还需`actions:{path,sha256}`。归一权益JSON：

```json
{
  "series_id": "证券稳定ID",
  "currency": "HKD",
  "status": "reviewed_terms",
  "coverage_evidence": "实际源及已审查区间；也可用对象列源路径和hash",
  "events": [
    {"effective_date":"2020-05-24","cash_per_old_share":"1.20","split_ratio":"1","source_id":"逐事件证据"}
  ],
  "unresolved": []
}
```

status可为`reviewed_terms`或首账户前明确冻结的`declared_research_proxy`；`needs_review`等未审查状态不能通过。空events必须有覆盖证据，空id211响应本身不能证明无事件。实际未覆盖事件/跨币/实物分派/配股留在unresolved，不能猜现金等价。源起点前不需要恢复账户持仓，但原记录应保留在`ignored_before_origin`，不能说它们已被解析。归一条款不等于实际到账日或新增股份可卖日；ledger_ready另管。

价格和量采用Decimal事件递推（40位、HALF_EVEN），再一次转换binary64；无事件日不重新累乘。成交量除以截至当日累积拆送比例，保持源起点股份单位。行业不作股票权益调整。非观察日发生的理论除权事件可保留明确synthetic_event_bar帮助因子过渡，但它不进入趋势价格观察或成交。

**缺量与缺价必须区分**：原`eligible_prices`保留合法价格且缺量的观察；它仍可触发结构破位/收复。原numeric事件自身只使用正量联合观察。桥不能用统一正量筛选删掉这些价格行。非法OHLC几何、明确source_invalid/anomaly由原mask排除并在覆盖差异中保留。

## 已有验收与未完成

`bridge-validation/attempt-06.txt`：16项合成边界通过，覆盖源hash、原点/单位、空权益、量价观察钟、因果前缀、冻结公式、陈旧排名、明确缺口重预热、unknown保留、生产门槛、流式输出和篡改拒绝。

首跑12项中的1项失败是前253观察RS全None使pandas推断object，与较长前缀float64不一致；已修复为明确float64，原attempt-01保留。后续HK缺量、来源断档和CSV布尔观察标记各增加1项有意义测试，未改趋势方程。

真实技术样本`bridge-validation/real-a-smoke-01/`及最终代码重跑的`bridge-validation/real-a-prepared-03/`使用已融合的6股、18,920条价格观察及61个生产窗内已解析权益；0桥接阻塞、12次源准备前缀完全一致。与旧THS浮点理论除权辅助函数相比，价位最大相对差约1.04e-15；6股全部target/entered/exited/independent_entry/created逐观察相同。保留新旧数值差异，不泛化为全市场数学等价。技术样本没有假造市值/公司/行业，也没有账户或数据池结项。

仍待：全池融合及结项收据、正式选择快照、全部同源行业来源连续性判定、HK归一权益审查、首账户执行假设冻结。桥实现和少数技术通过不代表这些输入已经完成。
