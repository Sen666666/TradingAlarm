# G/S只读历史装载器，供接线前独立审查

本目录仅准备输入与映射。金融账户创建、金融事件、买卖意图、指标重算均为0。前缀固定2022-01-04—05与2025-07-01—02；没有执行SyntheticRunner、原SC/PVR或G/S策略。

`loader.py`为只读入口，`input-v2/<window>/MANIFEST.json`逐文件绑定实际SHA。`SOURCE_BINDINGS.json`保留读取的原来源SHA；原文件未写入。输入冻结的1709身份、90行业及真NA均保留。`SOURCE_FREEZE.json`和`DELIVERABLE_SHA256.json`由最终收尾脚本生成。

## 可直接检查的接口

- `HistoricalInputs.bootstrap()`返回已审182份种子中的本窗91份完整F1 State/Source、原scope、policy_scope、scope observation sequence、原ordinal和proof_history。返回副本，不重放、不重命名State.scope。
- `initial_financial_state_spec()`仅返回新账合同说明：1m、零仓/订单/意图/损耗/消费/退出锁/应收、filled_trials=0、K=[]，没有创建账户。已成熟市场节点不算实际试仓或K激活。
- `event(day, ACTION/PAYMENT/OPEN/CLOSE)`只返回输入。OPEN的I/G1/CP1/保护取前一研究收盘；当前日只取除权坐标factor及原日线成交代理数据。后者读取完整当日OHLC/volume，**不认证真实开盘可得性**。CLOSE读当日已存原数值，不执行决策。
- `stock()`保留原I daily event与持续I target的区别；canonical receipt保留原receipt_id、scale_id、source_segment、原episode hash、形成区间、确认ordinal及完整原记录。原E0结构ID和I的(bool target,segment)分列，不编造新账epoch计数，不把bootstrap旧CP1重发为fresh。
- `priority(day, ids)`复用冻结PVR_SLOT1 `priority_plan`原函数AST，源码SHA硬核验。输入域是调用者给定的唯一股票集合；NA原槽位不动，ready按PVR降序、原H1/code同分；core/mobile同股票共用槽位，role key为(priority_rank,role!=core)。默认全1709是**输入fixture域**，不是原账户真实意图域。真实目标/角色/账户筛选尚未执行，因此不冒称已确定未来订单排序。输入可提供完整H1/PVR/NA及调用所需键，未来接线必须在实际候选域冻结一次，不能开盘重排。
- `payments_due(at)`仅返回截至原aware cursor声明已到支付时点的来源条款。未来账户仍须查自己的未付entitlement、只支付一次；来源事件不自动创建现金或红利权益。未知支付日保持None、应收不融资；本前缀9项支付日均未知。

## 股票Q与行业授权分解

保留：股票原暖机就绪、I方向、core的原I daily buy事件、原股票H1当日新鲜度、原固定选择/身份/市值>100亿/行业映射、原历史venue及availability。`retained_stock_Q`是不含新资本授权的必要股票检查，`retained_core_event_Q`另加原I daily event；mobile还需要fresh canonical CP1。

替代：旧common_ready中行业ready分量、sector_observed_today、sector_rs_ready_fresh、sector_up，以及旧budget/D1行业active/episode/attempt硬授权。它们逐项记录为legacy归因，**不设成True**，不继续作新F1行业许可的隐藏否决。新F1 G/S用途、ACT严格证明时钟与冻结V2应由后续真实策略调度使用。没有把原整项Q一键改True。T0纯股票资格函数的实际调用已用于映射回归。

as-of Facts.row沿用原最后已知状态：例如1/4实际当日I_ready1434，而as-of含2个旧就绪值为1436；7/1当日1636、as-of含3个旧值1639。缺行/陈旧值与同日H1、原市场可执行观察掩码分开，不把旧ready称当日可成交。

## 权息与坐标

实际原值：2025-07-02 688608.SH，每旧股现金1.20元，送转ratio1.40。OPEN保护仍取7/1收盘原线；用7/2实际price factor换为raw坐标。price factor包含现金除权效应，**不是股数乘数**。原规则现金净额80%研究代理、送转可卖日未知沿下一源交易日代理均保留在条款/原protocol内，未猜支付日。新账7/1前无持股权益，7/2除权后新买不补领旧分红。

原处理顺序须由未来金融接线复用：settle_due→除权旧库存现金应收→送转→已声明支付→OPEN→CLOSE决策；本目录只提供相应输入。

`check_action_support(event,layer_quantities)`明确拒绝未知分类或分层送转结果非整数。无真实层数量时只报conditional，不把UNKNOWN归零。每张STAR新CP1订单最低200、200以上step1；持仓不能令下一新单最低1。同一已授权订单的50股partial余量独立保留，不重发receipt。

## 验收与边界

最终验收见`validation-002/`、`validation-extra-003/`。基于真实已存原数值的实体Parquet前缀，不只内存切片：两日完整/截断/未来扰动、新进程读取核同；另首日实体截断排除次日真实行；当日收盘信号扰动不影响OPEN；错误SHA拒绝。原文件fixture覆盖000001、300308、688608两窗各两日原facts/CP1/PVR逐值。

这些测试证明输入映射与因果边界，不证明策略表现、资金能力、实时交易可用性或新历史金融接线已完成。

仍需后续单独授权/验收：R4目前对receipt source仍为fixture guard；须用本包真实canonical/source/结构明确绑定，不能伪装fixture。完整历史收盘调度、真实账户批次/公司行为/支付回调、ACT scoped proof导入及实际候选域priority freeze仍未连接。R4对一般零股、多层腾挪估费、多单S→G子集等已列UnsupportedOperation应保留；本包没有绕过它们。不得从本报告推定金融前缀已获准。

保留的工程失败：`input-v1/INTERRUPTED.json`记录重复解压H1 NPZ；`validation-extra-001/ERROR.json`记录扰动fixture的pandas dtype异常。均无账户事件；原始正确输入/旧策略/R4未改。
