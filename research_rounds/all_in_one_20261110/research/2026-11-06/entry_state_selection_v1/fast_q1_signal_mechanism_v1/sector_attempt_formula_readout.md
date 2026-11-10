# 原 fast 机制、行业 attempt 缺口与不可直接晋级的边界

## 结论先行

1. 本次合流没有丢失个股 G 入场资格。原 i_buy 本来就要求 G_ready、G≥2 和当日新证据。event.Q 不另加 G 不是“无 G 门”。
2. 本次确实没有接原 joint 的行业 active attempt。这个 active 的开启/失效是纯市场 E0/CP/价格路径，不是账户现金门。不能把行业市场 attempt 与财务 level、迁池、行业暴露和 ACT 混为一谈。
3. 但恢复完整 active 总门不能被当成 Q1 修复。5031 既有许可中 active=3255，inactive=1776；后者是当前行业 E0 首 CP 前1558、同一 E0 attempt 失败后等待147、E0_OFF71。Q1 的1875许可依次是1147、657、53、18。主体是首次等待，不是失败反复。
4. 仅抑制同一行业 E0 attempt 失败后的 fast/空仓 CP，并保留独立可行 AB，现有许可中触及142条，Q1为51条。这是已发生队列的事前状态标签，不是新策略删单结果、胜率或收益。
5. 7启动共654日均有精确行业当日状态。海能达原 Q 首次9/23，行业 active 9/26；银之杰原 CP 9/12、CORE9/19，行业 active9/20。把首次等待一并关闭会产生启动延迟。只关失败后等待保留这些最早资格，但未证明能实际入场、持有或不丢牛。
6. 行业状态没有 UNKNOWN，不代表执行已知。5031许可中的559执行 UNKNOWN完整保留：active组357，inactive组202。2024权益未同口径，启动窗口仅因果说明。

## 核验方式和文件

- `sector_attempt_diagnostic.py`只抽取原 trace/Stage 函数定义，读原数值 CP 缓存，不调用 calculate/Account/Runner/lifecycle。
- 90行业从各自完整暖历史重建 canonical receipt 身份和 Stage，全部26原状态字段逐位匹配 refs.state。源文件、数值输入和输出先按 manifest SHA256核对。
- `sector_attempt_permits_2022.csv`：5031既有许可，保留原 execution status，不新增经济结果。
- `sector_attempt_startup_rows.csv`：654启动日，exact-day join，不ffill缺日。
- `sector_attempt_daily_2022.csv`：21780行业日。
- `sector_attempt_failure_only_summary.json`：首次/失败/E0_OFF及AB保留边界。
- `sector_attempt_startup_summary.json`、`sector_attempt_verification.json`、source/output hash清单。
- 首版JSON输出NaT问题及跨episode旧失败的展示字段已修正，修订前脚本、CSV及摘要副本保留。最终失败展示按当前E0、source segment、unknown边界隔离；首次/复发计数不使用跨episode全局ffill。

## 精确源路径约定

- R=`/Users/bytedance/Documents/ChatGPT/money/research_rounds`
- W=`/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds`
- P=`/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1`

下列相对路径和行号均指实际文件，不是概念伪代码。

## 1. E0 是相对极点的确认和保护状态，不是宏观上升趋势

R/pv-strength-b5-20261025/code/evidence.py:100–146：使用正且有限C/V的有效观察时钟。r_t=ln(C_t/C_{t-1})；σ_t=max(sqrt(mean(此前63个r²)),1e−8)；V基准为此前21观察量中位数。方向 d 初值−1，当前方向继续创新极点时刷新极点 a。反向确认量为

K_t = (−d)·ln(C_t/C_a)·clip(sqrt(mean(V_{a+1:t})/median(V_{a−21:a−1})),0.5,2)/(sqrt(5)·σ_a)。

K≥1 时发 event=−d，确认pivot=C_a，方向切换且极点转到当前观察。阈值尺度固定在该极点，不用未来波动。

R/pv-strength-b5-20261025/code/policy.py:86–114：先判 active且C≤旧floor则退出；上行event=1在尚未active且不是同日刚退出时开E0，floor=pivot；已有active遇新up只令floor=max(旧floor,pivot)。负event本身不直接结束E0；穿保护底才结束。此链条禁用 decline_candidate，因此没有下跌参与回收旁路（W/native-I-cache-interface-20261031/cache.py:23–28）。

