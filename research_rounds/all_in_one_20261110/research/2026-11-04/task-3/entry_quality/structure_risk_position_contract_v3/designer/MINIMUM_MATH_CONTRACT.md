# SRP-v3：共享风险账最小数学合同

状态：**初值已明确的待检研究合同，未实现、未回测、非最优/收益保证。** v2留存不改。只为task4最新 `upside_revision_v1/MINIMUM_CARD.txt` / `logic/MINIMAL_INTERFACE_AND_INVARIANTS.txt` 提供同一RiskBook；不复活旧PAPER_CARD的EMA门、固定4/6%目标、两次或1R规则。本轮0模型/新账户/回测/参数搜索。

## 1. 已冻结候选初值及推导

| 项目 | 候选初值 | 来源/含义 |
|---|---|---|
| 同机会参考本金 | B_k=.0025·V_origin | 沿原CORE单笔比例，但改为同机会共享；非已证明最佳预算 |
| ACT剩余空间 | A=max(0,V_prefix−.8·Peak_ACT) | 从原ACT20当期峰值到阈值的剩余金额；非终身本金floor |
| 共同压力折扣 | 一步.8，两步.8²=.64 | 20%取已有ACT损失尺度与银之杰触发收盘到次日成交约20%的进一步下跌反例作先验，**不是历史法定limit、概率或最坏界** |
| 历史容量 | c_i=floor(.01·mean(最近20个已知正量观察)) | 沿原执行协议参与率/观察数，另作事前限额；不读次日全天H/L/volume |
| 行业压力份额 | T_s=(c_s/.90)·A，c_s=.02/.10/.20 | 沿原行业stage资本门与现金留10%对应的90%风险资本，把剩余空间按旧集中度份额分配；待检先验 |
| 其它原门 | 原stock10%、行业资本、probe10%/0.5%、行业名义risk1%、现金10% | 保原分母和门；下述待退出锁是对risk0的明确补充，不用新κ偷换旧g |

**原库无完整historical ST/涨跌幅bound。** 统一20%是压力估值代理，不按STAR/BJ猜真实涨跌幅；dated quantity、费用、T+1/结算和已知可交易状态仍用原版本。压力估值含5bp费用假设也不声称是合法limit订单成交价。

## 2. 真实持有合同H、单位与快照

RiskSnapshot绑定 `book_version/as_of/source/ACT_episode/proof/holding_contract`。CORE和新HELD_I_INCREMENT沿真实I_target/last_I_line，旧MOBILE沿真实逐层CP线；新I层没有“初始entry线永久硬max”。先旧线触发/原I退出，未触才ratchet，再同步风险。任何新H放宽先按放宽后的全存量申请，拒绝则保持旧H；已锁退出不可撤。不允许紧CP线定量后按宽I持有。

比较在原当时已知a坐标，金额用raw：`h_raw=h_a/F_t`、`C_a=C_raw·F_t`；Q是raw股，价格元/raw股，风险人民币元。M_i为当前已知投影mark；若当前已有更低可知OPEN报价，压力起点Z_i=min(M_i,known_OPEN)，否则Z_i=M_i。新拟买使用raw已知OPEN m作mark/Z，支出仍p=m(1+s)，**不能把含buy slip的p当mark**；CLOSEpreview用当时raw reference，不得用未来CLOSE。投影book/cash/mark与实际native账分开对账，不改写native NAV。

机会k=`sid × source_segment × 原canonical E0真实off→on开启`，**正price/volume event不是新E0开启**。B_origin为该k首个真实成功reserve的signal NAV；首单纸面preview用本signal NAV拟冻结，reserve失败不建立新额度。盈新Jan20仍是原E0段内新正event，不能另造B；Jan10已冻结的B及D继续。跨k旧损耗账不删，透过真实NAV/ACT空间与公开行业账保留；本版不另加历史行业debt倍率，不声称跨E0累计损失硬帽。

## 3. 费用分组与κ、g、待买责任

