# 统一持仓状态卡：原 No60 接口审查

本件是静态代码接口合同；未执行 Account、模型、合成路径、回测或参数验证。主设计的验证条件、TRIAL 数量和总目标公式仍由设计卡冻结，本审查不另外选择规则。旧封版不改，不引入 G/C1/D10。

## 必须修改与可以复用

| 接口 | 原行为与 source 行 | 统一状态必须处理 | 可保留部分 |
|---|---|---|---|
| 原信号/结构 epoch | `joint_v3.py:213–219` 的 `(I_target, segment)` 变化推进 epoch；`event.Q` 成功更新 global_watch | 原 I epoch 不是实际持仓 campaign，不能把 intent/reserve/actual fill 混为一个起点；状态须绑定 source epoch、实际首 fill 和 campaign ID，既有持仓不能因新行业 attempt 或 I epoch 换名而清空责任 | 原 eligibility、global_watch 的当时输入、源时钟和 epoch 计算可复用，不重新生成 E0/I/CP |
| 首次入场合并 | `joint_v3.py:243–257` 可同时有 CORE/mobile 两角色；CORE 需 flat+event.Q+coreepoch未锁；mobile 需 fresh CP+continuing.Q；255 每次 CP 独立 min(2%NAV,10%NAV余量) | CORE 或 flat-mobile 都先产生一个 TRIAL 目标，同日双资格最多一个同股目标/订单；保留真实 admission_source 与 receipt，不能把 TRIAL 当成伪造 CP 或新源角色 | 原 ACT、exit_pending、buy_pending、quote/floor 可得性屏障继续生效 |
| 验证后加仓 | 原255把每 CP 当独立新 gross 额度 | 先确定该股总目标，再计算扣除实际持股及未ACK承诺后的正差额；新 CP 是授权/证据，不自动再给独立2%。验证须发生于真实首 fill 之后，不能同一个首次信号立即给自己验证 | 原原子数量预留和实际资金账可继续承接差额订单；分层只作成交/成本追踪，不再拥有互相独立目标 |
| 唯一股票资金位 | `native_rank.py:47–74` 已合并同股角色为 unique stock slot；round12、原H1 slot tie、UNKNOWN保原位 | 合并目标应在 priority_plan 前完成，且每次 planning 只调用一次；TRIAL/TOPUP 不新增第二个股票位，不用资金不足重排或第二轮填空 | 原排序逻辑可复用，原score口径保留；`apply_priority:76–91` 不改其他字段的旧断言需更新为新卡契约，不能假称旧纯rank改动仍成立 |
| CORE 竞争 confirmed | 有效 `route_without_account_check.py:8–10` 仅 mobile 可加 confirmed 候选；`request:226` 非mobile拒绝confirmed | 若设计允许行业已confirmed时CORE竞争资金，必须同步改 route 候选池与 request 的 `mobile_role_required`。CORE仍以真实CORE_Q为来源，不伪造CP、不改名mobile绕过token检查。行业confirmed只说明行业资金资格，不等于新股票已验证 | No60去confirmed60资本项保留，其他行业/个股/现金/probe限制是否原样保留须卡上明确 |
| 全pool CORE锁 | `model_without_account_check.py:223` 只在probe校验CORE epoch lock；`pilot.py:70` 只在core真实买成后写core_epoch | CORE可走confirmed后，lock须在选pool之前或request的全pool共同入口检查；新统一trial锁也必须覆盖flat-mobile首成交，防改源/改池重复TRIAL。reserve/pending另有锁，不能等fill前容许并行订单 | 原 actual fill 才写实际持仓事实；零fill不能伪记已持有，原source epoch历史不随flat删除 |
| sizing/preview | `study.py:42–66` 仅kind=core有all-in风险校验；mobile仅冻结gross；reserve:94–103要求q≤cap、gross≤budget、knownOPEN、无同股买卖pending | 若TRIAL统一使用同一风险合同，必须让 CORE来源和CP来源都显式调用该合同，不能仅写`stage=TRIAL`而让mobile绕过；若TOPUP用不同总目标也须显式冻结，不借`kind=core`重命名改变退出语义 | 复用合法整数搜索、原fees/fee最低额、knownOPEN≤floor拒绝、冻结cap/gross、次合法OPEN时钟。不得因跳空上调已授权总目标或预算 |
| reserve/ACK/partial | `J:92–128` 镜像与真实账桥，`J:278/route:7` ACK前禁admit；`study.py:94–103` 只接受实际可预留q | 状态转移只能挂在原真实reserve/fill/cancelACK回调之后；目标、承诺股数、已填股数分开；部分成交不等于完成目标，也不能新开第二单弥补；同步/检查点须保存新状态和幂等ID | 原order_bridge、actualcallback、fees、pending_ACK guard、reserve一致性断言复用，不另造余额引擎 |
| 退出 | `J:225–240` ACT/I优先；mobile旧CP先检查再ratchet；CORE_I不是该分支独立价格stop；`pilot.py:104–115` 退出目标层合并 | 统一持仓应明确一种持仓级退出责任，不能TRIAL来源决定持有时偷偷切换不同hardstop。若不改变原退出，必须诚实保留源层差异。EXIT_PENDING覆盖部分卖出余量，禁止新增风险；新信号不撤销原退出 | 可继续调用原sell/ledger.fill_exit，不以未来最低点/保护线价代替执行价；全股退出应按全部真实live layer IDs，不仅最后CP层 |
| 线下risk0 | 继承的 `budget_v3/model.py:106–117` 用持股mark-to-floor正距离；mark≤floor时为0，capital不为0 | 最小一致修正是新增独立的pending退出参考责任，并在同一resources API及route/request admission使用；只在报表加字段而准入仍读0不构成修正。责任基于当时已批准入场参考、剩余实际单位、同一原fee域；未成交不释放，partial只按真实已卖份额释放，拆股不减少货币责任 | 保留真实capital/cash/reserve/receivable，真实sell后才结算。不得借责任字段修改账面NAV、现金，或说银之杰已经利用risk0超额买入 |
| market/ledger | `sector_account.py:688–809,846–910`；`fast_market.py:45–66` | 保留T+1可卖批次、容量、daily-H/L成交代理、整数与零股规则、原fee累计最低额、原权息与paydate不明应收处理；状态仅观察真实结果 | financialengine、FillWindow、sale settlement、fee schedule、corporate action桥全部复用；不假定stop保证成交 |

