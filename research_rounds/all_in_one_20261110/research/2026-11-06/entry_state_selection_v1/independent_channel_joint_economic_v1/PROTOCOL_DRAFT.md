# A+B 原样保留与独立价格通道：唯一逐股研究合同草案

版本：JOINT_AB_PRICE_V1。状态：DRAFT，等待父任务确认与独立审查；本文件不授权新经济执行。2026-11-08。

## 0. 本轮只固定一个比较

- 基线：`A_UNION_B`，采用已经现金权益修复并封存的原逐股消费者，不采用 relative 优先，不采用 `AB_FAST_SMALL` 作基线。
- 联合臂：`A_UNION_B_PLUS_PRICE`。保留 A/B 的原事件、原 I 许可、PVR 排序、初仓、I 退出、CP-add 与权益合同；另增独立 PRICE 通道，参与同一行业每日两个初始预约名额。A/B 不借 PRICE 标签改变其持有或退出。
- 固定两窗：2022-01-01 至 2022-12-31；2024-09-01 至 2024-12-31。两窗两臂各自从执行 FLAT 开始，不共享库存、claim、订单目标或消费集合。既有持有、既有 target 的续量、一次合法 ADD 和已登记权益管理至 2026-06-30，不强平。
- 市场根用完整 warm history 初始化。窗口内一张真正的新 frontier 收据可以成为本窗第一次 PRICE 小仓邀请，即使其 root 出生早于窗口起点；不得把窗口起点当新出生或重置市场 F/Q/S。窗口前收据不得重放。本窗关门后不再从无 parent 的空仓新建初仓；窗内末个信号的立即 next-common OPEN 仍可执行。已有固定 parent 可依本合同在窗后补余量，不能借此新开根或新领初仓预算。
- 2026H1 不是第三个主经济窗。2022/2024 持有延伸若碰到 2026-05-18 切源，必须 UNKNOWN 锁存；不得卖出、释放库存责任或推定资金可用。
- 本轮是逐股条件生命周期，不是共享现金账户，不报告账户 CAGR、总资金回报、账户最大回撤或可实盘性。静态 1709 股票池、行业及当前历史资料 NON-PIT；22 个无本地观察名称保留不可用标签，不当负例。
- 不设第二套量门、M3 总门、排序/退出参数或事后候选菜单；不根据本次未来净收益择式。既有案例、108 个旧赢家和旧收益标签只用于事后解释，不输入选择器。

## 1. 冻结参考及精确回归目标

2022 参考：`m3_stock_birth_during_sector_v1/relative_priority_equity_run_2022_v1/engine.py`、`run.py`、`dynamic/`、`report/CORE_AND_FULL_ROUNDS.csv`，只取 `A_UNION_B`。该消费者已选 2732 回合，2627 条条件闭合、103 UNKNOWN、2 个旧名 NOFILL；这只是工程回归规模，不是新联合臂目标。

2024 参考：`m3_stock_birth_during_sector_v1/cash_equity_baseline_2024_v1/engine.py`、`run.py`、`PROTOCOL.md`、`economic/`、`report/CORE_AND_FULL_ROUNDS.csv`。参考 1354 回合、1320 条条件闭合、27 UNKNOWN、7 个旧名 NOFILL。旧表的 `NOFILL` 文本保留用于逐列回归，语义另映射为未提交预检拒绝，不能反推有真实订单。

复用冻结 primitive：dated market identity、quantity rule、fee、单边滑点 0.0005、`size`、容量、NET80 claim 时钟。参考 NAV=1,200,000 元、初仓预算 INIT=24,000 元、ADD 单次预算至多24,000元、SLOT=48,000 元、整轮计划风险 RISK=3,000 元。48,000 是 ADD 时原价开盘库存市值的槽上限，不是累计买入额上限或动态账户 NAV。

只在关闭 PRICE 的工程模式要求：两窗全部原列 ROUNDS/ACTIONS/DECISIONS/RANKING_AUDIT/END_STATES，以及 REGISTER/CLAIM/BRIDGE/mark 账本逐行对齐；保留原 financial coverage 标签。相同 A/B 信号进入相同历史状态时，联合臂 A/B 角色应完全沿原路径；新通道改变占位/行业队列后的差异则须明确归因，不能要求新状态复现旧 selected。

旧策略文件和旧输出一字不改。新实现不直接执行任何旧 runner 顶层主体，导入/抽取定义必须无收益执行副作用；新输出只能写本目录的阶段子目录并拒绝覆盖。

