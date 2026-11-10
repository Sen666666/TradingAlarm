# SRP-v2：结构—执行风险分配器接口，授权政策尚未识别

**状态：探索，未定稿，UNIDENTIFIED。** UPG-1的2/5/10%成熟目标、固定两次升级、1R/2R、6%全户帽、2%GAP储备全部不沿用。旧文件不改。本轮只读代码/既有证据和纸面公式；0模型、0账户、0回测、0参数/数值路径试验。以下提供可编码的分配器接口，不把缺少经济依据的授权政策伪装成完整可交易算法。

## 1. 核心可证伪假说及明确边界

同一机会只有一笔小的**参考风险本金B_k**；不因CP个数、持仓盈利、金融epoch、pool迁移或所谓成熟状态倍增。首笔可以用满这笔小本金，后续没有次数/名义仓位梯度：只有未用余额或既有层真实生效线推进使本金参考风险下降，才可能容纳新层。fresh CP是一次合法结构申请，不是另一份金额券。

这允许在条件反复满足时出现任意多次、每次有限的扩张，但**不保证每条健康趋势、每张CP或每个最小交易单位都可加仓**。特别是没有提线/没有可退出容量时，价格上涨本身并不创造预算。它不是新原理，属于旧G/保护释放再用风险近邻；旧G强窗明显损害参与的证据保留。

本最小版本选择**逐层正部本金参考风险**，不允许旧层负成本缺口抵押新风险；旧层保护超过成本后风险止于0，继续提线不再释放该层参考额度。不能为凑出可交易股数暗换成有符号负风险。该选择可能限制持续赢家扩张，是待否证代价。

## 2. 原代码已经知道什么，不能重复命名成新证据

| 原信息 | 精确来源 | 已有含义与缺口 |
|---|---|---|
| I持有/进入状态 | `native-I-cache-interface-20261031/cache.py:25–32` → `b5-g1-20261025/code/policies_g1.py:20–34` | E0 shadow与grade/warm/fresh消费生成I；active先检查旧I floor/结构失效，后ratchet，I_target=False由J225–229退出。持续I=True不是新资金证明。 |
| stock CP新进展 | `continuous-protection-lines-20261028/code/model.py:35–49`；`cp1-evidence-trace-20261031/trace.py:43–57` | 当前价格严格越局部已消费frontier才积新位移；位移和金额调制credit达到冻结scale条件才receipt。是真新局部推进，非同价重复消费；但重锚/下降重置后可在旧大周期高点下再出CP。 |
| CP保护候选 | 原CP model45 | `candidate=C·exp(−sqrt(21)·used_scale)`，scale在原anchor冻结；新receipt不保证candidate高于旧生效线，也不保证新买价到线更近。credit不是现金或可多次用的风险本金。 |
| 实际层退出 | J225–240 | CORE原I退出、mobile原旧CP线检查后ratchet保留。资金改革不自动改kind/持仓线。外部持仓线改革若改H，必须先按拟真实生效H占风险账，不能用紧线授信、宽线持有。已锁退出不取消。 |
| 原流动性代理 | `temperature-sizing-20261026/code/fast_market.py:45–66` | 原1%×过去20个正量均值，再min执行日全天量，且当日H/L flat可拒成交。后两项是执行后验，不可搬到OPEN融资。J319–322明确先funding、后查execution窗口。 |

因此，额外记录PVR/CP分数、新高或I=True，再说“二次确认”没有独立证据。真正能改变**名义每股执行风险估算**的新增状态至少有：生效退出线相对实际可买OPEN的距离改变、逐单费用/最小手改变、可卖存量/T+1改变、已知成交容量与压力执行情景改变。它们仍是条件化估计，不保证真实尾部下降。

原股票CP输入另有命名陷阱：`case-stock-cp1-warmup-20261031/generate.py:23–27`把facts.i_target映射为CP模型的e0_valid；不能按字段名误称另一个独立E0证明。

若p与h同比上涨，比例距离未变而绝对每股损失可上升；若candidate低于旧线则旧层不释放；若量骤增但未来不可交易，历史容量也不代表可退出。这些是必须保留的反例，不增设已见样本例外。

## 3. 单位、成本与三本风险账

验证/源线用原当时已知adjusted坐标a，交易/金额一律raw域：`h_raw=h_a/F_t`，`C_a=C_raw F_t`。F_t用原时点factor，不用未来复权。Q为raw股，p/h/M为元/raw股，费用/风险为人民币元。partial按真实parts分配剩余gross成本及买费；split同步变换Q、每股成本/线和订单，货币额不凭拆股改变。

