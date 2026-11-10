# V4：V3持有上下文＋原CP公式＋每up一次试探的最小信号候选

本轮只做信号计算、逻辑状态与条件表，不导入/运行Account、不生成数量/现金/收益。V2/V3封存。固定案例：盈新2022-01、海能达2024-01和2024-09至11-27；均从原完整source前缀计算后截展示。没有新价格阈值或资金参数。

## 1 三条通道，明确CP输入版本

1. 市场结构沿已冻结V3：负E0确认峰R并撤mature、不清P；新正E0启动up周期；P旧线先检后max，破旧P发结构退出；同代P不降。I_hold表示市场持有上下文，不等于实际有仓。
2. CP*逐字使用原CP.model.calculate公式，输入close/amount/segment_id与原e0_down；将原e0_valid=旧I_target替为V3已知I_hold，i_floor替为V3结构P。I_expand绝不能作CP valid。仅源未准备的I_hold未知映explicit cp_valid=False并记录I_NOT_PREPARED；已准备后未知、缺价/amount或源不可比不得伪造可交易事件，应标UNKNOWN/阻止授权，不能用未来补值。保留旧CP作对照，逐项报告CP*差异，不假称旧缓存已等价。
3. 已持仓层保护是独立账本：原CORE沿原I硬退出；原MOBILE先比较C与t−1已知旧floor，命中即提出原保护退出，未命中才max(oldfloor,有效I_floor,当日CP*candidate)。负E0的CP内部reset、mature撤销都不清/降低已存floor，不撤旧pending exit。此次不建持仓账，只给原实际层注释与伪代码合同；不能称新持仓/退出路径已被验证。

CP市场receipt_consumed只是发布收据后重锚，完全不等于账户用过、更不等于试探已成交。

## 2 本轮once的明确语义

**主规格采用一次成功发行的permission/request-event，而不是一次成交。** 信号引擎原子发行唯一request后永久消费本up试探机会；后续资金拒绝、零成交/跳空取消也不返还。这样不使用未来成交改写市场信号，但有明确错失代价。本轮不声称实现“一次有效成交试仓”；若目标改为一次成功reservation/fill，必须另接真实ACK反馈，不能拿原账成交替新路径消费。

up_credit_key=(version,sid,source_segment,原正E0确认事件ID)。每个合法原正event新建一个未用信用，旧信用作废不累积；持仓generation变化、CP锚重置、同日调用次数、旧订单取消都不新发up信用。负event撤成熟并关闭旧信用，等待下一真实正event。

CP*每个确认日最多一个receipt，用key=(CP*_version,sid,source_segment,confirmed_CLOSE_day)，不借旧canonical ID冒名；若恰等旧CP，注释其旧ID而不混用。seen_CP与up_once分两本账。被市场拒绝的过期CP不存成以后可补用凭证；同key重放返回同decision/intent_id或REPLAY，无第二份权限。

## 3 信号控制器的外部输入与唯一purpose

输入除市场facts外必须有当时已知ExecutionContext：has_position、pending_buy、pending_exit、cancel_ack_pending、源/保护有效性。缺失状态=UNKNOWN，不当flat。旧原账context只能列作原路径条件注释，不当新路径实际状态。

先按原规则提出保护/结构/流动性退出。exit_required_today（包括本收盘旧P已破后又出现新代up）、pending_exit（包括部分卖出/无法成交）、pending_buy或cancel_ack_pending未清时不发行新买request；不只检查t−1的外部pending。不假定同开盘卖款已回流或T+1仓可售。市场新up/confirm可成立，但不能消除订单责任。

在锁均已知清楚、当前CP*为新receipt、I_hold真、up_after_R真时，至多发行一项：

```
if has_position and I_expand is True:
    purpose=MATURE_CP_ADD
    consume CP key
    settle/burn this up's unused probe opportunity as well
elif up_credit is UNUSED:
    purpose=START_CP_PROBE  # flat或已持有时均只能用一次
    consume CP key AND up_credit atomically
else:
    BLOCK  # 已空仓不能把旧mature当无限重入权
```