## 2. PRICE 市场根不改公式

唯一公式来源为 `independent_channel_probe_preflight_v1/core.py::simulate` 及其 `PROTOCOL.md`，并以全1709已审来源封存为准。它是市场状态，不读执行持仓或旧赢家标签。

1. 当日 C 严格大于此前连续20个有效价格 bar 的 High 最大值 U，价格独立出生。a 是此前20 Close 中最近的最低日；失效后再入时 a 不早于前根失效日。a/U/Ca/B/R 出生时冻结。
2. B 是严格 a 之前21个有效金额的中位数；缺 B 或必要金额仅使量信用 UNKNOWN，不能阻止首探。R=log(U/Ca)。市场 frontier_F 从0开始；每次 delta=max(0,log(C/Ca)-frontier_F)，frontier_F 取历史最高；`volume_credit_Q += min(1,sqrt(amount/B))*delta`。缺新前沿所需金额后 Q 不回填；既已确认事实不倒销。CONFIRMED 只负责后续 ADD 市场许可。
3. 出生保护 S=minLow[a..birth]，出生当日不接 E0 floor。以后每收盘先 C<=旧S 判价格失效；仅存活时以 ready 且 target=1、有限且 0<floor<C 的原 E0 floor 抬 `max(oldS,floor)`。不改成 I 退出，不设止盈、冷却、额外价格阈值或次数闸门。
4. 出生一票，活跃根以后只有严格新收盘 frontier 才发新票。同价、横盘放量、量态刚转 CONFIRMED 但无新前沿，不造票。失效当天不得再出生。
5. `root_id=(sid,source_identity,root_birth_day)`；`receipt_id=(root_id,frontier_close_day)`，保留封存旧文本ID作 alias。source_identity 包含 source_kind/source_path/segment；新 canonical 身份只补命名空间，不改变公式。重复同内容幂等，身份相同内容冲突锁 UNKNOWN。
6. 市场信用 Q/F 与执行 `target_Q`/`filled_F` 完全不同字段，禁止共用变量或相互填补。市场 root 因价格/来源 UNKNOWN 隔离，不证明已有执行库存消失。

## 3. 行业资格：原快入口四事实，不是 M3

PRICE 每一次新初仓、未完成 probe 续量和 ADD 邀请，只使用该信号收盘四事实：`sector_known`、`sector_observed_today`、`sector_rs_ready_fresh`、`sector_up` 全部严格 true。字段来自原 fast native S0 的逐项理由/事实，使用同日行业观察与原行业 E0；不把整体 `event_Q` 或 `continuing_Q` AND 回新价格根。

四事实仅是交易资格，绝不否认或延迟市场价格根的出生。任何 UNKNOWN 优先标 INDUSTRY_UNKNOWN；已知 false 标 INDUSTRY_FALSE；均不新增订单。行业 off/UNKNOWN 不直接卖已有 PRICE，也不把已知价格失败吞掉。以后只有新收据重新检查，不保存旧票等行业转好。

不加入 stock I/G、stock common_ready、cap>100亿元、stock RS、i_buy、旧 CP、M3 或量 CONFIRMED 首探门。PVR 仍只承担原两个资源名额的排序，见第4节。

### 已冻结全窗过滤事实，不是入选或成交

使用封存 `overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet`，在未看新经济前统计：

| 窗口 | 出生票 | 四事实全真 | 行业不通过 | 全部frontier票 | 四事实全真 | 行业不通过 |
|---|---:|---:|---:|---:|---:|---:|
| 2022 | 4057 | 3894 | 163 | 24733 | 24014 | 719 |
| 2024_924 | 1790 | 1739 | 51 | 12723 | 12538 | 185 |
| 2026H1，仅事实诊断 | 2580 | 2412 | 168 | 17745 | 17084 | 661 |

以上各窗四字段无 UNKNOWN，不通过项均为 sector_up=false。四事实全真出生票中 PVR已知且有限为3824/1731/2380；这些不是额外市场确认。通过行业且原“从未开始parent”close size可行为3662/1688/2074；其不是联合路径目标数量，也不证明空仓、两个名额或可成交。