对层l记剩余gross买入成本K_l、Q_l、原实际退出线h_l、原卖出slip s及预计增量卖费f_l。真实已付买费一次入已损账；不能再于D+当前风险重复收费。

```text
κ_ref,l = max(0, K_l − Q_l h_l(1−s) + f_l)       # 剩余原始本金到原线的参考风险
g_ref,l = max(0, Q_l M_l − Q_l h_l(1−s) + f_l)    # 当前权益到线的回吐参考
u_l     = max(0, K_l − Q_l M_l + f_l)             # 当前已知本金浮亏参考
```

κ和g不能混称全账户DD风险。κ可为0而g/GAP/流动性风险不为0。为此还必须有**当前mark执行压力账ρ**，不能删掉它或拿任意2%储备代替：

```text
ρ_Ω(Q) = max_{ω∈Ω_t} [当前组合可标记权益 − ω下可执行清算净值(Q)]_+
```

Ω_t须给出共同时点的压力价格路径、可交易性/T+1、逐期容量、费表及未退出尾仓估值；行业/账户同时受一个共同情景，不能因为分成90行业就假定独立。参数/情景来源见第8节未解项。原No60没有这份已校准provider；**ρ未知时不得用κ=0宣称可继续扩大**。

## 4. 固定小本金的明确资金路径（最小版本A）

k用原sid×source segment×因果E0开启ID，ν记真实flat→flat执行子周期。金融I epoch、fresh CP、角色换名、迁池不清历史。B_k在首次实际授权前由外部风险政策给定并冻结；原CORE `.0025×当时NAV`仅可作沿用对照假设，不是当前有经济证据的最优或充分预算。

L_k累计真实gross负损益和实际费用，G_k累计真实gross正损益和已到账可归属权益；只append。`D_k=max(0,L_k−G_k)`。**此式选择累计净已实现利润缓冲：既有盈余G可以抵未来L，而非只偿当时旧D。B_k本身不增加，不能再另把G加到B；这仍是可再用已实现信用，不是没有风险重用。浮盈不入G、不增加现金。** 各层实际卖出的gross basis移入一次L/G，剩余basis不重算为已卖损益。

```text
可用参考余额 A_k = B_k − D_k − Σ_{live_nonexit} κ_l
                   − Σ_{buy_open_or_cancelpending} κ_order − Σ_{affected_exit} E_l
允许新量：D_k + κ_after(q,真实将生效H) + E_after(q) <= B_k
```

actual OPEN因价格/费用或真实退出使责任变化，必须按当时真实状态重核。实际亏损/GAP可令D>B，负余额保留，不能clip真实损耗。B公式只控制新增参考许可，不保证累计实际损失封顶。

同一实际层仅属于live_nonexit或affected_exit之一，不能Σκ_live与ΣE_exit双计。全户ρ仍覆盖**全部真实live（包括待退出）及未完成买单**；不得把一整份全户ρ反复塞入每个E_l。买pending尚未支付的buy fee必须进入其κ_order预留；actual fill时按原logical-order增量费将这部分一次转L/D，live成本口径不再重复已付买费，剩余pending只留未发生费用。费用支付引发的新D与旧pending释放在同一真实回调桥更新。

提线释放的是**尚未兑现保护下的参考信用**，不是settled profit/cash；资金仍须有原ledger真实available并留下原现金储备。κ逐层取正部，不用旧层负缺口借给新层。A正时可申请，A≤0则本机会不能加；原保护推进至零后再提高该旧线不额外放钱。若最近新层日后又真实提线，可再次产生余额，因此无固定次数；并无“每次无限扩张”的保证。

## 5. 结构驱动的连续总量求解，而非固定成熟目标

先由**来源政策Σ**选出一个真实合法contract a：源资格、真实physical kind、H0、CP ID及实际退出语义。I-only用原I线；CP-MOBILE用max(原I线,原freshCPcandidate)。不得让CP来源换成宽I线，也不把紧CP线偷给CORE。

对选定a，决策CLOSE定义可行集合：

```text
F_a(t) = {q是该证券当日合法买量，且
  原I/Q/行业/ACT允许、无同股未ACK买/退出；
  本机会D+κ_after(q)+E_after(q) <= B_k；
  行业与账户当前mark压力ρ_after(q) <= 给定T_sector(t), T_account(t)；
  总库存Q_live+Q_buy_pending+q在给定退出horizon的已知容量限额内；
  新单实际gross+fee满足settled现金与原stock/sector/pool资本约束 }
q_cap,CLOSE = max F_a(t)，空集记0
Q_target = Q_live_all_roles/pools + Q_buy_pending_all + q_cap,CLOSE
```

