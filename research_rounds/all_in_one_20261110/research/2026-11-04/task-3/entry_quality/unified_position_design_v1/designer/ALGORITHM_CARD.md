# UPG-1：统一机会仓位与责任合同（纸面逻辑审通过，未实施）

本卡定义一套联合政策：**每个机会先取得一次TRIAL，再按已知价格进展分级取得同股总目标；已损、持仓及未成交责任共享额度。** 它联动改变flat-MOBILE风险上限、1R/2R验证、总目标、GAP储备、行业debt、全户当前责任帽及CORE池接口，**不是单因素改动**。不跑模型、经济路径、账户、影子投影或参数测试，不写生产runner。所有数值是可审的初始先验，未经收益验证，不能称最优或可晋升。

## 1. 要修的具体断点与原证据

现行No60主链为 `trend_exit_controls_v1/load_inputs.py:8–10` → `task/pvr_pool_feasibility/native_adapter.py:11–22` → `native_rank.py` → `case-stage-ledger-20261031/v3/joint_v3.py`（下称J）。

- J244–256：I-only CORE按参考风险resize；flat-MOBILE可直接拿每CP最多2%NAV gross，后者不要求实际CORE存在或盈利。行业stage晋升是行业原证据，不是本股试探成功。
- CORE不能仅看J的continue判断无价格退出：`native-I-cache-interface-20261031/cache.py:25–32`用`project(G1_I)`生成I；`b5-g1-20261025/code/policies_g1.py:20–24`在active且close≤旧floor时已令I_target=False，再由J225–229安排退出。因此原CORE间接已有I线价格触发。本卡保留原I/CP退出，不新增同名CORE硬线；参考风险仍不是按线必然成交的损失保证。
- J.Budget:16 为 `shared_loss_budget=20000, record_only`；已损不消费当前resources。原resources的 `max(mark−floor,0)` 在触线但未退出时可为0；股票市值、退出单与现金责任仍存在，不能推论原单实际释放资金或已发生超额买入。
- 原盈新链：CORE买款306.1772元，后5笔mobile周转买款92622.4842元；这是原资金路径，不是可直接删掉的亏损或本卡收益。见 `risk_philosophy_review_v1/capital_path/CAPITAL_PATH_FACTS.json:5172–5173`。
- 原银之杰layer1963：触发后300股尚在、mark到线risk为0，实际下一OPEN才卖；必须保留退出责任到真实成交。见 `risk_philosophy_review_v1/REPORT.txt:44` 及 `independent_review/BUDGET_AND_PENDING_EXIT_AUDIT.json`。

## 2. 统一身份、时钟与有限参数组

**机会key k**：原sid × 原source segment × 原E0从off到on的开启ID，采用J190–194已有 `structure_lookup`。CP ID、I金融epoch、pool、CORE/mobile标签、ACT暂停恢复均不改变同一原E0 key。原E0结束后下一次因果开启可建新k，但旧账永不删除、行业历史反馈继续携带。不能事后把失败路径合并、赢家路径拆开。

每个k有 `source_role`（原CORE或CP-MOBILE来源）、原physical kind、`position_stage`、首次真实fill、原始风险锚、已消费证据、总目标和损耗账。**position_stage不替换原kind字符串**；partial fill只建立一个逻辑首单，不重复发TRIAL。

| 项目 | 初始值 | 先验理由及局限 |
|---|---:|---|
| TRIAL/BUILD/RUNNER同股总gross目标 | 2% / 5% / 10% 当前决策NAV | 2沿原mobile首笔上限；10沿原stock cap；5是中间台阶，无最优证据 |
| 同机会阶段累计试错许可 b_j | 0.25% / 0.5% / 1% 锚定NAV V_k | 从原CORE β=.25%起按两个有限台阶放大；不是每CP再发一份 |
| 规则验证价格幅度 | 初始1R；第二级累计2R | 有限风险单位的先验，不称已证明趋势；与旧1R/local-high近邻必须并列 |
| 行业当前本金责任总帽 | 1% 当前NAV | 沿原行业risk比例，计量改为下述责任；原资本stage2/10/20%仍在 |
| 全户当前本金责任总帽 | 6% 当前NAV | 未优选先验，容纳多个行业责任；不是20%DD保证，不含全户累计损耗永久锁 |
| GAP/无法即时退出名义储备 g | 2% 当前mark gross | 初始不确定性储备，绝非最坏GAP；不能覆盖银之杰约19–20%线外缺口 |
| 原probe资本/risk、现金留存 | 10% / 0.5% / 10% | 保留原数值，risk改为同一责任口径；confirmed60继续移除 |