预先点名病例：银之杰300085.SZ在2024-09-19出生当天四项全true；江丰电子300666.SZ在2022-06-06及2024-09-27出生当天均全true。海能达002583.SZ在2024-09-20价格出生时 sector_up=false，不能首次预约；9月23日新frontier才全部true，确实延迟一个共同交易收盘，最早条件OPEN由9月23日推迟到9月24日。海能达9月23日三层原证据分别为：(1)raw A_SECTOR_BIRTH；(2)原I_qualified=true、PVR_known=true、PVR=68.422911；(3)原AB close_check=PASS，close_q=2500、close_plan_risk=2976.234342元。旧基线该日FLAT，但队列第6、PASS_NOT_TOP2，并未入选。因此在联合臂自身也FLAT时应以AB角色竞争，不等于已获槽或成交；不能把PRICE的size PASS冒充AB size。不能为了海能达或任何具体启动例事后豁免行业门。

原五病例中的江丰启动实际上是2025-12-15，不能用上面2022/24两日代替。已按 `fast_entry_equity_2022_v1/prepare_inputs.py` 原定义只读构造单股native上下文：2025-12-15及12月17日的四行业事实均true，原行业E0事实于当日15:05已知，同日H1=88.333333于15:10可读；原event_Q=false只因buy_allowed=false及stock_up=false。12月23日四行业事实仍true且原event_Q=true。故本合同的行业门不额外延迟该江丰价格根或17日新票，但不代表获得资源/成交/收益；此2025病例只验机制，不扩展为主经济出生窗。

## 4. 同股所有权及跨股每日两个初始预约

`owner_lane` 一经正条件首填即固定 AB 或 PRICE，直到本轮真实/代理卖清且全部订单责任结清。已有 AB 的 pending/held/exitpending/UNKNOWN 不发 PRICE 初仓；已有 PRICE 的初始parent（包括已登记但零fill）、partial/held/exitpending/UNKNOWN 不再开 AB。市场票仍照常记录并注明被谁阻挡，不会改变原持有身份。

同股同收盘的优先定义：在自身 FLAT 时，只有当日原 A/B 事件、原 I许可、原PVR已知有限和原AB收盘size检查全部合法，才给 AB 角色优先。raw AB event本身不挡PRICE；AB许可或收盘size不合法时，独立PRICE可按自身合同进入队列。已经选定合法AB后，同收盘PRICE票记 `SUPPRESSED_BY_AB_SAME_CLOSE`，不缓存；AB next-OPEN拒绝不能回退同张PRICE票，只能等以后真正新frontier。AB优先只指同股角色，不是跨股票AB排在PRICE前；跨股票仍按下段唯一排序。开盘失败无队列替补。

每个行业、每个信号 CLOSE 最多两个初始预约（BUY_PENDING），不是该行业最多持有两只，也不是总账户槽。统一队列包含可申请的新AB、可申请的新PRICE、既有PRICE probe parent依新票请求的固定余量。probe补余量仍属初仓责任，消耗本日一个初始预约槽；同股不重复排两次。原AB CP-add与PRICE ADD均不占这两个“初始”名额。

唯一排序已在收益前固定：所有PVR已知且有限的AB/PRICE混排，按 `PVR_score` 降序、sid升序；PRICE的PVR未知不否决，排在所有已知候选之后，再按sid升序。AB保持原PVR_known及有限值门，不借此获得未知排名许可。未知不估0，没有PVR>50之类阈值，也不要求PVR新高，PVR不是独立根或量确认，但整个联合分配算法仍依赖PVR。记录市场收据、行业资格、资源排序三层，不把“排不上”改称无价格信号。必须分列未知PRICE申请、close可行、获槽、被排位挡，以及与已知组的财务覆盖/风险暴露；本选择不是对PVR优劣的实验。

在原 CLOSE 已知条件下顺序扫描；state不合格、close手数/风险失败不占槽；前两个可行者预约。next-OPEN失败也不补候选、不用未来OHLC/成交结果重排。存在待补固定Q时，close检查必须审余量能否在原预算/风险下整体提交，不能用从未开始parent的q上界替代。

## 5. 唯一历史执行代理和真实执行界线

唯一主研究代理为 `CONDITIONAL_NEXT_COMMON_OPEN_FULL_FILL_V1`，沿旧小仓场景的下一共同OPEN价全额条件填充，不增加可成交概率、量价阈值或一字排除规则。它不是实盘订单模型，也没有真实ACK证据。