只有Σ、B、ρ provider、T、H_exit、原量价/factor/规则单位均READY时，solver才可求q。任何必要字段未知返回 `UNKNOWN_NO_GRANT(reason)`，不以局部κ已知就给正q；与已知全部条件下无合法最小手的正常 `ZERO_CAPACITY(reason)` 分开。当前授权关键项未识别，状态是前者。

这是从实时风险/容量算出的连续总量接口，不按CP数升档、不每CP领独立2%。整个股票只有一个slot/一个增量合同，仍按原PVR一次排序、单pass资金顺序；前一个真实reserve后更新组合责任再看后一个。首单q_seed也必须重新调用该可行域，不保留旧CORE已经冻结的小quantum后再锁CP；行业已确认时若CORE应可用confirmed，必须同步改route/request/allpool epoch。

**来源政策尚未识别**：`argmax_a max F_a`可消除306元CORE先成就锁更大CP的情况，但会隐含偏爱紧CP线、改变首层退出契约，绝非中性/最优来源选择；保原来源优先也可能保留小CORE占先代价。这是争议候选，不纳入已确定核心，不私加双腿种子。Σ未明确且独审前，不生产q_seed可执行单。

已有仓位的扩张有一个与父线程task4共享的**联合事件接口选项**：原I/行业持有仍健康、无退出责任、actual firstfill之后，允许原合法fresh CP或held下的新I buy_event发起一次申请。它不生成第二套算法，不增加B。

```text
I_event(t) = I_active & base.target & grade>=2 & (base.entered OR fresh_up)
apply_event(t) = 原eventQ/core_Q(I_event) OR (fresh canonical CP & 原continuing_Q)
```

`policies_g1.py:29,33`与`grade.py:24–29`表明fresh_up来自新E0正event、新S21/S63确认或已确认上行结构的新frontier；grade可以不变，I_event仍可为真。原eventQ/core_Q本身不含held/epoch，J244才后置flat/epoch阻断；原mobile_Q是替换买事件门后的continuing_Q，**不能冒充fresh I**。因此本接口的真实变化是让已有仓位也消费当时合法的新I事件，而非读取每个I_target=True就加钱。

I没有现成canonical receipt：需要绑定sid、source segment、确认观察、原i_buy/up_reasons及对应event/pivot/frontier观测来源；并非每次fresh_up都是新pivot。与CP同日/同stock/重叠底层advance只合成一个申请槽，不算两票独立确认，不重复增加目标或B；跨日共享底层信息保留关联与消费审计，不能修改原CP阈值后自称同一receipt。无法追溯I来源时该分支UNKNOWN，不伪造stock_CP、不把continuous Q当I事件。

原CP/I实际退出contract仍由Σ选择，held I走真实I较宽线就按I风险计，不能按CP紧线融资。这个联合接口与全部风险provider、Σ未识别项一起仍未给出可执行grant；没有额外1R、保本、固定天数或同价新高重复确认。

若继续要求“盈利后加仓”，可在原实际在手含费估值Π_open>0时允许申请；该条件本身已覆盖大量失败加仓，**不是已识别的新质量信息**。是否把它设为必要授权仍列Σ政策未解，不用语义强行确定。无论有没有该门，风险余额/压力/现金约束不放松。

nextOPEN只按已知OPEN和冻结q_cap缩量/拒绝，不能gapdown后增q。所有pool/role旧股与open/cancel_pending均占总量；partial不新发单。price上涨被动超过legacy stock cap只禁新增，不主动再平衡旧赢家。保No60原stock10%、行业2/10/20%、probe10%/0.5%、现金10%仅作为旧天花板对照，**不是本v2证明过的最佳值**；改变risk口径/CORE池仍需显式接口。

## 6. 流动性只用当时可知量，不能偷看执行窗口

原FastMarket60的因果部分可抽出：`c_hist(t)=.01×mean(截至该CLOSE已知的最近20个正量观察volume)`，单位股/观察；原volume单位、CA、source availability必须核对。`.01/20`仅继承原执行代理，不证明它预测次日/压力卖出容量。

总库存应受 `Q_total <= H_exit×c_hist(t)` 或同一含停牌情景的实际累计容量约束；**H_exit没有已识别经济依据，未选数值**。不能只限制这次q、却不看全存量需要几天卖完；也不能用next执行日全天volume/H/L来给OPEN钱。若历史量不足/单位不明/停牌规则未知，capacity=UNKNOWN而非无穷/0改善。