V_k为该k首次成功reserve的决策NAV，后续stage/CP不重锚。验证价格用原当时可知调整坐标a：`C_a(t)=C_raw(t)·F_t`，F_t为该时点原已知factor；`P0_a=P0_raw·F_0`。责任/股数/现金统一用raw域：`h_raw(t)=h_a(t)/F_t`，`Q_raw·h_raw`才是人民币金额，不能用raw股数直接乘adjusted线。不用未来复权；金额一律人民币元、数量raw股、交易价格元/raw股。

| 状态 | 进入/离开 | 可申请的同股总目标 |
|---|---|---:|
| WAIT_FRESH | flat且无待单；等待原合法新证据 | 不自动买 |
| TRIAL_PENDING | 首单成功reserve、尚无actualfill；0fill到ACK回WAIT_FRESH | 2%，无验证权 |
| TRIAL | actualfirstfill，冻结P0/H0/Δ0；满足第4节才升级 | 2% |
| BUILD_ALLOWED | 第一次CLOSE规则验证；nextOPEN仍须融资，可为0 | 5%，无BUILD实际fill不得升下级 |
| BUILD_FUNDED | 至少一笔真实BUILD增量fill；另一新CP/ownedCLOSE+2R才升级 | 5% |
| RUNNER | 第二次独立规则验证；不再有更高新级别 | 10% |
| EXIT_PENDING | 原I/ACT/对应层CP退出已提交；直到actualparts/ACK | 禁同股新买、责任保留 |
| RETRY/NO_CAPACITY | flat后同k仅以剩余TRIAL许可重试；不足最小手明确0股 | 重验前2%，旧D不清 |

原买卖资格UNKNOWN或价/线/factor/机会身份UNKNOWN时，只允许已有退出责任继续处理，不补0、不创造新target/新预算；恢复需原资料在当时重新READY。UNKNOWN不是结构成功/预算归零事件。

## 3. 首次投入：CORE和flat-MOBILE均为TRIAL

原Q/I/行业/可交易/ACT资格不扩大。原合法I-only CORE或原合法flat-CP-MOBILE均可申请TRIAL；**无需先有CORE成交，CP-MOBILE本身可成为第一笔**。

首笔总gross上限为0.02V，实际股数还受0.0025V_k金额风险、所有层级责任、原整数最小手、费用、行业资本与现金规则约束。保持2%是上限，**不等于承诺原数量不缩**；把flat-MOBILE纳入.25%风险检查是实质新约束，旧宽I线/最小手误伤证据必须正视。

首单有效退出锚H0的provenance：I-only CORE用当时原I线；flat-MOBILE用 **max(原I线,该时点原fresh CP候选线)**，与原J255一致，不丢掉较近CP线换成宽I线。若同一CLOSE两个来源同股均合法，保留一个股票slot、两个来源备选，按原CORE先、CP-MOBILE后依次检查各自真实线/资格/整数融资可行性，只成功reserve一笔逻辑TRIAL。CORE不能合法融资时才检查原CP-MOBILE备选；CORE已成功即不再买mobile。成功来源决定source_role/physical kind/H0，仅成功CP-MOBILE消费其CP；不把CP候选线偷偷装入CORE，也不伪造CP凭证。

首个实际fill前不能验证。首单partial的总冻结股数属于同一TRIAL；首次实际成交确定P0（首批真实成交价及真实费用），后续partial不改验证锚。若只reserve未fill则仍为TRIAL_PENDING，不取得持有成功状态。若整单0fill直到expiry/cancel且收到实际ACK，转同k的WAIT_FRESH、解除仅属于该pending的TRIAL_LOCK；保V_k/D_k/已消费CP历史。下一份原合法新I事件或新CP可重申请同一逻辑TRIAL，不生成新k/新额度、不重放已消费旧CP。

## 4. 可证伪的规则验证与盈利后加仓

定义冻结初始每股风险距离：

```text
Δ0_a = P0_a − H0_a·(1−s)
       + [(首批实际买费 + 按H0_raw预估卖费)/首批实际raw股数]·F_0
```