信号 CLOSE=T；有效期仅立即下一共同OPEN=O（交易日历，不是该股下次有价日）。缺O价格、来源、factor或dated规则所需事实为UNKNOWN，不跳去更晚开盘。OPEN决策只读该时点可用的 raw_open、来源/因子/已审经济事件及T以前信息；不得用O当日高低收、成交额、量或日终flags验证O可买。预计算market daily表的O日phase/failed/root_id/valid/S_new含当日收盘信息，OPEN一概禁止读取，只能读前一CLOSE已封存root/许可/保护；当日源元数据在OPEN已知的切换检查与当日收盘root计算严格分开，不能用收盘失效倒消早盘买单。

实际历史 `actual_order_id/actual_ack/actual_fill` 始终 UNKNOWN/NOT_PROVIDED。研究日志单独用 `proxy_target_registered`、`proxy_fill`、`proxy_complete_known_at`，不得命名为真实 submitted/ACK/成交。`execution_permission` 的真实凭证接口不能把代理日志伪装为 broker context；同一责任状态机须有明确 evidence_domain=PROXY 或 SYNTHETIC_TEST，现实适配器另需真实认证证据。

主代理的固定事件次序：
1. T收盘仅预约并做可行检查，`close_q`是预检，不是target_Q。
2. O预检通过价格/源/坐标/责任/dated规则；若 raw_open<=当次合法S_raw，则 `PRECHECK_OPEN_AT_OR_BELOW_S_NO_SUBMIT`；若合规手数q=0，则 `PRECHECK_Q0_NO_SUBMIT`。尚无parent时两者都不登记target，不记录零fill ACK。该票失效，名额不回填。
3. 通过后先计算q，再原子登记不可增大的target_Q=q及其根、角色、预算、信号收据、decision_open、保护与证据版本；随后才写任何proxy fill。严格禁止以最后成交量F倒推Q。
4. 主代理一次填满登记Q，买价raw_open*(1+0.0005)，dated买费；同一proxy OPEN事件内完成账本和proxy complete。假定的即时完成时间明确为 `(O, OPEN_PROXY_COMPLETION)`，晚于登记/填充；它不是虚构的真实ACK。
5. 后续ADD依“收据known_at严格晚于proxy complete-known_at”应用同一条件研究时钟。不得把这项代理结果用来证明真实probe已成交完成。

全日一字只能事后标 `DAILY_ONE_PRICE=true`，不能叫真实成交或NOFILL，也不能在O决策使用其未来H/L。结果必须单列：含一字入/出/加动作的回合数、条件PnL及占总条件净额/正右尾的贡献，以及去掉这些回合的描述性汇总。后一汇总不重跑队列，不称“可成交版策略”。所有回合 `historical_tradability=UNKNOWN`。

## 6. 固定Q、zero-fill/partial/cancel/latefill责任合同

主历史代理不伪造0-fill/partial序列；下面是执行适配器必须通过的合成行为合同，不是用旧回报证明新路径可执行。

- 一个根最多一个probe parent。第一次实际/代理提交之前创建target_Q；未提交预检拒绝不创建。已存在parent后Q永不因新票、新S、价格变化、资金空闲或取消增大或重新领24k。
- 已提交的0-fill与partial必须有 order/fill/terminal-ACK ledger。`filled_F`是该parent所有去重正fill累计；`live_leaves`包含所有仍活跃/撤单待确认数量；`filled_F+live_leaves>target_Q`立即锁UNKNOWN，不必等实际超填。任何迟到/冲突/超填、不明订单、pending exit均阻止另一单。
- 仅当所有相关订单 terminal ACK 与fill账对齐，已知 `live_leaves=0`、无未决/退出责任，才记unlock_known_at。请求撤单不等于已取消；不可在撤单请求时解锁。晚于旧unlock才到的latefill先更新F、撤销旧解锁并重做对账；冲突或F>Q锁UNKNOWN。
- 续量必须是同root同parent的Q-F，且有 `receipt.known_at > unlock_known_at` 的新frontier，current receipt只许可其立即next common OPEN。旧receipt、同价重发、旧root、退役root一律拒绝。同一票在首次登记提交时原子消费；未提交也在该OPEN过期，不能次日缓存。
- 续量不再重算新Q。每次CLOSE和OPEN核整体剩余Q-F的日期整手、容量、剩余初仓成本预算、风险和责任；若全部余量不满足则不提交、不缩目标、不另开小目标，等待以后新票。partial实际已用成本及每单费用必须计入剩余24k；不得因部分填充重置预算。新增订单量+已填F不得超过Q。probe续量的existing_risk固定为 `max(0,filled_probe_qty*(current_buy_px-S_raw*(1-SLIP))+all_probe_entry_fees+fee(filled_probe_qty,S_raw*(1-SLIP),sell))`；零库存该项为0。remaining_risk=max(0,3000-existing_risk)。余量以当次原dated size/费用核可全额提交，q合法且可行上界>=Q-F才可提交Q-F，不提交可行上界作为新目标。
- 初仓parent从登记起占同股责任，即使F=0且本次订单已终结也不能被AB偷占。若根失败，永远退役该根未填余量；撤单/卖出未结不能FLAT。已知F=0且所有取消对账完毕可释放；F>0须先完成对应卖出。旧根失败后的新根也不继承旧Q/F/permit。
- 真正probe完成条件为F=Q、live_leaves=0、全账对齐及complete_known_at已知。0fill或partial绝非完成。Q-F不能改名ADD。
- 每次卖出按实际/代理买入日分lot审T+1，不可仅按最早entry_day放行后来补量。退出后旧target永久退役；再次开仓须晚于完成/解锁的一张新票，不能重放原permit。AB也仍须新的原A/B出生事件。