## 总目标接口应冻结的最小字段

同一sid只有一个状态记录，至少包括：`campaign_id`、`source_epoch`、`source_segment`、`source_role`、`source_evidence_id`、`position_stage`、`actual_first_fill_at`、`verification_known_at`、`target_total_gross/quantity及其计价口径`、`target_frozen_at`、`approved_delta_cap/gross`、`actual_shares`、`pending_order_id/remaining_commitment`、`pending_cancel_ack`、`exit_order_id/remaining_sell_target`、`reference_risk_basis`和`pending_exit_responsibility`。来源、状态、资金池、物理层ID必须分开。

决策CLOSE确定总目标和最大新增合同；次OPEN先原真实退出/结算，再按已知OPEN检查剩余目标差额及原资金约束。持股市值与新买执行gross在总目标中的计价定义要写清；同股pending承诺需扣除且不能又创建新单。OPEN只允许缩量或拒绝，不得越过冻结最大新增数/金额。目标金额不自动成为已成交金额，资金不足不自动标记已验证/已达目标。

原ranking按股票，一只股票一个差额合同。原同日CORE优先只是同股两角色的旧兼容排序，不应再作为统一TRIAL之后第二笔mobile权限。

## CP消耗与失败/重试合同

原真实native顺序不是“每次看见CP就消耗”。route:4–6先核fresh未用token、15–27纯预估/资金搜索；q=0直接返回，不调用request，所以原正常preview/route失败不consume。进入 `request:218–232` 后，request ID先写stock_requests，token在232消费，**随后**才migrate与资源检查；因此request本身不是无副作用preview，直接调用且失败可能留下ID/CP消费。这项必须在新接口中明确修正为通过全部校验后原子commit，或保留为显式失败终态；不能无声rollback/重试。

纸面最小兼容合同如下，不改变时效：

