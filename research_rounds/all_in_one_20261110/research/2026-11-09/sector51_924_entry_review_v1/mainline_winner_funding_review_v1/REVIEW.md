# 最小 A 资金竞争合同独立审查

状态：合同层可实现；不是策略实现 PASS，不是完整回放授权。仅静态读源码和原已保存 JSON。未 import 任一策略、Data，未运行 history，未改冻结策略、旧设计封存或原输出。

## 结论与最小选择

采用父级确定的最小 A：P0 与每个新 MATURE SEED 退让子集均使用原 M7 自然只读投影，独立重算该集合的原 D/X/T、sector floor、receiver 排斥和原买卖排序。比较逐健康 lot 的 y<=y0 与逐 ADD/EVENT 的 q>=q0；失败只按完整原请求排名末位移除新 MATURE SEED。不得给 donor 主动加帽、重排、裁剪、指定最小供资前缀，不为 A 另开优先队列，不给 RESIDUAL 下限。

该版本是一个资金竞争许可因子：它只选择原算法在有限嵌套请求集合上的自然结果，不引入收益优化、行业准入、利润覆盖或轮风险限额。它可能保守地退让一个本可用另一组合容纳的 seed，这是固定顺序代价。

## 有限性证明

在同一阶段/同一只读快照，设新种子固定优先序为 n1...nm（高到低）。只枚举 Rk=B+{n1...n(m-k)}，k=0...m。P0为R_m自然投影，所有影子、候选使用各自原参考目标和各自原receiver/donor计划。每次失败k增加1，最多m次删除、m+1个不同候选（影子只算一次复用）；最后R_m=P0，两个比较逐项相等，无需豁免。无约束绑定即原full，N为空即原P0，输出整份原分支而非订单裁剪结果。

前提是原快照已通过原认证，可形成投影。若原unknown/公司行动桥/元数据触发atomic block，应原样阻断；有限性不是“总能交易”，不能跳过原block来选择空N。

## CLOSE与OPEN合同必须分开的量

1. 原授权上限：每枝原 _ref_q/planned_q/econ_q、transfer_plan.max_q、frozen_lot_qty、close_sector_floor。
2. 只读自然投影q/y：用于比较，不能反过来成为新增执行cap。
3. 最终撮合fill：只按原执行器提交/记账，后验报告偏离。

CLOSE dry-run没买到，不意味着OPEN永远不能买。若价格/可融资额改善，原M7可以在原_ref_q内成交。因此不得把CLOSE现金投影q当OPEN新增硬上限。中途退让N会改变T及receiver排斥，所有允许OPEN采用的嵌套分支必须各自提前保存完整CLOSE合法计划；候选簿可以是带branch_id的并集，但不得跨枝取max_q、最低floor、受益者上限或donor rank拼贴。_donor_sectors必须逐枝，不能拿并集屏蔽RESIDUAL。若只冻结full和shadow两枝，则OPEN只能二选一，不能声称支持未冻结的中间枝。

## 源码相位和前看边界

- mainline_candidate_v7_demand_capped/engine.py:10-29,43-89：capped_water、独立MATURE demand、D/K/U/X/T/envelope。删N后必须重新调用等价原公式，不能沿用full targets。
- mainline_candidate_v4_known_sector_fix_v2/engine.py:142-213：EVENT→MATURE→RESIDUAL排序、demand、原筹资。demand仅EVENT/MATURE，RESIDUAL不发动筹资。
- 同文件117-124：RESIDUAL若位于该枝_donor_sectors，则reference cap为0。不能把候选并集当实际donor sector集合。
- mainline_candidate_v3_core_reference/engine.py:148-188,297-314（受M4/M5最小hook继承）：先execute_transfers，再按原rank预约买入；donor逐lot floor=max(close_sector_floor,fixed_open)，数量受本枝max_q、T+1、frozen_qty及整手规则。
- mainline_candidate_v5_expansion_competition/engine.py:12-32,54-64：角色、M5 donor tier、EXPANSION部分卖量；角色不得改。
- mainline_candidate_v1/engine.py:124-139：info_open在融资之前确认information_pending。必须先在只读副本完成OPEN可知条件下的预测保护/桥和info_open，再计算共同预测H_open；CLOSE已确认和本OPEN新确认应分别记来源。不能因CLOSE未H遗漏OPEN新H。
- joint51_candidate_v9_facts/engine.py:98-108,116-144：数量/费率、nav/net/cpvalid和实质OPEN preflight均不需要当日H/L/volume。
- mainline_candidate_v4_known_sector_fix_v2/engine.py:104-124；M3 noncash/demand/transfer：OPEN只消费raw_open、factor/来源、前晚r.capacity/参考证据、dated规则。capacity虽在Data中按计算日20日raw_volume计算，但请求在CLOSE冻结；不得改用cap[OPEN日]。
- 不得调用classify_reference(OPEN日)来“重新”判H/目标，因为它读当日M/E/stock/I/CP/raw_close。OPEN只用前夜冻结证据+OPEN报价/桥/当次info_open。
- mainline_candidate_v1/engine.py:94-104：scan_targets读取当日raw_close作诊断。不得把这个诊断反馈为新H/选N依据。原实质OPEN gate只验open/factor/来源/桥。
- mainline_m7_november_boundary_design_v4/engine.py:134-148,163-179：ST no_fill明确读当日完整OHLC，buy_nofill在完整预约循环之后才发生，donor/强制退出也有原位no_fill。不能提前用它挑N或缩donor；不能利用事后fill现金重排receiver。本研究只承诺OPEN可知条件的预测不挤出，最终q/y可能偏离，单独审计。原93日EXECUTION_BOUNDARY_LOG中BUY_NO_FILL/DONOR_NO_FILL/SELL_NO_FILL均0，仅说明未触发，不表示边界不存在。既有loader/价格认证非PIT限制亦保留。