## 7. PRICE持有与唯一一次ADD

PRICE初仓和ADD共用本root的一条S保护，不引入CP保护或新价格阈值。这是本轮在收益前选定的新PRICE保护合同，不称原CP机制原样套用到新层；AB原I/CP保护及追加完全不改。S只按第2节原冻结公式更新。old I关闭、CP absent/unknown、M3 off均不是PRICE卖出理由；原行业四事实失败只禁止新增。

每日有效CLOSE先测C<=S_old，成立即永久退役root并安排下一共同OPEN卖出全部已填库存；不把新抬S用于回杀当日。根已失败不再发买票。信号后次开卖出仍先查原raw/source/factor/rights/dated规则，UNKNOWN必须锁存而不是假卖。存活时抬S_new，下次开盘仅用这一已知保护。已有持仓没有另加开盘/日内触线即时卖规则；价格跳空风险可超过3000，不掩盖。

唯一PRICE ADD须同时满足：
1. probe已完成且本收据known_at严格晚于其complete_known_at；全订单责任已结、健康持仓、root活跃且从未创建过另一个ADD parent。
2. 当前真正新frontier收据，且该根量态CONFIRMED（可以是历史已确认但本日金额缺失而保留的确认事实）；出生同票不得兼发probe和ADD。
3. 收盘四行业事实全true；本轮 NET80 净清算权益严格>0。OPEN再次严格>0且raw_open>S_raw。权益是本轮cash+已确认receivable+全部库存按卖出滑点净值−dated独立卖费，不能借用同股上一round股息或旧回报。
4. 沿原小仓预算：`budget=min(24000,max(0,48000-held_qty*raw_open))`。买价为raw_open*(1+SLIP)。使用真实已知S_raw计算现有初层风险：`max(0,held_probe_qty*(buy_px-S_raw*(1-SLIP))+probe_entry_fees+fee(held_probe_qty,S_raw*(1-SLIP),sell))`。remaining_risk=max(0,3000-existing_risk)。用原dated `size`、当次收据收盘冻结的前量容量和相同S_raw计算ADD q/买费/计划风险。与AB原规则的差异仅为其实际保护由I/CP改成本PRICE S，不假用更高CP线减少风险。
5. q=0/OPEN<=S/OPEN净权益<=0仍是未提交，不创建ADD target；以后只有新票可重新候选。一旦q>0并首次登记提交，独立ADD target_Q固定；同根永不创建第二个ADD target。0fill不算完成或正成交，但也不能重新开第二个ADD；partial只补本ADD余量。
6. ADD续余量仍要求新frontier、CONFIRMED、行业四真、close/open正净权益、健康持仓、terminal对账后新票，且检查原24k ADD目标的剩余成本、48k当前库存市值槽和3000组合风险。预算=`min(24000-本ADD累计已花买入本金及买费,max(0,48000-全部已填持仓数量*raw_open))`，不低于0。风险中held_qty为已填probe+已填ADD，existing_risk=`max(0,held_qty*(current_buy_px-S_raw*(1-SLIP))+全部已发生入场费+fee(held_qty,S_raw*(1-SLIP),sell))`。共同保护的既有合并库存只收一次假设整体卖费，不分层重复最小费；新余量仍按原size自身买费及自身假设卖费计算增量风险，保持原分开规划的保守结构。余量全额不满足时不提交，不另定Q。
7. ADD使用共同S，因此不另外独立sell_add后再填回；S失败卖全部，终结本PRICE生命周期。PRICE不得消费CP receipt或触发原CP-add。AB持仓只执行原CP-add，不接受PRICE ADD，不被量态门改写。AB原单次追加锁和保护规则逐列保留。