| 事件 | 状态/证据责任 |
|---|---|
| CLOSE只有合格信号；OPEN缺报价、低于线、最小单位失败或route无法fund | 没有真实reserve，不消费CP；不得制造已成交或提高stage。该CP只在原有效确认时钟使用，不能变成多日stale授权。CORE锁未因零成交而写入 |
| budget request与真实reserve均成功 | 同一CP只消费一次，绑定唯一logical order；TRIAL_PENDING/TOPUP_PENDING，资源持续占用，不以没成交撤回消费 |
| 真实reserve前后出现异常 | 原程序assert即停止；新实现要明确原子提交/补偿ACK合同，不能继续另一路buy并把资源对账强制抹平 |
| 成功reserve但市场无合法成交窗口 | 原单在原one-session lease内保留；到CLOSE按原expire/cancelACK释放余量。CP仍已消费；后日不得复用该CP无条件再开单 |
| 部分成交 | 首actual fill建立/延续同一个TRIAL或TOPUP campaign；native一个logical order后续matching用fill_step，不以每callback新买最小整手重新预留/收最低费。原单租期后余量cancelACK，已买持股保留 |
| 后续retry | 同一原单的matching重试不再消费；过期后新订单必须有当前新资格/新canonical证据并重新计算目标差额，不能用旧CP重造2%层。残余已成交不能被当flat；只因未达目标不构成新信号 |
| cancel_pending/ACK race | ACK前全部未成交承诺仍占资源；真实fill先发生就保留已买库存，不能ACK删除该lot。J回调顺序原样复用 |

## 退出责任、权息和执行的最小一致性

`EXIT_PENDING`是未完成事实，不是发出卖单即flat。原planning与opening均有同股pending屏障；原opening全体旧退出先于新reserve，保留此顺序。原C.fill_exit只按可卖批次、容量和合法数量实际成交，状态不得预扣股票或预加现金。卖出应收只在原due_at结算后进入available；股息paydate未知仍是应收。

新增风险责任只是授权视图字段，不能修改原ledger。其原入场参考依据需保存，不能在跌线当天以零距离初始化；费用最低额按logical order累计，不按虚拟层各收一次。拆股后数量、单位保护线、pending订单与卡中的target/cap同桥调整，货币预算/预留不凭拆股扩大；不得重造订单、CP和campaign。旧已可卖股与新送股的sellable_at仍按原批次保留。

GAP时原preview会按已知OPEN缩量/拒绝、已持股可能在下一合法OPEN以远离线的价卖。TRIAL命名、参考风险占用和EXIT_PENDING不能保证单次最大损失。此接口审查不新增隔夜buffer、不选择等待期，也不复活旧候选。

## 纯代码反例清单（未运行）

1. 同日CORE_Q和freshCP都成立、flat：如果保留两intent，OPEN旧`done`只让先funded的一种过，但次日新CP仍可独立2%，没有实现统一验证门。必须先合并总目标。
2. 行业已confirmed但probe紧：只改route让CORE进confirmed，request仍返回`mobile_role_required`；只改request则route仍无confirmed候选；两处改却不扩corelock，会出现pool绕锁。
3. 以`role='mobile'`冒充CORE：没有真实CP会被request拒绝，伪造CP则破坏源语义；以`kind='core'`冒充TRIAL则意外改变原保护分支。
4. CP已成功reserve但零fill：把expiry当成“证据未用”会允许同一旧凭证重复申请；相反，纯preview就调用request可能在真正fund失败时提前消耗。
5. 部分trial已买、旧单尚pending或未ACK：以target−filled直接再下单会双计剩余目标/漏算预留，且可能重复收最低费。
6. 跌线后零距离、退出因容量只能卖一部分：状态若立即回flat或重置参考责任，会丢未平库存及原T+1责任。新行业attempt也不能洗掉它。
7. 原持仓拆股：只改真实shares、不改卡中target/pending责任单位，可凭数量变化虚构扩仓缺口。只按层收最低费则虚构成本。
8. 新信号在EXIT_PENDING期间出现：若用新CP清除退出、更新floor或重新给TRIAL，违反原不可撤销结构退出与原同股pending屏障。

上述是接口矛盾推演，不是已运行合成实验，不带收益或覆盖结论。状态卡中验证公式、TRIAL/总目标金额、统一持仓退出与旧CORE/mobile保护差异、参考责任具体计算域必须由主设计明确；在冻结前不能宣称可直接接线或原金融函数全部无需变化。