真实剩余gross买入basis为K_l，不含已付买费；已付buy/sell费一次入L。partial移走sold basis满足 `K_before=K_sold+K_remaining`。L累计gross负损益+真实费用，G累计gross正损益/已到账可归属权益，`D_k=max(0,L_k−G_k)`；这明确允许累计已实现盈余抵未来L，但B本身不增加，不能又把G加B。

每个情景先构建卖出逻辑order组g：已有真实退出用其order_id/真实target parts；其它同sid待压力估值层合为一个prospective liquidation group。**每组**按原dated FeeSchedule全部适用components与原logical-order累计最低佣金状态，算剩余增量sell fee一次，再按该组剩余raw股数分配到层；不每层重复5元、不另收已付费。原buy order同理按真实剩余增量费计，不按partial回调重收最低额。计划情景各层价格可能不同，组费用用合计卖出名义额。

令 `X_l^P=min(M_i,h_l)·(1−s)`，f_l^P为上述组费用分配。**min(M,h)禁止破线/高线虚构卖出利润。**

```text
κ_l = max(0, K_l − Q_l X_l^P + f_l^P)       # 逐层正部：原始本金到计划退出
g_l = max(0, Q_l M_i − Q_l X_l^P + f_l^P)   # 当前市值到计划退出回吐
u_l = max(0, K_l − Q_l M_i + f_l^P)         # 当前已知本金浮亏参考
κ_buyorder = max(0, q_rem·p_limit − q_rem·X_order^P + f_sell_alloc)
             + 未付buy增量fee
```

κ必须**逐层positive后再加**，不能全机会净额后positive来用旧层保护浮盈抵押新层。floor≥cost可令某层κ为0，但g/共同压力仍不为0；提线过0不继续释放该层κ。费用/容量使风险非线性，单位增量应算 `u(q)=Risk(book+q)−Risk(book)`，不以固定每股费或一个近零价差相除。

`D_k+Σlive_nonexit κ_l+Σbuy_open/cancelpending κ_order+Σaffected_exit E_l^κ`是原prefix含pending责任的展示量；最终grant统一使用第6节全量postfill投影后的同机会量≤B_k，不混两种成本域。pending buy尚未付的买费预留在κ_order；真实fill时按实际增量费从pending一次转L/D，gross数量转live，已付买费不再重复计live κ。若G已有净盈余缓冲，费用转入后D仍按max(L−G,0)实际更新，不声称每一元预留都会机械变成一元D；缓冲不另加B。失败/超额可令D>B，负余额如实留账，不clip真实损失。

## 4. 有限共同情景Ω与容量

对当前book实际持仓、买单剩余和拟新增q，固定 `Ω={P,G1,G2} ∪ {S_s1,S_s2:当前行业s}`，最多183个，**不是无限所有路径**。

| 情景 | 同一情景的估值/容量假设 |
|---|---|
| P计划退出 | 各真实层按min(M,h)，原slip与order组费；不把高于mark的线当利润 |
| G1全户共同一步 | 每sid只生成一个基准b_i=min(Z_i,该sid所有实际live/待买/本proposal真实计划h的最小值)，共同在该边界外折.8；X_i=b_i·.8·(1−s)，同股全部层同价。可卖性/T+1逐真实批次 |
| G2全户共同延迟 | 同一唯一b_i，第一压力OPEN容量0，第二OPEN共同折.8²；X_i=b_i·.64·(1−s)。第二期容量至多c_i，尚未可卖批次仍0 |
| S_s1/S_s2行业共振 | 行业内同一步/延迟，行业外非退出持仓保持M；已锁退出责任仍保留 |

G1/G2固定是**计划退出边界之后**的一次/两次20%估值折扣，用以单列越线跳空/延迟，不是现价仅跌20/36%。sector情景对受冲击sid也用同一唯一b_i；行业外非退出持仓留mark。P仍按各层h作计划退出参考，**不是同一时刻的物理共同成交情景**。压力不允许同sid各层各取h·.8生成多个市场价。若新宽I令b_i变低，则同股旧紧CP层的共同压力也增大，先占全股责任；这不修改旧层实际保护，只是保守压力联动，可能过严。