## 8. 原容量、权益与UNKNOWN边界

容量精确沿旧式：截至信号收盘（包含该收盘日）的最近20个正raw_volume观察均值×1%，按原代码取整/整手规则；对next OPEN属于已知前量。不能用执行日成交量回填。每张新收据可更新当次容量约束，但不能增大既有target_Q。

2022只复用既已审402+24+10共436事件权限，2024只复用已审165事件权限，不把同股其他日期自动准入。d_source只解释冻结factor，d_cash算NET80现金，d_ref不能混用。坐标权限与权益权限分离：已知登记Q=0的pending可用纯坐标桥，不给股息；已持有而权益未验证不能凭entry10证明过关。

公司行动必须用每臂/每窗/每sid/每经济事件登记CLOSE的自有已填probe+add库存，claim属于当时round。每次事件独立幂等；ex前计应收，pay CLOSE只在cash/receivable间转移，下一共同OPEN可用。卖出/UNKNOWN不抹去已确认claim；重入不继承上一round的盈利。固定预算不因股息扩张。

S在原signal坐标保存，合法纯现金桥只把其raw投影依Fold/Fnew转换；不重写冻结a/U/Ca/R、量B或把经济事件当新根。新PRICE遇已知未准入行动、未知source/factor/价格/订单责任时锁UNKNOWN；原AB严格用各窗已封存guard顺序，不借新增通道偷偷修订旧语义。如源缺口只可事后知道，仍分列financial_coverage_status，不倒灌历史选择。任何两通道覆盖规则实际差异须报告，不称统一完整权益认证。

UNKNOWN保留round、最后已知库存、已确认claims、未决target/退出责任及失败phase。不能据后来有效价格恢复入场、计算未知后收益或把该股当FLAT；没有共享账户也必须注明资本责任未释放。无明确恢复证据/另版合同，本轮不自动解锁。

## 9. 每日唯一事件顺序

1. 已登记有效claim的ex OPEN前确认；保持原经济时钟。
2. OPEN source/price/factor/权益核验；先处理已有卖出责任，再处理该股允许的买单。AB严格走原held_open；PRICE全卖优先于任何probe/ADD续量。T+1按lot检查。
3. 消费前日预约的初始开盘机会；预检失败不补行业名额、不转角色。
4. CLOSE更新市场价格根（无论持有哪条lane均可作事实记录），按owner_lane运行持有管理。AB仍原I/CP；PRICE先旧S失效后有效E0抬线，再作未来ADD邀请。
5. 登记CLOSE库存快照：已卖清为0；已发卖出pending但尚有库存仍属于登记库存；今日初始预约不算库存。
6. 在本窗允许的新初仓收据及合法既有probe续量之间，同股去重、行业四事实/close尺寸检查，按已知PVR降序/sid、随后未知PRICE的sid顺序排两个初始预约；AB保留原PVR已知门。
7. pay CLOSE结算既有claim。任何今日才知道的解除责任，只允许严格晚于该known_at的新票；不得重用同时间更早的票。

## 10. 必须补齐的接口和资料，不能沿用的旧捷径