跌市局部反弹也能相对近期低极点完成sqrt(5)尺度确认。因此“E0重开”不等于已收复前一失败结构，更不保证持续净推进。

## 2. G 与原 i_buy 的准确逻辑

基础G证据：R/pv-strength-b4-20261025/code/model.py:163–182。
- μ_h=EWMA(r, alpha=2/(h+1))，h=5,21，从首个收益暖机。
- s=max(1.4826·median(|此前63个r|),1e−8)。注意这不同于E0的RMS尺度。
- q_eff=(r/s)·sqrt(clip(V/median(此前21V),1,4))；q_eff≥2急上、≤−2急下。
- S21/S63是事件锚定方向，不是21/63日均线。model.py:122–160、195–255：对方向性新前沿才记增量，价格位移和量加权前沿credit都达到sqrt(h)·锚定s才确认，之后只保留相反方向候选；新高/低会重置反向候选。

G分类：R/b5-g1-20261025/code/grade.py:20–46。
- S21=S63=0：G=0。
- μ21<0、μ5≤0：两尺度皆−1时G=−3，否则−2。
- μ21<0、μ5>0：S21=1时G=1，否则−1。
- μ21>0：两尺度皆1则G=3；仅S21=1则G=2；否则μ5>0为1，余为−1。
- μ21=0：按μ5正/负/零给1/−1/0。
- 两尺度上行且sqrt(5)μ5/s、sqrt(21)μ21/s均≥1，升为4。
- 急上且当天E0上行event且μ5>0，G至少2；快速不利位移可降至−2，急下覆盖至≤−3。
- 拟升级但没有fresh证据时保留前G；降级无需fresh。

fresh_up 的来源是 OR（grade.py:24–29）：
1. 新E0量价up事件；
2. 新S21或S63向上确认；
3. S21连续为上行，且其running extreme price又创严格新高。
第3项允许持续结构内多日给新入场证据，不需要G级别变化，也不需要新I根。

R/b5-g1-20261025/code/policies_g1.py:16–34：
opportunity = E0_active ∧ G_ready ∧ (G≥2) ∧ (E0_entered ∨ fresh_up)。
i_buy = I_active_after_update ∧ opportunity。
I原本关闭时可由opportunity开启，但同日刚因结构退出不能重开。I保持期间只因E0失效或C≤旧I floor退出；G1_I没有G冷退出（use_x=False）。幸存后floor=max(旧I floor,E0 floor)。

因此存在两种不同的“反复”：
- 同I根重复i_buy：真实的新前沿/确认证据，但成交后不允许再消费CORE epoch。
- I失效后后续新根：原保护授权已重新建立，epoch也不同，可再次试仓。原式没有保存“上一失败I根的推进/保护底是否被修复”的记忆。不得把这说成同根重复成交bug。

## 3. event.Q 含什么、不含什么

R/actual-risk-recovery-20261027/code/engine.py:31–47把stock trend替换为原I_target，把buy_allowed替换为原market buyability AND exact-day i_buy。continuing.Q只去掉i_buy。

R/rs-h1-execution-20261025/code/sector_stock_admission.py:185–220的S0包括：共同股票/行业readiness、历史market可买、市值>100亿元、I状态、issuer/sector身份、股票同日H1可读、行业同日观察/同日H1可读、行业E0为真。任一UNKNOWN优先于其他FALSE。

不存在：额外行业M3、行业G暖、行业CP attempt active、行业财务level、H1正值阈值、PVR>50门。H1可读不等于正强度。共同ready/行业E0的桥接在current_pool_bridge.py:323–365；源缺口在298–320保留UNKNOWN。

## 4. PVR 的精确式及用途边界

W/pvr-current-v3-information-capital-20261101/original_score_function.py:4–18：
- r_t=ln(C_t/C_{t-1})。
- s_t=max(1.4826·median(|r_{t−63:t−1}|),1e−8)。
- B_t=median(amount_{t−21:t−1})。
- u_t=tanh(r_t/s_t)，b_t=tanh(ln(amount_t/B_t))。
- e_t=u_t·(1+0.5·|u_t|·b_t)。
- E_t=Σ(j=0..20) w_j e_{t−j}，w_j=0.9^j/Σ(k=0..20)0.9^k。
- PVR_t=50+50·tanh(2E_t)。