本proposal的h仅在q>0时纳入b_i；q=0不把未获资新线写进book。原库存、真实pending和已commit持有合同始终计入。新增一小笔宽I可能令整股压力发生台阶变化，不能用恒定单位风险线性外推。

每个压力价计原slip和order费用；不声称该价能在limit/halt当天成交。共同shock先作用于预定基准，再合计全账损失；不能把股票A的P最坏与股票B的G2最坏任意拼成“同一情景”。此基准在任何全局pressure计算之前冻结，不按计算结果选择。

事前容量c_i只用CLOSE已知、与原finite positive-volume mask一致的最近20个正量（含当时已经公布的本CLOSE，不包含nextOPEN所在日的完整量）。历史volume需按截至快照已知share actions换到当前raw股单位并绑定来源；缺单位/行动桥则UNKNOWN。新单要求 `实际总Q_i+未ACK买余量+q <= c_i`；exit只是库存子集，不再加一遍。已有超c_i只拒新增，不假定强卖已成交。

压力内按真实sellable_at、dated卖出格点和容量分配可卖量；未卖余量按该压力价估值，**仍是库存/责任，不是现金/退出完成**。已知停牌/locked不成交时容量0，不假卖。超过两期仍卖不出，保持余量责任并报告stalled；另列“余量零估值”故障暴露，不把它混入primary Ω使所有股票必全拒。连续多日停牌/跌停可超出此有限初始压力，绝不据此保证ACT20不被击穿。

## 5. 全户与行业压力损失，退出锁逐情景去重

每层在情景ω的当前mark损失 `φ_l^ω=max(0,Q_l(M_i−X_i^ω)+f_l^ω)`（P仍用该层X_l^P）；每个pending买单为 `φ_order^ω=max(0,q_rem(p_limit−X_i^ω)+f_sell_alloc)+未付buyfee`。同一真实/预期逻辑order费用只按第3节算一次。sector外无新卖出时X=m、sellfee=0，但pending仍保留q(p−m)+未付buyfee，不能因不受shock省略已知入场slip/费用。

affected exit与live_nonexit互斥。进入退出时保存每层各ω的 `e_req,l^ω` 与κ_req；actualpartial只按真实剩余股数换单位，费用按真实order增量重算。待退责任：

```text
E_l^κ = max(κ_req按真实余股折算, 当前κ_l, 当前u_l)
E_l^ω = max(e_req,l^ω按真实余股折算, 当前φ_l^ω)
Φ_market,ω = Σ全部真实live(含待退)当前φ_l^ω + Σ待买当前φ_order^ω
Λ_ω = Σlive_nonexit φ_l^ω + Σaffected_exit E_l^ω + Σbuy_open/cancelpending φ_order^ω
Φ_market = max_{ω∈Ω} Φ_market,ω
Λ = max_{ω∈Ω} Λ_ω
Λ_s = max_{ω∈Ω} 同一ω中属于行业s的授权责任和
```

Φ_market才是同一当前快照的情景经济压力；Λ是加入request历史锁的授权保留量，不能把各请求时点E拼成真实同步market loss。预算用较保守Λ，报表同时给Φ_market/Λ。不能把一整份Φ重复塞每个E；也不能Σ_i max_ωφ_i冒充max_ωΣ_iφ_i。mark跌到floor下面不释放冻结责任；实际已知价格/费用变坏，E可提高。只有实际fill/真实cancel ACK才释放完成部分；买余量ACK前占资本/现金/责任。旧亏损、真实live与新pending费用分区一次，不重计。

