# 结构与每股风险：真实接口边界

本件仅审原源码、协议和既有 B 持有线预卡；没有导入或执行 CP/I 模型、Account、合成路径、回测或参数试验。UPG-1固定阶段、1R/2R、任意新增储备均不在本合同内。这里没有选择新仓位阈值或宣称收益改善。

## 接口结论

真实 CP receipt 必须有新局部价格 frontier 推进，不能把它称为同价反复发证；但 **新 receipt 不等于已生效保护线变高，也不等于实际每股风险下降**。candidate 只是按旧冻结波动尺度从当日价格折回的候选。动态扩仓能读取的是：原退出判据通过之后合法生效的实际保护线、真实持股/未完成订单、当时可用价格和原费用约束；不能将 credit、receipt次数、candidate名称直接换成新增资金。

原流动性接口是成交可行性代理，含未来执行日完整日线量/H/L，不是已校准的事前退出承载模型。只复用原参与率并不能使新的总仓位可行域自动获得该保证。

## CP 字段的精确定义

原 `continuous-protection-lines-20261028/code/model.py`：

| 字段 | 源行与意义 | 能否直接增加风险预算 |
|---|---|---|
| 当前 `r/s/z` | 22–24：r为adjusted收盘对数收益；s为前63个绝对收益的中位数×1.4826（shift后，不含当前），z有原最小尺度 | 不能。它是原波动尺度输入，并非可损失金额 |
| `B/u/v/m` | 23–24：B为前21个amount中位数；u=tanh(r/s)，v=tanh(log(amount/B))，m=1+0.5×abs(u)×v | 不能。m是新上涨位移的量价权重，不是资金流净额或实盘胜率 |
| `anchor` | 35–38、49：启动、负native event重置、SEEK新低或上次receipt消耗后的log-close起点 | 不能。不是持仓均价、亏损后的补仓线，也不保证为全campaign低点 |
| `frontier` | 40–43：本段anchor以来被接受的最高log close；只有严格新高增量fresh才累credit | 可证明该局部段有新价格推进，不能证明突破整个交易链旧高 |
| `credit` | 42–44：只累计新frontier增量×当时m；回到旧frontier以下不再赚同一段credit | 不能当预算/已实现收益/止损抵押。它只参与receipt资格 |
| `used_scale` / 输出`scale` | 36、38、46–50：anchor时冻结的z，直到本次receipt使用；确认日当前z只成为next_scale | 不能把当前波动下降事后灌进该receipt。不是每个CLOSE自动重算的剩余风险 |
| `receipt` | 44：fresh>0，且displacement与credit同时达到sqrt(5)×冻结scale | 是新局部授权证据；不是固定仓位档位或每次2%资金权利 |
| `candidate` | 45：C_t×exp(−sqrt(21)×used_scale)，与C同adjusted坐标 | 只有实际接受后高于有效旧线，才可能改变保护距离。不是确认pivot/实际低点，不是能以该价成交的保证 |
| `next_*` | 48–50：receipt后anchor/frontier重置到本次log close，credit清零，scale更新为当前z | 不是另一次证据，不能把本次旧尺度与next尺度各算一次授权 |

常被忽略的输入映射：实际股票 CP 的 `case-stock-cp1-warmup/generate.py:23–27` 把 **facts.i_target** 映射为模型名字叫 `e0_valid` 的字段；`e0_down`来自原native events.event==−1。不能按字段名字误认成另一个已重算的E0策略。I仍有效时也可能出现负event，重置局部CP anchor；之后在整个campaign旧高以下出现新CP是原算法允许的行为，不是同一frontier增量被重复使用。

`trace.py:45–57`进一步绑定canonical series、source segment、确认日、anchor observation、advance observation IDs及evidence signature，断言advance未复用、区间在anchor/上次receipt之后。别名/重复receipt去重见59–65。同一receipt/同一确认观察反复查询是重复证据；不同合法receipt即使价格低于campaign旧高，也不能叫重复凭证。它仍可能提供不了新的风险改善。

## I floor、已生效 mobile floor 与时钟

I floor来自真实市场结构链：`pv-strength-b5/code/policy.py:99–113`先判断旧floor失效，正native event接受canonical confirmed pivot并max更新结构线；`cache.py:27–32`调用 `policies_g1.project(...,'G1_I')`，将其target/floor存为i_target/i_floor。

G1_I active时，`policies_g1.py:20–24`先按 **adjusted CLOSE≤旧I floor** 或基础结构失效退出，未触发才ratchet；30禁止本观察退出后立即重入。`J:225–229`据I_target0全股请求退出。因此CORE已有上游I线间接止损，不能新增同CLOSE对新ratchet后I线的重复硬止损来“补缺口”。`J:231–234` last_core_line是同I floor的最后决策已知参考，下一OPEN同步不能读取该日未来CLOSE。

mobile的原有效线是逐真实层的路径状态，不是总取最近candidate：`J:235–240`先跳过已在sell_layers的层，再用当日CLOSE检查该层旧floor；触发即退出，未触发才max(旧floor,当时I floor,当日receipt的candidate)。只有此分支接受后的线才可进入下一次风险视图。本日新线不倒灌重判本日旧线退出，不能用较低新candidate撤销旧退出。新买mobile初始线仍是`J:255`的max(I,本次candidate)。

按每股风险变化动态确定总目标，需要保留各批真实生效线或明确统一线的法律效力；仅在卡上写一个新共同floor，却让原退出还按各层不同floor执行，会使预算与执行不匹配。统一线若改变CORE的I退出或原mobile线，属于另一个持有/退出机制，不是纯资金计算。