## 原整数/现金残余：保留而非偷偷修复

原M7按desired筹资，后面经济SEED不可拆，可能留下无法花出的储备外现金。P0要读取完整原greedy投影，不可把demand想买量当q0，也不能新增“清掉无谓donor”的优化规则。

只读原 mainline_m7_cash_batch_design_v6/once_20260630 输出验证：
- 2024-11-07：OPEN desired 583,732.3391210841110，初始缺口534,036.29520241454625，筹资533,037.6574500207000，仍缺998.63775239384625。000700.SZ EVENT的1000股成本7,609.287403580000，最终因cash_reserve拒绝，储备外只余6,610.649651186153750。全部实际买款576,123.0517175041110。该日M_actual_buy_cost=0不是“没买”，只是该日志仅算M==1。
- 2024-12-13：OPEN desired452,673.4699917701820，缺口406,612.30536695084760，筹资402,554.1257415408475，仍缺4,058.17962541000010。600050.SH MATURE 1400股成本7,429.185859811000而未成交，储备外余3,371.006234400999900。

来源：TRANSFERS.json（TRANSFER_CASH/RECEIVER_FUNDING）、CANDIDATES.json（相应OPEN拒单）、ORDERS.json（实际买款）、EXECUTION_BOUNDARY_LOG.json。这些证明desired与最终整数买入有差异；不能据此认定所有余款都是本可避免的销售。

合成边界：若原无N影子本会卖H=100却无法买ADD（q0=0），新种子以同样卖量使用原剩余现金，可通过字面规则。它不增加相对原M7的H卖量。这是最小A的限制，不能宣称每笔受准卖款均实际支持A。若要消除该行为，应先做独立执行修正对照，不纳入本次因子。

## 尚须落实的执行接口

- 新种子退让必须保留原身份、signal_day、event_id、nav0/budget/origin。不能从pending删除后无声丢失新尝试。原ticket规则只接受capital-only cap失败，需要明确资金竞争拒绝如何接入原等待/False取消/unknown暂停生命周期；不得伪造REFERENCE_CAP。该接口是本因子必要状态桥，不是新增期限或准入。
- 强制退出前缀也有ST no_fill，不能先实际运行含整日OHLC的exit_open，再把其现金/存量/info_open/H输出用于选N。选择用OPEN可知条件预测前缀，真实原前缀与已选分支再按原模型执行；原后验退出失败造成的实际H/现金/q/y偏离仅审计，不回流。真正已观察到的实时回执可用，但历史全日OHLC推断不是该回执。
- 保留原preflight targets。不能删N躲开来源/桥/unknown安全认证。
- 原强制保护退出独立先行，不记作可选融资y，不受H比较阻挡。各选择情景必须使用同一OPEN可知的预测保护后快照与共同H，不可重复记入卖款或用分支交易后的净利重判H。
- 冻结CLOSE上限与OPEN预测下限都按分支身份保存。不能先卖再临时选枝。最终只执行所选分支一次，CP consumed、ticket结果、EVENT spent仅真实一次；原EVENT priority_attempted由真实OPEN尝试规则决定，不能简化成只有fill才更新。
- 影子不污染active/archive共同引用、cash/claims、proof、events、pending或日志；新增分支簿/审计字段纳入原atomic snapshot/rollback。真实执行失败沿原处理，不以后见事实重新选枝。
- 保证范围为计划量，实际fill需报告偏离及原因，不通过新quantity cap把预测约束强制写入原执行器。

## 合同层原型验证范围

contract_selector.py只接收已给定的各分支自然q/y、固定N顺序和H/A集合，返回首个通过的原分支对象。它不产生真实M7投影、不读取行情、无策略/Data import、不做历史，不证明上游投影的时间正确性。独立断言覆盖零N=P0、逐lot/逐receiver、RESIDUAL无下限、未知不增加许可、固定末位删除、首个通过即返回、原full保真、禁止分支重排/裁剪、有限性和无未来字段。

审查意见：可以冻结最小A合同后进入独立接口/合成实现审查；现阶段不能据此宣称真实M7接口已实现、最终成交双约束保证、或收益改善。

## 附录复核

已读 EXECUTION_FREEZE_ADDENDUM.md / EXECUTION_FREEZE_FIELDS.json：最小A、独立完整分支、bar_q与q_hat分开、CLOSE不通过枝不在OPEN复活、共同H均与本审查一致。已及时指出“实际强制退出prefix可能已读取OHLC”的剩余相位问题，须以上文条件预测prefix修订优先。原型新增CLOSE不通过枝不得OPEN复活断言；总计19项。附录本身仍未实现，不能与合同选择器PASS混为真实策略实现PASS。