待买→fill的压力/NAV桥必须在同一投影book/cash/mark上守恒。新买须原preview严格raw OPEN m>h，pending/fill使用相同raw factor、实际H、唯一b_i及order fee group：`pending φ=q(p−X)+F_buy+F_sell`；fill后 `live φ=q(m−X)+F_sell`，`NAV损耗=q(p−m)+F_buy`，故二者之和相等。不能在pending用p做Z、fill改m，也不能在比较prefix A时再扣一次buyfee。若native当前mark不同于投影m，保存显式mark差额桥并用同一估值域重算NAV/φ，不能强制抹平native账。

## 6. 可实施的共享额度与q

OPEN先原退出、真实结算/sync；每个原PVR槽位只走一次当前prefix。`V_prefix`为此prefix原真实账NAV，`Peak_ACT`为原已存当期ACT峰值，不在风险模块自行重设。**最终grant一律在拟q及全部未解除预计fill的全量postfill责任投影上计算**，不混prefill行业分母：

```text
V_proj(q) = V_prefix − Σ预计fill [q_j(p_j−m_j) + 原logicalorder剩余增量buyfee_j]
L_proj = L_actual + 预计fill的尚未支付buyfee（仅投影，不写真实损耗）
D_proj = max(0,L_proj−G_actual)
预计fill股数/真实grossbasis转入projected live，移除对应pending数量及未付买费项
A_proj = max(0,V_proj−.8·Peak_ACT)
T_s,proj = (c_s/.90)·A_proj，全部行业同时重算
```

预计fill包含仍可能成交的open/cancel_pending剩余和本proposal；仅在责任投影中视为发生，不伪记真实fill/现金/成本。每个q的postfill κ/Φ/Λ、费用组、T+1与同股唯一b_i全部重算。入场cost已移入V_proj/D_proj后，Λ_postfill不再含同一笔pending买费/slip。prefillpending含cost与账户A_before的等价式只作守恒审计，**不能拿prefill T_s=w_s A_before给行业grant**，尤其不含本次买入的其它行业也会因V_proj下降而T_s缩小。

对原source已冻结的q_cap，逐dated合法BUY格点求最大q≤q_cap，要求：

1. 全投影后同机会D_proj+κ/E预算≤固定B，预计已付买费不再留pending责任重复一次；
2. `Λ_postfill(q) <= A_proj(q)`，**所有行业** `Λ_s,postfill(q) <= T_s,proj(q)`，同时公开Φ_market；
3. 原sector1%/probe0.5%名义风险门继续用原 `R_legacy=ΣQ·max(M−h,0)+Σbuy q·max(limit−h,0)`，不把本卡含费/slip的g冒充同口径；affected exit以该层冻结legacy责任与当期legacy值的较大者替换0项。原资本/pool/stock/现金门同原分母；
4. 同股总库存+pending+q≤c_i，真实费用/可用现金和最低手均满足；
5. 来源、holding_contract、canonical proof、book_version完全一致。

不预设可行性单调；可枚举有限BUY格点，只有单调性经证明后才用二分优化。风险单调/非线性不能靠LR旧二分函数名假定。q=0是合法结果，不向上凑最小手。

g_P、κ与完整压力Λ/Φ不是可相加的独立损失。G相对计划退出的额外回吐可仅诊断为 `max(0,Φ_market,G−g_P)`；grant已用完整Λ，不能再算g_P+Φ。新增宽I改变整sid的共同b_i，因此 `ΔRisk(q)=Risk(整个projected book+q)−Risk(同域book)`，不能化成q×新层风险。旧legacy门仍用原native分母和原nominal定义；不得把新postfill A/T分母偷换进原现金/sector/probe/stock门。

RiskGrant为 `(book_version,proof_id,source,qty,gross,buyfee,holding_contract,κ/Φ_market/Λ占用,有效nextOPEN)`，授权预算实际用Λ；commit一次原子写预算/原现金锁/事件消费，版本不匹配重算、不得两条线用同余额。CLOSE只冻结局部source cap与单笔.25%signalNAV上限，不提前花明日卖款、不因今日现金少就冒充nextOPEN final deny。OPEN只减量/拒绝，不能超冻结cap或读取当天未来I线/HLV。qpaper若缺全组合字段仅标LOCAL_CAP_NOT_FINAL。