## 哪些变化可用，哪些不能冒充风险改善

| 当时可见事实 | 可支持的判断 | 必须拒绝的跳步 |
|---|---|---|
| 原I仍有效、实际接受的I floor提高 | 在同一时点价格下重新算原持仓的参考保护距离；保留旧线先检查顺序 | 把I floor提高自动等同赢家已验证、利润变成可用现金 |
| fresh CP candidate严格高于该批旧线及I项，且旧线未触发 | 新line确实改变这批后续有效保护；可供同域风险约束重新评估 | 每个CP固定加份；若candidate没抬实际线仍记“释放风险” |
| candidate提高，但市场价/次OPEN买价涨得更快 | 要重算当前完整风险与新增每股风险；可能没有任何容量改善 | 仅看line上移金额，不看价格、持股总量及原费用 |
| 新CP在旧高以下、candidate≤已生效floor | 有新的局部价格证据；风险几何可能完全不变 | 把新receipt当全局结构突破或资金扩张充分条件 |
| 原冻结scale与next_scale不同 | 本receipt仍用used_scale；下一receipt按其未来合法区间处理 | 用确认日更小尺度回写本次candidate、双算两个scale |
| next OPEN跳涨或跌到线下 | 原preview可缩量/拒绝，保持冻结最高股数/金额和真实quote合同 | 为维持目标回补超出冻结合同的数量；用close作假买价；线下分母取0后无限放大 |
| EXIT_PENDING或cancel ACK未完 | 保留剩余真实库存、未完成责任和预留；同股禁止新增 | 以mark≤floor导致名义距离0就当成退出风险消失或现金释放 |
| 同一逻辑订单partial fill | 按实际已买/剩余承诺计算总目标缺口，复用原费用累计 | 将partial callback当多个CP/多次新授权，重复最低额或漏掉pending承诺 |

每股参考距离不是足够的q公式。即使允许求“最大合法q”，其可行域也必须同时消费整个sid现有库存/生效保护、同股承诺、原sector/probe名义风险、资本/现金/费用/个股总额、合法整手与时钟。原all-in参考包含双边费用和假定线价卖出的5bp，实际费用有最低额及partial累计，不能化成一个恒定的每股费再无限线性外推。旧持仓已支付买费也不能在每次评估重新付一次。此处不新定预算水平、不以浮盈设任意储备、不引入1R/2R闸门。

## 流动性与实际执行：可复用和缺失部分

真实源 `temperature-sizing-20261026/code/fast_market.py:45–66`：过去20个正量观察不足则无window；60的容量为 **min(过去20正量平均volume×原1%参与率，执行日完整volume)**，59还用执行日H/L flat-bar代理拒绝买卖。原economic-protocol确认为participation_rate=.01、A股sellable lag=1、settlement lag=0、bonus lag=1、OPEN±5bp。

`J:319–322`明确在所有funding完成后才查询这些execution proxies。新增授信不得窥视次日全天H/L、volume、最终FillWindow容量；这些仍只决定原实际fill。若主设计抽取前一CLOSE已知20正量与原参与率作为事前历史参与限额，须保存cutoff、源量单位、CA单位桥、窗口缺失状态，并明确它是**未校准的历史限额provider**；不代表原系统已有前瞻退出容量/多日冲击成本模型，不保证未来可卖。没有此provider的正式参数/缺失合同，就不能宣称动态仓位系统已完整可编码且有效。

`sector_account.py:688–744`处理真实可负担数量、buy minimum与continuing partial fill_step；746–797只卖sellable_at已到的批次并受真实容量/整数约束。J opening先原退出、结算/sync后新增reserve；exit未清同股不新买。结构退出责任直到实际fill，买单预留直到cancel ACK才能释放；原risk0不是资金释放。split必须同步真实股数、每股线、pending cap/remaining、计量单位，货币预留不凭拆股扩大，原fee schedule累计最低额不按虚拟层重复收取。股息paydate未知仍为应收，不进available。

## 与 B/mobile_floor_raise_holding_precard_v1 的冲突检查

已读其 `PRECARD.txt`，并只绑定原文件SHA，不修改。B仅针对已持有且无该层退出责任的mobile后续receipt：F_new=max(F_prev,I_floor,min(candidate,EMA20))；不改初始入场、新买单floor、CORE、资金公式、ACT或I结构退出。EMA合同尚未冻结，未获数值GO。

1. B可能使旧mobile线低于原CP max，但新买批仍按原max(I,candidate)起线；v2不能把同股所有shares都套到较高的新批线，或用原路径未来floor作候选自身有效线。
2. B变宽通常提高同一价格下旧层风险占用；若v2动态资金读floor，就有直接资金反馈。不能同时说“只多拿几天、资金不变”，也不能从旧原账预算路径静态扣加得到新组合收益。
3. 初始floor/I floor已主导、candidate不高于实际旧线、ACT/I先退出、已有pending层，B不作用；这些也不能被v2当成新释放风险的CP分支。
4. 若主设计本轮保原holding规则，B保持独立未启用；若将来叠加，必须另列v2原holding与B独立作用的合同/消融。现阶段不算EMA、不混写旧B文件、不把B预卡当已有效持有模型。
5. CP1_add_protection标签本身不说明后续CP提线导致了退出；它可能由初始线、I ratchet或后续CP主导。新机制不能凭最终标签挑“线太紧”交易或以未来峰值充当保护改善。

本件没有收益/覆盖数值或动态规模试验。还缺的是主设计对总风险口径、因果流动性provider的参数/缺失状态、保护线异质批次与最大q可行域的明确合同；并非缺新的CP/I模型或新的金融账引擎。