- `fast_entry_equity_2022_v1/lifecycle.py::role_options/prepare` 会引入FAST_CORE/MOBILE_CP和旧event_Q/continuing_Q；不能用于PRICE。它只能作为来源审计参考。
- 原 `checkclose` 缓存key=(sid,day)，不能同时给AB I floor与PRICE S使用。新key至少含window/arm/lane/role/root/receipt/day/floor/target版本；原AB关闭PRICE时结果必须exact。
- `getmeta(sid,date)`仅含dated规则可共享；带floor/预算/风险/库存的缓存不能共享。合成测试必须对同股同日不同AB I_floor/PRICE S，分别AB先算与PRICE先算，核各自手数/费用/风险结果及原AB结果不随调用顺序变化。
- 原 `checkclose/flags` 要求当日volume_eligible，不能只换floor后套给PRICE。PRICE使用冻结price_valid、有限raw_close/factor与可计算的原历史20正raw_volume容量；不额外要求当日amount/volume_eligible、量CONFIRMED或旧stock资格。容量不可计算可导致尺寸UNKNOWN，但不得把金额确认未知等同容量未知。原AB flags保持不变。
- 原 `entry_open` 把q0与open<=floor叫NOFILL并删除state，且一次写q为fill；不能承载固定Q、partial、ACK责任。保留AB历史输出，但新PRICE要先登记目标并用新事件类型。
- 原 `held_close` 包含I退出、CP未知锁、M3追加；不能换个标签复用。PRICE需要独立持有管理，只复用已审费用/尺寸/权益数学和已核raw事实。
- 原 `held_open` 用i_floor计算风险且用entry_day检查T+1；PRICE必须自身S及逐lot可卖量，不能把partial补单和ADD放入旧core总数后漏掉当日买入限制。
- 原 `freeze_unknown` 的简化state只留round_id；新增责任账本必须保留完整冻结快照，不因此改变AB已封存行为或释放资金。
- per-receipt `UNSTARTED_TARGET_SIZE_CHECKS`只是不曾建parent的预检，不能用作续量、ADD或最终Q；旧AB/fast flat仅为旧参考，不是新联合臂状态。
- 全1709已存DAILY_STATES/RECEIPTS只覆盖三个固定观察窗，缺2023、2024年1月至8月、2025；不能跨缺口跳更新S/失败/新票。实现前从原 `independent_channel_full1709_preflight_v1/engine.py::replay` 使用原full warm输入无改式补齐生命周期所需连续日期，并核对与已封存重叠行exact。延续管理所需行业原native事实和容量同样按原定义补齐；不能把2022/24/26三个缓存拼成连续历史。该补齐只产生市场/资格事实，不计算新策略收益。
- 所有输入/定义/数据/行业来源和输出hash封存；source identity细节、窗口边界、价格根和目标责任时钟必须可追溯。现有上游复权/native事实未由本轮重新认证PIT。

## 11. 放行前必测及一次运行门

G0（当前）：本唯一合同、源清单、全窗行业过滤及点名病例事实。没有新经济。

G1：父任务确认合同后实现import-safe适配器；仅运行合成与baseline-only回归，不启用PRICE经济。至少覆盖：
- AB禁用PRICE两窗逐列/逐动作/claim exact；AB与PRICE同日优先、原AB next-open拒绝无fallback；跨股PVR2槽、UNKNOWN排名、开盘失败不补槽；同股partial/pending/UNKNOWN不可重入。
- no-submit q0、open<=S与真正提交0fill分离；固定Q先于F、partial不升Q、cancel未ACK不解锁、cancel ACK后无新票不续、latefill更新/锁定、重复fill幂等、冲突重复/超填UNKNOWN、oldroot/退役parent/过期票拒绝、同票不得双发probe+ADD。
- probe全部完成且新票晚于完成才ADD；0fill ADD续同parent；partial ADD不创建第二个目标；额外fill的逐lotT+1；根失效取消余量并保留卖出责任。
- 旧S先触线后抬S、量未知不挡首探、CONFIRMED不倒销、sector false不卖、source change不卖、不解锁；2026-05-18边界。
- cash登记Q0/partial/已卖/卖出pending、NET80 exact、claims跨退出/UNKNOWN持续且重入隔离、S坐标桥、未准入行动、source/日期rule失败顺序。
- 真正截断原raw/facts/行业/CP/日历/量容量后市场和消费者前缀一致；新日志同run去重。合成输入不偷用真实旧回报生成新路径证明。
- OPEN隔离不变性：固定next-common OPEN及当时已知source/factor/权益/规则元数据，任意更改该日H/L/C/amount/volume/日终flags，以及由其产生的market.phase/failed/root_id/valid，OPEN动作、Q和fee必须完全不变；只有之后CLOSE可变。测试必须覆盖预计算当日价格失败、量确认及root切换，防止提前使用日线状态。

G2：独审通过、父任务对冻结合同/代码hash给明确经济放行后，才一次运行两窗两个消费者。run-once记录须原子创建；检查协议、代码、输入、独审及授权哈希，任何不匹配拒绝。禁止预先小跑PRICE收益、根据输赢修合同、再选最好结果。逻辑bug可修，但保留失败和是否看过收益的记录，重新独审并由父任务决定是否允许技术重跑，不自动当新实验。