以下验证的P0/H0/Δ0/C/Hclose均指a价；费用/股必须乘F0才能与a价相加。Δ0>0，否则拒绝锚，不能以0或ε补。s用原已知slip；这不是未来真实GAP损失。split后raw股数/每股成本/每股线同步换单位，a锚与总金额承诺按原source企业行动坐标保持一致，不生成新的验证/CP。

设Hclose初始化为**TRIAL原信号CLOSE的已知收盘价**；以后只纳入actual first fill之后、严格早于当前t的已知CLOSE。当前C_t不能先放进max再比较；首个owned CLOSE不用等待空窗口。

TRIAL→BUILD须在同一CLOSE全部成立：

1. t时间戳严格晚于实际first fill，且有实际剩余持仓；例如OPEN成交，当日CLOSE即可评估。
2. 原I_target、原行业有效/原Q延续及ACT仍允许；无退出/撤买待确认冲突。
3. 存在canonical fresh stock CP，确认时间严格晚于首fill，ID未消费，且当前C_t>Hclose。
4. C_t≥P0+Δ0（1R）；同机会当前在手各层合计净估值持仓盈利为正。定义 `Π_open_est=Σ_l[Q_raw,l·C_raw,t·(1−s)−预计卖费_l−真实剩余已付成本K_l]`；K_l按真实parts含买费分摊。已卖子周期盈亏另入D_k，不能删掉，也不要求当前赢家先替全部已卖子周期回本才验证；完整机会现金流净PnL另报审计。未到账/未知权益不计作验证收益或现金。
5. 新目标及责任额度仍可容纳合法股数。浮盈只是验证条件，**不能作为可花现金或直接补预算**。

BUILD→RUNNER须有上次BUILD实际加仓fill之后的另一张新CP/另一个CLOSE，C_t≥P0+2Δ0、再创该时点之前的post-entry CLOSE高点、同样净估值盈利和原资格成立。必须至少有真实BUILD增量fill；5%目标未能全部买满不阻止以后评估，只有授予但0股成交则不得跳级。原行业必须允许相应confirmed容量。一次CLOSE/同一CP最多升一级；不能一次大跳涨把两个台阶同时领完。每级最多一次授予总目标；阶段成功是规则条件满足，不是真实未来赢家认证。

验证不要求old floor≥entry、不等全仓保本、不固定等5/10天。快速行情最早首个owned CLOSE达1R及新CP后，次OPEN申请BUILD。若该日没有新CP，即使大涨也不升级——这是真实可能的启动延迟代价，不能偷加未注册快速通道。

## 5. 所有加仓只有总目标差额

每份合法CLOSE意图以当前NAV计算并冻结金额目标T_j(t)=g_jV_t，同时按已知CLOSE含slip报价、各自有效线、风险与整数规则冻结最大新股数q_signal_cap。同级“目标不再加大”指g_j不变、没有每CP额外加2%或累加b_stage；T的人民币金额可随不同决策时点NAV变化，不能将上涨NAV当新的验证事件。当前同股**所有pool/role/k**的实际持仓市值和所有剩余买单gross均占目标。旧机会不能被新k藏掉仓位。

次OPEN已处理原退出/settle/sync后，计算：

```text
headroom = max(0, 冻结T_j − Σ同股Q_live·已知OPEN − Σ同股open/cancel_pending剩余买单gross)
q_new = 最大合法整数股数，满足 q_new <= 冻结q_signal_cap
        且 q_new·已知含slip买价 <= headroom
        且费用/现金/原stock与industry资本、各级责任合同全部成立
```

target是天花板，不是必须买满；数量严格按原每证券/当日buy_minimum、buy_step及卖出零股/odd-lot规则，不统一假定100股；不足最低手为0，不为凑试仓向上补股。OPEN跳空重新核冻结目标、金额风险和最小手，不增加信号已冻股数；已知split仅按原企业行动换等价单位。已有未完成买单不得另发同股新单。cancel_pending在ACK前仍扣。被动上涨越过5/10%总目标只禁新增，**不自动卖赢家、不逐日再平衡**。

stage授予的证据仅成功reserve原子消费一次。“每级一次”以真实flat→flat持仓子周期ν为单位；同k重试可在新actual first fill后重新验证BUILD/RUNNER，但只恢复同一绝对b_stage ceiling与2/5/10总目标，不把旧已授b加到新b上。V_k/D_k/所有receipt历史不清，ν只是执行子账，不能洗损。stage决定总target，不是在每张CP旁边再产生2%额度；后续同级新CP至多申请仍未完成的目标差额，仍须原合法新证据与剩余风险。未成交而撤销的授予保留审计，不能无条件每天重放已消费CP；需要下一张原合法新证据，stage目标不再加大。