同日正E0、mature和CP并存：有仓优先MATURE_CP_ADD并结清probe；无仓只能START_CP_PROBE。仅市场mature出现、尚无CP或锁挡发行时不消费信用，之后未发行过任何purpose而退回START仍可使用本up唯一probe；“不能补领”专指已发行mature并结清信用后的fallback，不另加mature_seen价格门。同CP不分成CORE+MOBILE两张单，I+CP也不作为两份独立alpha。新的CP probe是受原MOBILE/add保护的用途标签，不映成原CORE的I-only宽线持有；旧CORE持仓不改。原资金pool=probe/confirmed另属资金层，不在本轮重定义。

permission issuance是一次原子操作，两个role调用不得分别先消费后汇总。验证与preview无副作用；所有precheck通过后同一事务claim CP/up并写outbox唯一intent_id。真实下单若重试用相同intent ID，不创建新资金申请。原Budget.request的consume写在部分资金检查之前，因此未来接线不能假定现接口天然支持这个事务，本轮不改它。

## 4 每个收盘及下一执行点

1. 读t−1持仓floor/pending状态；用本日已知C先提保护/结构退出。原T+1/流动性/跳空风险继续存在，信号退出不是成交。
2. 登记本日原E0 pivot一次；执行V3旧P优先、down撤mature/新up信用与P更新。两代同日事件分别保存。
3. 原CP* kernel按本日完整已知输入更新一次；down reset SEEK只改market形成状态，不清已有层floor。CP新candidate只有发布后可用于max抬线，不回头遮本日旧线已触发退出。
4. 生成唯一CP permission；exit/order锁优先。原无CP的CORE入口不在新候选发单，必须明列这种变化，不能称保留所有原买入。
5. 次交易可执行点只重验真实已知报价/保护/订单责任；若报价已在保护线或无法取得可执行报价则拒绝/取消，不假定看最终OPEN后仍按同OPEN成交。上跳造成数量/风险不合法交原资金/数量层，不在本轮造数量。拒单不回滚CP市场锚，也不返本规格已发行once机会。

## 5 本轮可运行的条件演绎，不造仓位

CP*与V3 fullprefix重算只生成市场facts。授权FSM另外在两种**固定条件分支**演绎：HELD（已知有仓且本日原保护/ACT等退出检查已通过、无外部订单锁）与FLAT（已知空仓且无锁）。HELD是条件假设，本轮没有层账验证其退出安全，不能称原持仓已通过检查。每支只更新CP防重放/up信用，不更新股数/现金/成交；这是条件真值表，不是两条交易账户。CP与两个授权分支均从完整source前缀消费/递推后再截97日，不在展示起点把已用信用重置UNUSED。它们分别显示有仓继续层与空仓入场的条件；不将PROBE输出自动变成held。另列旧原路径has_position/pending注释，不混入新分支。

逐CP*列day/C、E0/up/R/mature、CP形成anchor/scale/frontier/credit/candidate、旧CP是否存在/ID、两条件分支purpose/reason/credit前后，以及原CORE/MOBILE intent/成交日期的差异。新CP为29旧凭证母体之外也须列出；没有新CP也列原CORE意图。重点盈新1/6—1/26、海1月无旧CP与9/19—11/27；保留全部母体，不挑成功事件。

至少给同receipt重放、同日up+mature+CP唯一purpose、本日旧exit及未ACK新up、零成交不返信用、已发行mature后跌回不能补领probe、仅mature未发行时不误烧credit、CPreset不清旧floor、flat不能伪ADD的纸面/最小逻辑检查。不做账户/价格参数扫描。原G1/PVR/行业路由只作旧路径注释，本轮不替新信号声称已获其资金许可。

## 6 能力边界

V3 mature与CP*均依赖同一价格上涨。CP有新frontier与量价credit，不等于毫无新进展，但不是独立统计证明；同一CP只能一个意图。每次新up仍可新试探，V4不会保证过滤真假趋势；盈新1/24真突破后失败仍可能被允许。若首permission未成交，FLAT分支会在同up耗尽后等新up，可能漏连续赢家；需直接报告，不按样例回滚额度。此为本规格语义代价，不包装成已获正期望。