无效观察或source segment改变重启准备。它是自波动归一化的近期净推进，带量价修饰；不是胜率、不是市场绝对强弱、不是未消费证据账本。21观察滚窗大量重叠，tanh压缩强值，过去冲量可在当前分数中残留；I根失效不会重置PVR，因为PVR没有I输入。

P/fast_entry_equity_2022_v1/prepare_inputs.py:140–152读既有PVR，PVR_known要求score有限、原3日完整性state≥0、当日valid。state≥0不是state=1，并不要求连续3日≥60。lifecycle.py:227–245只在同行业当日可行候选按PVR降序取最多2张；没有PVR绝对下限。弱市仍可有本行业相对前两名，且每日两张不是同时只持有两股。

## 5. 消费、复用和重置

- W/case-stage-ledger-20261031/v3/joint_v3.py:216–219：每次(I_target,segment)变化（包括关I）都递增counter并清watch；当日event.Q真把epoch装watch。
- joint_v3.py:244：空仓且该epoch未CORE消费才给CORE。原fill消费在R/probe-pyramid-pilot-20261029/code/pilot.py:59–73，仅positive receipt写core_epoch。
- 新消费者P/fast_entry_equity_2022_v1/lifecycle.py:46–52、79–89、98–117也仅positive fill消费I epoch或canonical CP。CP不消费CORE epoch；NOFILL和未获槽不消费。独立AB资格不受fast epoch锁限制。
- CP市场计算本身在R/continuous-protection-lines-20261028/code/model.py:26–50：只有新log前沿才加credit，价格位移与credit都≥sqrt(5)·冻结scale才发receipt；发后anchor/frontier置当前价、credit归零，scale取当前历史尺度。I失效/unprepared、E0down、SEEK更低anchor也可重置。旧价格推进不能直接复用为新receipt。
- 原预算层CP在request/reserve即消费，W/case-stage-ledger-20261031/budget_v3/model.py:227–232；新臂改成fill消费是明示不同合同，不可称完整原账户复刻。

## 6. 行业 active 的纯市场状态机与财务状态分开

唯一权威市场状态机：W/industry-mobile-stage-20261031/stage.py:10–50。
最小每观察输入：行业ID/day、adjusted close、原E0_valid/floor/episode、source segment、当天CP receipt/candidate/canonical receipt_id。完整暖历史推进；不读持仓、现金、盈亏、订单或个股成交。

转移次序：
1. receipt ID先记seen；重复ID不能升阶段。
2. E0 false、source/episode变化、或C≤旧mobile线：结束attempt，stage=0，撤销auth。同日fresh CP即使出现也不能重开。
3. 输入未知：action=unknown，清auth但保留attempt责任；不是从未首CP。
4. 无attempt且当日新CP：开probe（stage1），line=max(E0 floor,CP candidate)。
5. 已有attempt且旧线未破：line先max旧line/E0 floor；若新CP再max candidate，stage升2/3，stage3后新receipt替换auth。没有新CP但auth仍有效则继续。

W/universe-cp1-inputs-20261031/prepare.py:47–53说明refs.state及CP输入/数值为全暖历史；refs.receipts仅输出2025-07..2026-06，因此此次对2022身份用cached数值+全历史原trace重建，而不是拿窄收据表补零。

joint_v3.py:195–205把E0/市场end_attempt/fresh industryCP映射为budget.active。route:274在资金量检查前拒inactive。所以本合流省略的是一项真市场授权，不纯粹是容量。

但budget中的level、confirmed_unfunded、pool migration是财务状态，不能拿作alpha。joint_v3.py:284–300的现金底线、probe/confirmed资本、行业资本风险、账户风险、单股上限都是资金约束。该原文件有account3%/confirmed60%限制，后续历史账户适配器另有移除，不能未经确认把原文件每项当当前生效合同。shared_loss在原Budget:16为record_only，并未主动阻止新风险。