**每次同级补目标都重新验证**：BUILD用当前1R门、RUNNER用当前2R门；当前CLOSE须新过此前post-entry Hclose、Π_open_est>0、原I/行业/ACT合法，fresh CP严格晚于上一次成功funding及最近一次相关退出完结时点（取较晚者），并重核所有预算。不能靠一次历史验证在后来亏损/弱反弹中自动补成熟目标。TRIAL在未升级前不以新CP补首单；只有原已reserve首单的真实剩余partial可在原expiry内续fill。因而“持仓少于target”本身从来不是买入信号。

单次数量算例（仅手工目标差额算术，非价格路径模拟；先忽略slip/fee）：NAV=100万、BUILD冻结目标5万元，旧仓200股、已知OPEN105元、无pending，则gross差额29000元；**仅对buy_minimum/buy_step均为100的证券规则**，目标最多允许新增200股=21000元，之后同股总gross42000元。真实执行须按原slip、费用、该证券当日规则及全部责任重新核数量/金额，可能进一步缩量或为0；上述gross不是精确执行收据。不能把目标5%误写为再买5万元。

## 6. 本金损失、浮盈回吐与未成交责任分开记

每层l记录**剩余**真实gross成本K_gross,l、剩余分摊买费F_buy,rem,l、`K_l=K_gross,l+F_buy,rem,l`，以及剩余raw股数Q_l、raw mark M_l、按上述factor换算的raw退出线h_l、预估卖费F_sell,l。K不是原始整单成本：每次partial sell按真实parts移走sold gross basis和买费分摊，满足 `K_before=K_sold+K_remaining`；已卖本金不能仍计在剩余仓成本内。

```text
principal_ref_allin_l = max(0, K_l − Q_l h_l(1−s) + F_sell,l)  # 含已付买费的本金参考
principal_budget_l = max(0, K_gross,l − Q_l h_l(1−s) + F_sell,l)
giveback_ref_l  = max(0, Q_l M_l − Q_l h_l(1−s) + F_sell,l)    # 当前权益到线回吐参考
known_loss_budget_l = max(0, K_gross,l − Q_l M_l + F_sell,l)
```

**主预算用本金责任，不用giveback冒充本金。** 真正已付买费在buy回调一次入L，故主预算不能在D+R中再计live买费；principal_ref_allin另报，R用principal_budget。为防止抬线到成本价就把责任写成0，每次真实fill冻结该层r_entry=该fill时principal_budget；剩余仓责任：

```text
R_l = max(principal_budget_l, known_loss_budget_l, r_entry_l·剩余股数/原fill股数)
      + g·Q_l·M_l，g=.02
```

未来卖费/原slip在r_entry内，已付买费在D内一次入账；线≥entry也保留首笔承诺、卖费与2%当前mark名义储备。g不因floor≥entry归0；它随仍持有gross计算，并非“统计上足够”的估计。行业1%、probe0.5%、账户6%都改用此primary责任，不继续混用旧mark−floor风险。**这是计量和接口的真实改动**，不把原比例同名当相同经济约束。

这是一项不会凭价格触线自动释放的会计授权责任，**不是最坏GAP损失、统计VaR或真实DD保证**。giveback_ref单独汇总并在审计公开；无谓将浮盈回吐当现金、利润保障或新增资金。2%mark只是这张未优选卡的固定初始储备；停牌、多日跌停及银之杰原约19–20%线外缺口均可能远超它。

pending买单按冻结最坏买价/未付买费/预计卖费/有效线计算同一R，GAP项以未完成gross为基数。actual fill时将已付买费从pending预留一次转入L，remaining order仅保留尚未发生的增量费，open lot责任不再重复买费；open/cancel_pending直到真实fill或ACK分配/释放。TRIAL/BUILD/RUNNER每层H0及后续线必须有source/confirmed_at，不从未来peak回填。

## 7. 同机会重试、行业反馈和跨行业总账

机会k：每次实际卖出的gross PnL=`实际sell gross−该parts的sold gross entry basis`；负项入L_k，正项入G_k。L另在实际发生时记每笔buy/sell费一次，不再把含费K_sold整体重新记损失；G另含可归属已到账权益。append-only，保留毛项不互相覆盖。净已损D_k=max(0,L_k−G_k)。正浮盈不冲销D。partial sold basis只进一次真实已实现项，remaining basis只在live责任/净估值中，不两边重叠。