## 7. 对齐task4最小入口与故障行为

CP KNOWN_PRESENT：原CP入口/原2%单次gross/真实CP初始线与退出语义保持，额外同一本风险合同可能同量/减量；不转I救单。CP KNOWN_ABSENT才考虑真实held+原fresh i_buy/core_Q+confirmed-only的typed HELD_I_INCREMENT，I线定量/持有、不套MOBILE2%单次上限；源身份必须底层event/pivot/frontier可追溯，persistent I=True、CP UNKNOWN都不造新proof。原CORE/旧MOBILE不转轨。风险合同对未来ON/OFF比较须完全相同，不能把风控变化归为held-I收益。

既有持仓按原因果k首个成功reserve来源回建B/历史L/G；缺原origin signalNAV或key则UNKNOWN，不以本次Q或最早事件假造起点。真实新E0开启才可新k，旧行业账仍公开；正event换名不能洗损。无固定成熟目标/次数，不因自然涨超stock cap卖赢家。

必要输入真实缺失（原价/fee/quantity/factor/vol单位/原origin/ACT峰值/事件来源）返回UNKNOWN_NO_GRANT(reason)，旧退出/责任继续；候选初值的未经经济验证本身**不**使整卡UNKNOWN。全部输入齐而预算/最小手不符为DENY_ZERO(reason)。当前已有风险>A/T或已超容量只禁相关新增/H放宽，不强行卖出、不另设置全户ACT状态；可随真实退出/风险下降恢复，原ACT暂停/flat-break恢复仍另按原代码。

## 8. 已知机械代价与未承诺事项

G2若忽略费用/plan/退出锁，风险已至少为36%gross；在NAV=ACT峰值、A=20%NAV时，gross机械必要上界20/36≈55.56%NAV，其它门/费用/更远计划线只会更紧。行业同理最多约0.6173×旧stage资本cap（2/10/20%对应约1.2346/6.1728/12.3457%NAV），而非自动保留原暴露。这会压低强窗参与，可能重复已知G类伤尾部代价，不能因“动态/共享”就称改善。行业T_s也可能使原高stage库存已超、下一单为0，不因看到赢家再救参数。

银之杰已知反例的两个分母须分开：触发CLOSE37.76→实际sell30.194895的进一步下跌约20.03%；保护线41.0234→sell的线外缺口约26.4%。本初值不能把它们都叫20%；G1可能不足、G2也非最坏界。

κ本金释放与g回吐不同：中船原320股提线的marked减少1832.97、本金正部只减1309.27至0，余523.70不能当A版本金信用；原费用/slip还需对齐，不能将1309.27直接grant。盈新真提线、marked减1568.34后仍失败，提线不是盈利证明。本合同控制授权/暴露，既不证明选股更好，也不保证实际损失<=B或DD<=20%；两期后继续锁死/更大跳空可击穿。

数值是从既有尺度构造的**一个完整待检初始组**，不是最优、历史概率、合法涨跌幅表或后验调参结果。后续若获准验证必须保留低容量/宽I/快启动/同业共跌反例，不能先按名股填补例外。本轮仅代码可实现公式和故障行为，0新回测。

父线程已完成7个**原账户真实OPEN prefix**的只读桥（原sell/settle之后、first reserve之前），全部已满足 `.36×原inventory > A`，所以本初值的最终新增grant全为0；局部cap476/369/2300等不得冒称可成交数量。两个已公布例：2026-04-22为513611.82>271396.91，2022-01-11为316302.26>195436.66（元）。这是本初值在这些原prefix不能实现扩张的明确反例，因此不推荐直接采用，也不调整参数来救这7例。

该桥不是从flat启动并连续运行本策略的新账户；若更早风险门已改变持仓，后续prefix会不同。因此不能由这7个0推称完整策略收益已被回测否决，也不能隐藏全局门只报告局部正cap。完整共同情景/实际资金路径未运行；这里的拒单由已违反的必要下界即可确定。