ACT20_BREAK：R/actual-risk-recovery-20261027/code/risk_policy.py:8–28，以实际账户NAV对该on-episode peak回撤≥20%暂停，持仓全清且市场breakout才恢复。market breakout虽市场可算，ACT本身依赖账户路径，不得按信号日推断或当新市场门。它不是泛称“熊市过滤”。

UNKNOWN差异：市场Stage会清auth；旧joint industry()未单独处理action=unknown，故不能把严格UNKNOWN诊断称原route逐情况复刻。本次2022/654启动日行业状态全已知，该差异不改变这些数量。

## 7. 当前许可上的精确边界，不是策略反事实

| 2022信号季 | active | 当前episode首CP前 | 同episode失败等待 | 行业E0_OFF |
|---|---:|---:|---:|---:|
| Q1 | 1147 | 657 | 53 | 18 |
| Q2 | 1043 | 430 | 17 | 17 |
| Q3 | 407 | 113 | 51 | 14 |
| Q4 | 658 | 358 | 26 | 22 |
| 全年 | 3255 | 1558 | 147 | 71 |

E0_OFF71全部是独立AB来源，不是event.Q违规放行。失败等待147中5条有独立AB的I角色close PASS，保持AB不动时剩142个既有许可受规则触及（Q1=51、Q2=17、Q3=48、Q4=26）。先前和当日持仓、队列、后续根、权益以及UNKNOWN会随实际策略重排，不能相减当新结果。

首次等待与失败等待都不能按日历年重置。分类来自全暖history中的当前E0 episode；未知边界不补为首次。当前episode从未receipt/probe与曾失败后无新的有效attempt是不同状态。

相关旧研究已存在：P/core_stock_selection_dmi_v1/experiment.py:38–59、P/selection_entry_diagnosis_v1/mobile_candidate_response_v1/reconstruct_domain.py:35–55已使用industry_active；P/early_sector_probe_boundary_v1/REPORT.md:34–53专门区分首次行业CP等待与失败。不是新发现或新alpha。其旧微试仓是冻结原账户剩余容量下的条件机会，不能移植其收益效应到此新消费者。

## 8. 仅提出一项后续机制假设，不执行或定阈值

行业失败门触及面太小，不能把它推成解决Q1的主方案。下一项可研究的差异是“跨I根的新保护锚证据”，而非提高PVR/G、要求当前UP、beta残差或再加M3总门。

诊断先行：对于每个有完整连续来源的I 0→1，保留前一已知失败I根的出生/最后有效保护floor、原E0确认pivot及证据日期；判断本次是否只是将floor重新设低，还是已有晚于失败日、能提高原生保护锚的确认。只标签，不先以收益挑阈值。

单一候选的明确方向：首次可识别启动保持现有fast；连续反复试仓不能只凭I关闭→重开自动获得全新资金资格，需新的原生保护锚推进证据才重置新钱授权。I持有/退出本身不改，AB独立许可暂不动。此处“原生保护锚推进”必须先冻结到底比较前根出生floor还是最后floor及如何处理新市场大周期，当前尚无足够依据选一个版本，因此仍是机制设计任务，不是可运行新公式。

与已否决UP区别：当前方向UP只是当下状态，本假设保留失败前跨根数值记忆和原生确认身份；与beta区别：不解释收益的共同因子，而检查保护锚是否真的新生。仍可能阻塞真正低位反转、提高追价/风险距离，且未必区分赢家，不能预称有效。

最小否证：若更低保护锚组与提高锚组同日同行业、原PVR/G与根首/复发层内无稳定差别；或正常反转/924启动系统性被拖迟；或主要损失来自首个根而非反复根，则停止，不能靠调数值阈值挽救。最终仍需同时过34/35%初层净胜率和盈利/亏损、右尾、完整UNKNOWN分母，而不是挑出一个35%子组。

## 9. 信号收盘可知与不能据此知道

可因果计算：当日原E0/G/I、fresh_up具体原因、当前与前根保护锚及身份（完整来源前缀）、event.Q及原reason、PVR分量/分数、行业E0/attempt/旧线/receipt、原生已消费市场前沿、当前历史first/failure分类。

不能由市场表得知：个股账户是否已flat、哪个epoch/receipt被该账户positive fill消费、ACT是否暂停、剩余行业/共享资金、获槽后的次OPEN/合法股数/成交，未来持有权益和执行终局。已有5031许可与消费记录只陈述原臂已发生路径，不授权把它当替代策略状态。