行业s：聚合**所有旧/新机会key**的L_s、G_s，D_s=max(0,L_s−G_s)。90行业原映射仅相关性代理、当前快照非PIT，不能声称不同桶独立。无可靠历史共同主题映射，不造“新题材组”；跨行业共同风险由账户合计约束兜底，仍不能刻画真实协方差。

```text
α_s(t) = b_sector(t) / [b_sector(t) + D_s(t)]，b_sector=.01·V_t
同机会允许新增：D_k + Σ_k R_live + Σ_k R_pending + R_new <= α_s·b_stage(k)
同行业允许新增：Σ_s R_live + Σ_s R_pending + R_new <= .01·V_t
跨行业允许新增：Σ_all R_live + Σ_all R_pending + R_new <= .06·V_t
```

同机会损耗与旧仓责任共享stage总许可，fresh CP不清D_k、不再造b_stage。行业历史债务连续降额但对有限D_s不数值变零；**账户历史gross亏损仅审计，不进累计耗尽后禁全户新单的硬开关**。当前责任不足只拒新增，不强平旧赢家、不触发ACT全户off。原ACT仍为另一个已有安全层，其episode peak恢复重置不等于全局本金20%floor。

整股flat后回到RETRY时stage降TRIAL；原k的D_k/V_k/已消费证据保留。必须等全部同股退出fill、待单ACK、真实持仓为0后，新的原合法I事件或新canonical CP才能申请同k剩余TRIAL额度；不要求越旧高，不恢复成熟5/10%目标。每次flat→flat有ν/attempt_id；新ν的actual first fill重建P0/H0/Δ0及Hclose（以新原信号CLOSE初始化），不重建V_k、不清D/receipt历史。若额度不足最低手，局部k为NO_CAPACITY，不伪造探针。新因果E0开启可建新k和新的TRIAL预算，但行业D_s不重置；资格和风险约束仍可使股数为0。

固定有限同机会总损耗与无限次正成本探针不能同时保证。即使同k许可有限，GAP/无成交也可使实际L超过事前许可；必须保留负余额/超支debt，不将真实已损clamp成B或抹零。本卡不保证同k无限重试，也不保证累计实际损耗封顶；选择“同k有限新增参考风险许可，新因果结构可再次试，但历史行业反馈保留”。长期债务/最小手仍可能使一行业暂时无可交易探针，不能粉饰为永续无损探索；其他有额度行业继续按原资格竞争。没有靠全户冻结解决低质量机会。

## 8. 结构失败、执行优先级与EXIT_PENDING

保持实际退出：position_stage不重写原physical kind的持有语义。CORE沿原I_target/ACT退出，原G1_I先检测close≤旧I floor再ratchet新floor；mobile/add沿原保存CP线收盘触发，未触发才以已知I/新CP候选max收紧（J235–240）。不把当前刚ratchet的新线提前作同CLOSE触发，不把新CP候选倒灌到旧CORE，不为腾出额度强抬旧赢家线。行业失效使新增/升级不合法并沿原预算撤pending，但不单独新增全行业强卖；真实持有退出仍由原I/ACT/该层CP规则决定。h_l必须引用该层原实际触发语义，不能只用同名更近参考线虚构风险下降。

冲突顺序：原ACT/I/该层CP退出及行业新增资格失效（后者仅撤pending/禁新增） → 已经存在的退出责任 → ACK与结算 → 新验证/新买。验证和持有失效同CLOSE则失效优先；已提交退出不可用次日CP转强撤掉。重叠理由合并到同一退出集合，不重复卖同层。

EXIT_PENDING是**受影响layer集合的覆盖状态**，带resume_stage，不等于整机会失败。原mobile单层CP退出只卖被触发层，不清仍健康CORE/其他层；I/ACT全股退出才覆盖全部层。某个CP层退出期间仍沿原sid exit_pending阻止该股新增。实际请求的parts已全成交/ACK后：若仍有健康持仓且原I允许，返回HOLD(resume_stage)，保已达到的目标ceiling，但标记REFILL_DISARMED；只有上述新的同级验证才能再申请差额。若已all-flat则进入同k RETRY，新ν重新TRIAL。不能永远等健康CORE也flat才解除单层pending，也不能把CP止盈/止损次数按各partial重复记为多个机会失败。

