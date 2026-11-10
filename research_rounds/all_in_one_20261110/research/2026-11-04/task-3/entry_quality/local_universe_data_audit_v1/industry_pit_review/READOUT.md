# 行业历史映射：本地有界核查

**SW确有回溯分类变更历史，可明确标作retrospective分组代理；当前证据不能认证历史首次发布PIT，也不能把SW成分接到THS行业指数。** 本次读实际processed/raw数据、meta及生成代码，无联网、更新、模型或账户。

## 实际数据与历史序列

`my-quant/data/processed/security_memberships/security_memberships.parquet`实为12,780行、5,862股票、553分类代码，全部`akshare/sw/stock_industry_clf_hist_sw`。start日期1990-01-01至2026-05-15；end全12,780缺失，无`is_current`或`level`字段。分类名全为代码自身，所查本地taxonomy没有SW名称/层级字典。所有代码不以00结尾，与叶码形状一致，但本审不凭数字形状硬认证三级。

3,895股票有多条记录；按同symbol/source分类码及start排序，6,918次相邻代码变化、0次相邻重复。没有同symbol+start多code冲突，也没有同symbol+start+code重复。重复同symbol+code在不同start有213条，不能直接按stock+code去重擦掉回归旧代码的事件。

原始真实序列示例：

|股票|原字段start与code序列|
|---|---|
|000620.SZ|1996-10-29:220101 → 2008-06-02:240106 → 2011-10-10:510101 → 2012-01-08:430101|
|600000.SH|1999-11-10:440101 → 2014-02-21:480101 → 2021-07-30:480301|
|002583.SZ|2011-05-18:320102 → 2014-02-21:730201 → 2021-07-30:730204|
|300085.SZ|2010-05-12:470303 → 2011-10-10:470302 → 2014-02-21:710201 → 2021-07-30:710401|

同一`update_time/known_from`日期有多条历史start的symbol组为1,040；这与“同生效日多分类冲突”不同，不能据此全否历史。变化也可能包含分类版本重编码，不全是公司业务迁移。

可按该接口的单列分类码序列以**下一start作为上一段exclusive end**，得到6,918个派生封闭段和5,862个尾段。它是可复核的回溯代理，非source原end。内部0gap是该构造定义，不证明真实历史无未分类间隔；尾段也不能冒source `is_current=True`。本次未生成完整新映射数据或接入策略。

## 时间、填补与PIT边界

原pull meta记录抓取2026-05-16T07:36:53Z，processed生成2026-05-16T08:09:38Z。请求范围2020-01-01至2026-05-15并未裁掉更早的SW事件：实际raw包含1990起历史。

raw已含source返回的start与update字段；与processed全部12,780行按symbol/start/code一一核同，没有本次cleaner填start。local AKShare实现将“计入日期”映为start_date、“更新日期”映为update_time，见[stock_industry_sw.py:17](/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/.venv/lib/python3.13/site-packages/akshare/stock/stock_industry_sw.py:17)。它指向一个历史分类XLS下载；该当前安装源码不是当次May抓取包版本的认证，pull也未留原HTTP/XLS发布vintage。

[builder.py:757](/Users/bytedance/repos/my-quant/src/my_quant/data/builders/a_share_boards/builder.py:757)只重命名source start/code，snapshot用update_time，却硬写`pit_status='effective_dated'`、`lookahead_risk=False`；[693行](/Users/bytedance/repos/my-quant/src/my_quant/data/builders/a_share_boards/builder.py:693)把config.end传作observed_at，故表内observed_at全为2026-05-15，**不是实际fetch时间**。[cleaning.py:516](/Users/bytedance/repos/my-quant/src/my_quant/data/cleaning.py:516)再默认known_from=snapshot_date。全部known_from等raw update_time；12,331条晚于start，4条早于start，其余同日。这些日期可以描述提供方更新，但不能自动等同历史第一次可得/未修订时间。

所给表没有effective_from列，也没有统一2005回填。只有000759.SZ/450102一条raw计入日期恰为2005-01-01，known_from=2015-10-27；它是raw返回值，不是本地将全史设为2005。其他未指定的effective_from2005文件不在本审范围；不能把研究MODEL_FLOOR2005当行业生效日期。

## 对本地价格与原TradingAlarm的覆盖

bars/BAR_SYMBOL_COVERAGE.csv的5,517股票exact-symbol匹SW为5,204，恰覆盖2,891 SZ及2,313 SH；313个920*.BJ没有同symbol匹配。SW另含832317/833874/833994/874090四个旧BJ代码，本次未做ticker/issuer alias桥，不能从exact未匹配推断公司绝无历史。

5,204匹配者中127的bar first早于首次SW start，形成127段**exact-symbol pre-first未知**。例如001914 bars始于2000而本symbol SW始于2019，302132 bars始于2010而SW始于2025，可能涉及代码/资产沿革；未核实体桥，不能反填当前分类。内部真实gap和实际退行业日期仍未知。价格first/last区间只作覆盖包络，不代表该日交易、上市资格或官方日历认证；May15是本份myquant表边界，不是本机所有行情截止。

所查industry_taxonomy实际465行=90 THS行业+375 THS概念，与SW553 code相交0。board_daily_flow为独立THS指数接口结果，不是用这份SW成分回算。SW分组可用与THS指数成分兼容是两件事。

原TradingAlarm current-stock-master实际5,576股票；No60原selection为1,711行，其中cap-qualified1,709、90行业。它明确roster_asof2026-10-22、cap_observed2026-10-24、observed_at2026-10-24T21:56:29+08:00且market_timestamp_unknown。其行业由当前Block tree/master重连，见[repair_classification.py:31](/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/code/repair_classification.py:31)，没有历史生效区间。1,709中exact匹SW1,678，缺31。90个URFI尾码与myquant90 THS行业code全部匹配，只说明代码字典对应，不证明SW成员是该THS指数历史成份/权重。

另亲读TradingAlarm已解析cache 8,340条A/HK成员；effective_from/to全None、观察时间2026-10-18T08:56:04.157174Z，已有review也明确not_historical。其file version不等每股加入/退出时间。这只限定所查缓存，不宣称本机绝无其他历史映射。

可收敛的代理方案是：在明确覆盖和未知的原stock-code价格范围内，用SW原start序列作**回溯分类代码分层**；不因end缺就全盘停止，不静默填alias/前史，不冒充历史PIT。若研究需要THS行业指数许可或RS，则历史同taxonomy成员/版本证据仍缺，该连接分支不能据SW替代。完整字段、样本、日期及源SHA见EVIDENCE.json。