最小新增诊断字段：stock_I_root_id/root_start/known；prior_failed_root_id/failure_day/birth_floor/last_floor；current_E0_episode/confirmed_pivot_price/pivot_observation/confirmation_observation；G_fresh_up_reason_bits（E0_up/S21_up/S63_up/new_S21_frontier）；PVR_r/s/amount_ref/u/b/e/E；sector_E0_episode/attempt_id/old_mobile_line/receipt_id/formation_interval/current_episode_receipt_count/failure_count/unknown_count；account_consumption_status单独列，不混进市场信号。

静态1709池/行业映射、历史发布可得性和真实下单可成交性仍未被此审计证明为PIT。无新增经济运行。

## 10. 后续唯一出生底候选的启动否证与停止

上一节提出机制方向后，唯一主式被进一步固定为“当前完整已知I根的出生floor > 前一个完整已知I根的出生floor”。前根最后抬高floor只作描述，不作为另一候选择优。随后7案例全部654日由另一种连续状态段算法独立重建，根日期和前根日期完全一致，floor比较容差1e−14，未读任何经济label。

| 案例 | 当前I根 | 当前出生底 | 前根 | 前根出生底 | 前根末底 | 主式 |
|---|---|---:|---|---:|---:|---|
| 海能达 | 2024-09-19 | 20.119354 | 2024-08-30 | 21.074742 | 21.074742 | LOWER |
| 银之杰 | 2024-08-30 | 41.589681 | 2024-06-26 | 42.117469 | 42.117469 | LOWER |
| 捷捷微电 | 2026-01-05 | 186.767105 | 2025-05-08 | 179.969956 | 222.181022 | HIGHER |
| 江丰电子 | 2025-12-23 | 83.144936 | 2025-10-27 | 94.001895 | 94.001895 | LOWER |
| 珂玛科技 | 2025-12-10 | 50.257200 | 2025-11-11 | 52.003008 | 52.003008 | LOWER |
| 金海通 | 2025-11-06 | 123.628528 | 2025-09-08 | 99.900314 | 128.404398 | HIGHER |
| 源杰科技 | 2025-04-10 | 129.331190 | 2025-01-24 | 179.019892 | 179.961659 | LOWER |

以上是原共同adjusted价格坐标，不是当时raw报价。5/7最早信号所处根被HIGHER硬门拒绝，包含两只924案例。保AB独立只能说其原AB授权未被此新门直接取消，不表示fast/CP更早通路保留、队列不变或实际持有保住。依预定启动代价检查，这一主式不应进入经济试验，也不应转而选择前根末底、临时豁免或改尺度挽救。

排重范围：本项目、2026-10-29研究目录、2026-11-04项目，检索previous/prior root/epoch floor、birth/initial floor、higher low/support/pivot、跨根/前根/保护底/anchor reclaim。没有找到完全相同“相邻完整I根出生底更高”的已完成测试，但存在明确近邻，不构成新颖性证明：
- `/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/failure_no_progress/mechanism_review/CANDIDATE.md:25–59`：真实全股负现金两败后、支持抬高加新高的恢复；其REPORT.txt已因“支持不抬不等于无价格进展”、零股恢复不可达、作用域小而否决。当前主式不同于实际盈亏计败，但同属支持证据近邻。
- 同级 `mechanism_review/CANDIDATE_AUDIT.md:42–46`：原CP SEEK两次已确认repair低锚更高+局部突破，只恢复TRIAL的设计。
- P/selection_entry_diagnosis_v1/cp1_signal_mechanism_v1/cp_band_structure_case_audit_v1/price_rebuild_event_audit/REPORT.md:10–37：更高低点+突破+同日freshCP的成功/失败同形反例，明确停止。
- 同级结构信用卡 `structure_credit_card_v1/structure/REVIEW.md:75–81`：早已指出新E0根重新发风险许可会跨根连续失败；frontier+支持重启门是未采用的另一信号政策。

新增输出：`sector_attempt_anchor_first_milestones.csv`、`sector_attempt_anchor_startup_independent.csv`、`sector_attempt_anchor_case_QA.json`。这是停止候选的因果案例证据，不是新的收益回测或整类结构策略无效证明。