流动性改善可能使同规模库存更易退出、ρ下降，从而释放真正模型内的压力额度；单日量价共振已进入CP金额调制，不再当独立alpha。这里没有证明实际冲击函数、未来容量下界或GAP概率；这些需要独立execution stress资料，不能用“动态”二字隐藏参数。

## 7. 失败、重入与未成交退出责任

原I/ACT/各层CP退出与先旧线检查后ratchet时钟不变；若别的线程修改真实生效H，先占同一风险账，H放宽增加的责任先于新买扣除，不允许紧线评估宽线持有。没有已定义regime就不执行这个联动。

EXIT_PENDING按affected layers，`E_l=max(触发前冻结κ按剩余真实股数折算, 当前κ_ref,l, 当前u_l)`；锁的是单层参考/已知本金责任，不把全户ρ当该层责任。mark≤floor绝不自动释放。该份责任替换同层live项，不能live+exit双计，组合ρ仍包括该实物持仓。同股待退期间不新买，真实partial/ACK只释放真实已完成数量；尚在的健康CORE/其他层不因一个CP止盈退出，待该部分完结后可恢复原健康持有资格，仍需新事件和余额才再买。现金只按真实sale settlement到账，不以挂卖补available。

全flat重入同k：ν增加，actual新fill重建价格锚/层成本，D_k/B_k/CP历史保留；新CP只能申请剩余风险，不恢复一个成熟名义仓。source E0结束后新因果结构可建新k，**旧L/D行业总账不删**。行业历史债务如何分配到新k的B、何时可发新的探针预算，是独立风险偏好/授权政策未识别项，不用简单永久行业/全户耗尽开关敷衍。

有限同机会许可、实际跳空损耗可超额、最低手/固定费用以及无限正成本探针不能同时保证。本接口允许局部q=0，不保证任何行情必参与；未定义的新的风险拨款不得伪装成“新CP自动恢复”。跨行业总账至少保留原90行业与账户合计，不能编造真实PIT主题/相关矩阵。

## 8. 已识别部分、未识别部分与当前裁决

**已能精确定义/编码接口**：原CP/新I事件来源、真实层line/fee/raw坐标；固定B下正部κ余额；总持仓+pending的连续数量求解；一次slot资金先后；当前ρ provider合同；真实fill/partial/ACK/重入债务不洗的状态桥。

**不能据现证据填写的授权政策**：

1. Σ来源选择及“盈利后加仓”是否硬门；held I∪CP是可定义的联合申请接口，canonical I/跨CP去重还需来源合同；原事件是否足以提供经济增量，尚不证明选股/启动更好。
2. B_k/.25%沿用假设及新结构风险拨款如何随行业债务分配；第一笔为何应给多少，不能仅凭“试探”选另一个数字。
3. ρ的共同执行压力情景Ω、行业/账户预算T、流动性退出horizon H_exit及容量/冲击函数；原No60没有这些已校准资料。
4. 与其他持有线策略的真实生效H及regime；若未预先定义，不能反事实挑紧H授信。

故当前结论是 **分配器接口可编码，风险/来源授权政策UNIDENTIFIED，不构成可执行完整策略或经济PASS**。不恢复UPG-1数字凑齐，不以逻辑PASS授权运行。

必要反证保留：旧local_high强窗静态净−52.50万；无CORE mobile714层强贡献；post盈利后加仓占负额93.43%；G10/20/40/NR20完整账户强窗显著参与代价；2026半导体25层仅7达1R的父线程既有审查，因此本版不加1R。以上既有数不能当本v2收益/误伤估计。

父线程本轮只读链独审另有两个直接反例：中船4/30层986旧线66.4113→72.2401，原320股mark到线风险减少1832.97，但成本到线正部缺口只减1309.27至0，余523.70是利润保护，不是本A可再用本金；相关成本是否含费、未来卖费/slip尚须逐域对齐，**1309.27也不能直接变成grant**。盈新1/24真实提线、mark到线风险减少1568.34，后来仍失败。两例说明提线不是新的获利证明，marked和principal释放绝不能混算；数字来自既有独审、不是本卡运行结果。

### 交付范围

来源：No60/load_inputs/native_adapter/component/J/原预算及route/request、CP model/trace、I cache/project、FastMarket/ledger，以及v1 prior_evidence与v2 interface只读报告。旧封版不改。主报告只裁决上述数学/经济缺口；本轮0新模型/账户/回测/参数及经济路径试验，后续按父线程实际授权范围推进，不额外虚构只读工作审批要求。