进入EXIT_PENDING时锁定每层当时R_exit；以后：

```text
R_pending_exit_l = max(触发前冻结R_exit按剩余股数折算,
                      当前known_loss_budget+g·Q_remaining·M_current,
                      当前principal_budget+g·Q_remaining·M_current)
```

mark≤floor不归0；未成交、T+1不可卖、停牌/跌停无窗口均继续占股数、资本、退出责任和预算。同股禁止反向新买。partial sell只按实际parts/真实股数释放对应冻结责任，并把真实费用/负损耗记账；余额到真正成交或合法取消ACK前不释放。拆股同步改Q、每股成本/线/冻结锚/订单单位，总金额承诺不变；现金分红与权益AR不双算、不提前作spendable。

触发线与次OPEN成交之间仍有GAP/费用/流动性未知。R是计划/授权责任；实际亏损可超过预算，超额后以真实损耗更新账本，不能补填成“按线止损成功”。

## 9. probe/confirmed与原接口必须同时修改

TRIAL统一资格独立于source_role，但不伪造stock CP；行业level0仍仅probe、行业总资本2%。行业level1/2允许真实TRIAL（含I-only CORE）使用相应confirmed容量；BUILD/RUNNER只在原行业确认容量合法时扩张。原probe全池10%、0.5%责任、行业资本和现金10%留存继续核。

这依赖CORE-confirmed资金池草案的接口修改，**不是已实现功能**：route当前仅mobile可选confirmed；request226禁止非mobile confirmed；core_epoch锁当前只在probe_request分支。三处要同时改为来源无关的campaign/TRIAL锁并对所有pool生效，迁池/取消ACK/restore都需覆盖。不能把CORE改名mobile绕过验证。已有旧资金不会因新标签无损自动转换。

同sid在native PVR unique-stock排序仅占一个slot，TRIAL/TOPUP不另排两次；同一reserve原子处理预算、CP/验证证据消费、原现金锁与实际订单。原request在资源/migrate检查之前已写stock_requests/consumed，当前并无这里要求的完整事务。实现必须先无副作用prepare校验，随后在一次commit内写预算reservation、CP/验证消费、campaign锁和真实reserve；任一步异常必须停止该时钟并恢复commit前完整状态，不能只还现金却保留已消费CP。取消仍按真实ACK，不回滚已经发生的真实fill；成功reserve后无fill的凭证不能无条件再领。checkpoint必须带新policy/state/source hash及事务边界；不能读旧状态假称同合同。这些均是未接线的设计义务，不声称已具备。

## 10. 必须保留的反例与当前否证边界

- 旧local_high曾把flat-mobile按CORE .25%及宽decision I_floor缩量，并等待post-fill high：强窗静态少正869088、少负344095.56、净−524992.45；中船Apr22 320→0、原层+89853.47，唯特偶Apr20 300→0、原层+52230.89。本卡保留CP较紧线并允许首owned CLOSE，经济动作仍近邻；.25%统一风险/最低手误伤仍未知，不能称修好了这两例。
- 303新增层中，85个加仓负层有80个在原仓已浮盈后发生，相关负额65268.16占加仓毛负93.43%。因此“原仓盈利”本身不是足够质量证据；1R+新CP/价格前沿仍可能连续假突破，不保证解决主亏。
- 原strong无CORE mobile714层贡献约112.38万元；不得要求原CORE先盈利。本卡允许其本身先TRIAL，但后续成熟授权节奏仍可能伤它们。
- 旧保护毕业需floor≥entry，恢复56层仅24 ever-hit，中位12.5session；本卡明确不采用，但1R本身也会延迟/错过快涨后马上回落、V恢复或先放量后无新CP的赢家。
- 旧G成本guard全账STOP：强窗G10/G20/G40/NR20分别+10.610/+45.484/+99.183/+21.846%，对照+126.328%；不能靠“保护释放额度”语义宣称有效。本卡不以浮盈抵现金、旧层承诺不因抬线自动归0；仍属风险反馈/资金许可近邻，未有绩效支持。
- 总目标差额会在反复假突破时反复恢复损失后仓位，局部D与stage重置限制但不能保证反复试错净损小；行业反馈可能拖慢真实新主线，不得隐去。

当前只可裁决逻辑与接线是否闭合。任何未来经济研究必须先独立审卡、冻结唯一数值组/反例，再获用户授权；本轮不启动。旧开发窗不称样本外，不把原层损益差额当本卡账户收益。