## 12. 预承诺报告与结论边界

按窗、lane分别报告市场票→行业→同股阻挡→PVR已知/未知排序组→close可行→2槽→next-open预检→固定目标→proxy填充→持有→闭合/UNKNOWN/CENSORED。保留无parent预检拒绝、已登记0fill/partial（合成测试）与真实未知三类，不混分母。

首要比较单位固定为股票×出生窗口，不以单个闭合回合胜率择优。每臂对同一1709名册逐股汇总本窗全部首次入场、重入、probe/ADD、买卖费用和自有现金权益。分列：(a)已实现买卖净额、已确认NET80权益收入及两者之和；(b)截至统一终点的开放且可估值库存净值、剩余成本与净未实现盈亏，并旁列已确认应收；(c)UNKNOWN库存/订单/权益责任、最后已知估值日期及冻结数额，不补到终点；(d)真正从未进入且责任为已知零的股票。

报告成本归属预先固定：原AB sell_add/sell_all沿原角色，角色内按fill已知时钟FIFO分摊该fill实际买费与买成本；PRICE全卖/合成partial卖同样按角色内FIFO。已实现买卖净额=已卖数量卖价收入−实际卖费−其分摊买成本（含买费）；权益收入在合法ex确认时计一次、pay只转资产。已知开放净未实现=终点可验证库存按卖出滑点变现值−dated预计卖费−剩余买成本。已知总盈亏=已实现买卖净额+已确认权益收入+已知开放净未实现；应收已包含于已确认权益收入，不能再加一次。这里FIFO仅为透明研究归属，不改变原交易/NET80税情景。闭合回合此分解须逐项对齐原cash+receivable。不能把cashflow_to_date直接当已实现PnL，或把未回收本金叫亏损。

全部闭合股票的净额可直接汇总；有开放/UNKNOWN者必须单列可辨认部分与未确定整体，不填0、不只选已赢回合。共同可比覆盖集合、每臂独有可用集合和被排除原因同时公布，固定全体分母不改。上述逐股净额仍不是完整账户回报。

主比较只两条FULL消费者。初始层CORE为各自FULL实际proxy入/退出和数量、独立dated买卖费及其自有权益诊断，不另跑会提前释放state的core-only策略。收益必须同时列：条件闭合、财务证据可用闭合、双方共同可比分母；UNKNOWN和覆盖缺口非随机，不填0。原2022/2024收益不可粘到新entry上。

必须先证明两臂原AB原始permit集合、事件ID及原许可字段数量精确不变，再明确A/B受到什么影响：相同AB事件保留/被PRICE同股持仓、待单、partial或UNKNOWN先占/被PRICE同行业两槽挤出/因既有状态不同新增或丢失；首次分叉日期、竞争队列、PVR、可行性、占用round和后续连锁。PRICE自身净贡献与AB贡献变化分开，二者相加对齐联合逐股变化，不能只报PRICE独有赢家。相同AB event且相同路径应actions/claims/exit exact，否则属于实现错误。旧108大赢家逐一标同事件保留、异时同股持有、被挤出、UNKNOWN或未参与，不能把“有新票”写成保住收益。

须报告 PRICE 完整胜负分布、初层与FULL净额、均额、右尾、费用、风险超预算跳空、持有长度、执行/财务UNKNOWN、一字代理依赖；另列行业门造成的启动延迟与PVR资源损失。可解释性不能只挑新增赢家。两窗方向不同或一窗变好另一窗变差均原样呈现，不换门、换阈值或删窗。

本次最多支持“在已冻结代理和已见样本下是否观察到逐股改善”的结论，不把一个指标为正当整体策略证实，不把正常右侧追涨后止损本身当算法失败。显著依赖UNKNOWN、一字价、少数右尾或挤掉原A/B大赢家必须具体披露。绝不将逐股净额相加称共享账户回报、真实ACK、真实可成交或实盘利润。

## 13. 当前授权状态

截至本草案：只读核验既有来源与行业计数，未导入旧经济runner，未跑新经济，未创建任何真实订单、成交或ACK。必要业务选择已唯一写定，不需要通过试收益来补选项。尚需父任务确认此合同和独立审查；连续生命周期事实补齐、代码实现、baseline-only回归及一次新经济分别遵守上述阶段门。
