# MATURE 新 SEED 的个股 CP 证据门槛：单一事前设计

状态：DESIGN_ONLY / NOT_FROZEN / NO_HISTORY_RUN。仅本地代码与既有研究资料；没有外网、CNINFO、PDF读取，没有账户重跑、历史筛选、参数扫描或冻结引擎修改。

## 1. 结论先行

候选可以被定义成可计算、可反证的一项入场资格改变，并不存在“没有先持仓就永远不可能出现 CP”的逻辑死锁。CP 是市场数据生成的推进证据，不需要持仓、已有利润或 ADD。

但它不是已经成立的改进，也不是“成熟行业中的个股必须已获本轮盈利验证”。F 是行业条件，保留F旁路只是快速启动的取舍，不是宣称F胜率或期望收益优于S；放行 F 并不能保证该股有推进证据。S-only 不是假主线的同义词。CP 是波动尺度下的新高推进 receipt，不是回踩确认、旧亏损修复、保护线必须抬升或本金不亏证明。现阶段不建议冻结或声称能减少净损失。

唯一假设：当原行业资金阶段已是 MATURE，而行业快路径 F 尚未提供充分广度推进证据时，新个股至少应在其原 A/B 决策当日或以后形成一个当前仍有效的原 CP receipt，再取得原成熟扩张额度；EVENT/RESIDUAL 的小额试仓、已有持仓、ADD 和退出规则均不变。

本稿在查看任何新 CP 门槛筛选结果之前固定：receipt_day >= original_signal_day，含 signal 当日；不再比较严格 > 的第二版本。同日 A/B+CP 只称“同期个股推进证据”，不能称“额外经过一轮验证”。选择 >= 的结构理由是要求决策时可用的、与本次入场同时或较晚确认的市场证据，而不是要求机械经过另一个交易日。严格 > 会无条件推迟全部 S-only 首个 nextOPEN，不能把这种一日延迟包装为结构必要性。两种写法本来是不同假设，本稿只保留前者。

## 2. 不得因样本结果改变的边界

- 保留原 M=S OR F、Q、E、W_alloc、代表排序、容量/dated lot、经济下单单位、单次原始 NAV 预算、现金准备、分配及融资迁出规则。
- 仅改变当前 allocation_phase=MATURE 的新 SEED 的合法需求；不新增 I 抬升、收益正号、等待 N 天、M 连续 N 天、旧轮高点、亏损次数或 CP 距离阈值。
- 不把新 SEED 变为 ADD，不让其拥有 confirmed_history，不把入场 CP 写进真实持仓 active.cp。
- 不添加本金不亏、风险必须被浮盈覆盖或“加仓会用掉利润就否决”的条件。原 ADD 的既有净利条件及执行检查原样保留，本稿不扩大也不重新解释它们。
- 不恢复共享试错风险池。等待不占现金、不占风险预算；释放的资金仍由原账户机制处理。
- “规则不变”不等于反事实中的订单、ADD数或退出日期必然相同。种子入场改变以后，现金、持仓和后续行动可以内生改变，不能强行复制原路径。

已知背景反证，均不是本候选的新筛选结果：晚期479个MATURE中393 S-only原净约−75982、40 F-only约−17179、46 both约−26947；9/24 OPEN的28 MATURE全部S-only；10/24光伏30 MATURE也全部S-only，原净+35358.06。晚期458/479处于事件首次M段，20为M已知false后恢复、1为unknown后恢复，所以不能先假定多数是旧慢路径反复复活。保留F不会天然保留真正启动，可能被伤的恰是S-only启动。

## 3. 从原代码确认 CP 的含义

原 continuous-protection-lines-20261028/code/model.py 是纯市场模型，无账户导入。

设 p_t=log(C_adj,t)，r_t=diff(p_t)。原尺度来自前63个对数收益绝对值的中位数乘1.4826，底值1e−8；receipt尺度 z=max(s, log(1.001))，在anchor时冻结。成交额背景是前21日中位数。u=tanh(r/s)，v=tanh(log(amount/B))，量价倍率 m=1+0.5*abs(u)*v。只对超过已有frontier的新推进量累计 credit。receipt要求：当日有新的frontier推进，累计位移与累计credit均达到 sqrt(5)*冻结尺度。候选线 floor=C_adj,t*exp(−sqrt(21)*冻结尺度)。比较浮点边界继续采用原模型ge/gt，不新增容差参数。

这里“新高”严格指当前CP内部frontier的上穿，不是滚动20日高点，也不是本轮持仓最高收盘。SEEK状态下更低收盘会把anchor/frontier下移并冻结新的尺度；一旦receipt形成，phase进入UP，anchor/frontier重置为该receipt日log(C)，credit清零、尺度取当日值。此后只有超过frontier的收盘推进量计入credit，回撤、横盘或重新走到frontier但不严格超过都没有新推进。每次下一receipt又作同样重置。

尤其在UP状态，回撤本身不会降低anchor/frontier。若原持仓因sectorfalse、stock状态改变或融资退出，但CP自己的I链仍有效且没有原e0_down/source重置，CP并不知道“账户已失败一轮”；未来receipt可能仍需收复此前frontier，甚至再达到冻结尺度的累计位移/credit。这与被否证的旧H恢复门槛有真实的迟到机制相似性，可能同样晚于光伏/聚和启动，不能用CP术语替换就声称解决了旧H问题。区别是CP不依赖持仓盈亏/退出历史，且I无效或原e0_down可让其重新SEEK，在较低anchor形成低于旧账户H的receipt；两者并非恒等。究竟哪条重置在具体启动前已发生，需要逐时点本地证据，不在本设计里臆断。

receipt之后市场模型自己重置anchor/frontier/credit，与真实账户是否买入、是否消费CP无关。个股CP输入中的 e0_valid 实际映射原 i_target，不能误称“原行业E0独立又确认一次”。source segment变化、I无效、原e0_down及寻底状态沿原模型重置。不能把冻结CP模型在每次A/B时重新启动，那会变成第二个算法。

不重复的原因：
1. S是行业10/20日相对收益及10日绝对收益；它不保证该股出现receipt。
2. F的20日新高是行业内至少半数，不保证待买的该股属于那一半，也不等于其CP尺度阈值。
3. CP可以在尚未超过20日旧高时形成，F也可以为真但该股没有CP。条件有关联，非逻辑等价；关联程度需后续一次诊断，不在此先验断言。
4. 当前I为真/stock为真/A或B出生并不等价于一个新receipt。反之，CP本身使用I事实，所以它也不是完全独立的外生证据。
5. receipt确认日在signal之后，不保证其全部形成区间在signal之后。anchor、尺度、credit可能早于signal。若要求全部新信息，必须另起假设；本稿不偷偷加入 formation_start>=signal。

## 4. 三值公式及先后顺序

使用 T=1、F=0、U=−1；AND：任何F则F，否则任何U则U，否则T。OR：任何T则T，否则任何U则U，否则F。不得用Python bool(−1)或not F替代三值逻辑。

先按原规则判断票身份、I/stock/sector、事件状态、M与E、报价/因子/保护、容量和经济量。已知source变化或原I/stock/sector为false、I保护破坏优先取消。未知不可当false，也不可取得新的现金资格。未准入公司行动属于原经济阻断，不是本门槛的U。

对原始合法请求r，在当日真实phase基础上：
- kind!=SEED：本门槛不参与。
- phase=EVENT或RESIDUAL：本门槛不参与，严格保持原额度和优先级。
- phase=PAUSED或原M/E/事件条件不符：沿原暂停；不能用CP绕过。
- phase=MATURE且原M=1、E>0、事件ACTIVE、身份相符：G=OR(F, CP_state)。T才有成熟合法需求；F记STRUCTURE_WAIT；U记STRUCTURE_PAUSED_UNKNOWN。

在有效MATURE域内此式等价于 F OR (S AND CP_state)，因为M=S OR F且原额外rs5可知性要求仍已满足。选择较短式不放松M。若日志出现MATURE同时M!=1或E<=0，属实现一致性错误，不靠本门槛修复。

完整门槛真值表，行是F，列是CP_state：

| F \\ CP | T | F | U |
|---|---|---|---|
| T | T | T | T |
| F | T | F | U |
| U | T | U | U |

重要边界：S=T/F=U/CP=T可以通过；S=T/F=U/CP=F只能暂停，不能记“明确S-only结构不合格”。F=T时CP缺失/失效/未知不阻挡门槛，但原报价、source、I和公司行动检查仍全部必需。

## 5. 入场影子CP的生命周期

### 5.1 身份与最早观察

每张原始合格A/B票自signal CLOSE就维护独立entry_cp_shadow；不是等到首次被资金拒绝或后来转MATURE才开始。不改原票出生资格。不对未合格或已取消信号偷偷造票。

票身份继承 sid、birth_type、original_signal_day、origin=(source_kind,source_path,segment_id)、原nav0/budget/factor/ifloor及event_id。影子证据字段包括receipt_day、floor、source lineage、model_version、observed_at=CLOSE、最后已核OPEN/CLOSE、invalid、unknown_gap、superseded_by。receipt身份置于独立ENTRY_CP namespace，绑定sid、source、原确认日、原candidate、原CP模型版本；源文件哈希记录为provenance，不因文件以后追加未来行就改写过去receipt身份。

signal之前的receipt一律不能入本票。含signal当日的receipt可在该CLOSE创建。CP模型有完整历史暖机，但决策只能读到当日CLOSE，不用未来receipt或未来公司行动补证。

### 5.2 原单slot语义，不挑旧低线

复用原持仓CP的单slot更新顺序，而非从历史所有CP挑一条最有利的低线：
1. 先在当期已知OPEN/CLOSE对已有slot核破坏。
2. receipt显式为真、candidate有限正、源和调整尺度一致且当前C_adj>candidate，才创建或替换slot；旧slot记SUPERSEDED。
3. 新receipt当晚若C_adj<=candidate，记RECEIPT_ALREADY_BREACHED，不替换此前仍有效slot，等同原M3行为。按现CP公式正常应不会出现，可作异常输入边界测试。
4. 每次receipt不是“保护线只能抬高”。原新candidate可以低于旧floor；本稿不加candidate必须更高条件。
5. 若最新已创建slot以后破坏，不能回头找更老、较低但还没破的CP救资格；需等新receipt或F路径。
6. receipt=False只说明当日没有新receipt，不删除既存有效slot。

### 5.3 生效与失效的时间

receipt在d CLOSE形成，所以只核d CLOSE；不能倒用d OPEN来破坏一个当时尚未存在的CP。后续每个可观测交易日的OPEN及CLOSE，P_adj=raw_P*经原桥接验证的current_factor。P_adj<=floor（含相等）使slot永久invalid；价格后来回到线之上不复活。新有效receipt可替换失效slot。

与原引擎一致，未破仅指已核OPEN/CLOSE，不新增盘中low触发规则；不能声称全天最低价从未破或保证止损成交价。已知完整合规数据且无slot/slot已invalid为CP_state=F。已有slot未破且源、必需价格与receipt更新流完整为T。

当天receipt缺失/非布尔、receipt=True而candidate无效、报价/尺度或source未知，或slot以后存在不能核验的OPEN/CLOSE/receipt更新缺口，CP_state=U。保留slot原身份但不能仅靠恢复日价格在线上证明未知区间没破。完整缺口后来获得原源证据，只能按发现日更新知识；或者当日新的有效receipt建立新的可检验后缀，不能回写历史计划。

canonical模型明确输出ready=False且receipt=False时，它是模型明确没有receipt，不能伪造receipt，也不把这个已知False一律改成缺失。若旧slot仍可完整验证，单独ready=False不另设一个新门槛；原源链/I规则继续优先。缺行与明确False必须分开。

### 5.4 真实持仓严格隔离

成交时影子slot只留在订单审计字段entry_evidence_id，结束该票的影子生命周期；真实新轮保持cp=None、confirmed_history=False、add_count=0。该receipt不是已持仓验证，也不在SEED成交时消费原ADD receipt。真实持仓仍只能用receipt_day>=actual_seed_day的新收盘证据，经过既有CLOSE/nextOPEN净利、I、M、CP等检查后确认/ADD。实际SEED当天OPEN之后新形成的CLOSE receipt，仍可以按原规则参与真实持仓确认；这与前一日的入场证据不同。延迟SEED可能使原本可作为真实持仓后CP的receipt变成入场前证据，进而推迟下一次真正post-SEED CP/信息确认/ADD；这是本单因素经路径产生的真实机会成本，不能为保住赢家另改ADD规则。

## 6. 等待票、阶段迁移和取消

本候选需要显式STRUCTURE_WAIT，而不是删掉A/B信号并假设未来还有信号。原ticket_from_seed只为资金原因构造retained，不能假造cash_reserve拒绝把结构等待硬塞进去。应在新研究实现里增加独立的结构等待创建/转换入口，保持相同immutable identity；不能修改冻结helper的意义。

每天先按原规则更新：
- I/sector/stock已知false，I保护破坏或source已知改变：取消票并清掉该票影子；不能靠同时出现CP或F复活。
- 同字段unknown、缺报价、容量未知等：沿原暂停，保持原票、NAV、预算和事件身份。I为真且线有效时仍按原逻辑只上调I，即使其他状态unknown。
- 仅CP破坏：只失效影子，原A/B票不取消，继续STRUCTURE_WAIT/UNKNOWN；它没有持仓，不产生止损或亏损轮。
- 新receipt、F或阶段变化使原请求重新合法：只生成下一OPEN候选，不追补过去成交。
- 同股只保留一张live票；持仓后不得另生SEED。已取消票不能再生，未来新A/B才创建新身份，原receipt早于新signal的不能继承。

phase每天由真实事件和M/E重算：WAIT不能冻结为原EVENT，也不能人为保持MATURE。若M回到0且原事件仍ACTIVE，票可按原RESIDUAL小额规则请求，并绕过本成熟门槛。这不是全入场禁令，而是限制扩张额度；若禁止这条降级通路，就已经改变EVENT/RESIDUAL试仓哲学，属另一策略，本稿不做。

等待不限固定天数、不增加优先级奖励、不恢复事件的一次优先权、不重新锚定NAV或2%预算，也不清空已有event spent。已有市场CP可能一直不再产生，票可长期等候；这不是循环依赖，但是真实的饥饿/错过趋势风险，不能增加N日自动放行补丁来掩盖。

## 7. 股息、源身份和零仓位边界

所有live等待票即使当日不在购买pending里，也进入原经济preflight和quote-gap链检查。不得因新门槛更早筛掉请求而跳过其已知公司行动。

- 继承已准入的公司行动清单与原1e−11因子一致性校验，不因本稿新增事实来源或放宽准入。
- 纯现金除息在同源、旧新factor链完全匹配后更新current_factor。影子floor本来位于冻结连续调整尺度，保持原数值；不能再乘factor_new/factor_old做二次变换。新OPEN/CLOSE以raw*current_factor与其比较。
- 零仓位等待票record_qty=0、dividend_accrual=0；不能因为原signal早于登记日就获得股息权益或盈利缓冲。
- 已知source_kind/source_path/segment_id改变取消；未知source暂停，不把unknown字符串当新源，也不静默拼接两个源。
- 未准入公司行动、同源无桥接的factor变更或桥接不符，保持原原子BLOCK语义；不能把它改成CP_UNKNOWN继续认证。
- 缺报价时按原Q0暂停，恢复时核完整源/因子链并等待当日CLOSE后再计划，不能用恢复OPEN补成交旧计划。桥接已核只证明尺度连续，不证明缺失OPEN/CLOSE期间CP未破。
- 原有非PIT及公司行动事后核验限制完全保留；因果回放不等于生产时点可得性认证。没有发布时刻的本地receipt最多称当日收盘可计算。

## 8. CLOSE计划、nextOPEN和资金/优先级接入位置

### CLOSE固定顺序

1. 原source/经济知识与状态/保护检查、原退出识别。
2. 同步原sector event；新A/B出生或原票刷新，更新影子CP；原账户CP照原路径运行。
3. prepare_requests按原方式确定EVENT/MATURE/RESIDUAL、score、econ_q及事件身份。
4. 对MATURE新SEED应用本门槛；不合格请求登记wait/unknown诊断，但其合法q=0、cost=0、D=0。
M7原capped_water满足 sum(X)=min(max(0,free),sum(U))，其中U=K+D；W_alloc=E+max(E−E_prev,0)用于归一化相对分配，所有W同时正比例缩放不会改变X。因此本门槛在D形成之前改变合法需求，不是给E/W加一个绝对强度阈值。不能把相对权重大小直接解释为可证明的市场机会质量。

5. 只有合格MATURE请求进入M7 independent_mature_demand。随后仍按原capped_water、M5 W_alloc、EVENT预留、ADD优先、代表排序及融资需要计算。不能先把等待请求计入D再在最终买入时删掉，否则会虚增目标并卖出不必卖的donor。

### OPEN固定顺序

先原经济preflight/股息会计/已锁退出；原info_open确认不变。对上个CLOSE冻结的F、phase、计划CP身份做OPEN重核，再进入资金迁移的receiver需求检查与实际买单检查。不能OPEN重算当日F或读当日CLOSE receipt。

- 冻结F=T：本门槛仍通过；即使影子CP破位或unknown，也继续完整原SEED检查。
- 冻结F!=T且靠CP通过：同一证据必须仍有效，OPEN_adj>floor；若<=floor，永久失效，拒绝本次购买并回STRUCTURE_WAIT（F=U则门槛U）。不能用今日晚些的receipt救这笔OPEN单。
- OPEN也<=原I：原保护取消优先，不仅等新CP。
- 跳高可通过结构但原预算、现金、费用、容量、dated lot、冻结planned_q、限价/一字板或其他执行门槛仍可拒绝；不追价扩大原预算。
- 仅本新结构门槛的OPEN失效要有专用结果处理，不能落入原retry_open_outcome的“非资金拒绝一律取消”而误删等待票。其他原非资金拒绝保持原语义；原纯资本拒绝继续retained，不重置CP。
- 在donor融资前和实际买单前都必须用同一个门槛校验，防止无有效receiver却先卖出donor；不改donor排序或添加新资金来源。
- READY不预留永久现金。重新READY仍按当日原排序竞争，既不跳过ADD，也不按CP年龄、等待时长或旧亏损提升排名。
- 一个日内发生原子BLOCK，新增影子、wait状态、身份、日志也要完整snapshot/rollback，连同原event/现金/订单一起恢复；不可只回滚订单而留下未来证据。

## 9. failure history的准确语义

本候选不建立收益失败历史。没有old_high、亏n次暂停、亏损累计占用他股风险预算，也不从未来最终marked_net推断当日资格。

必须区别：
- 结构等待/CP失效/身份取消：零仓位资格事件，不是一次已亏损交易。
- 已有持仓I/CP/sector保护退出：真实成交和已知权益按原会计记录，原因保留。
- CURRENT_NON_MAINLINE_SEED_RETIREMENT、NON_MAINLINE_EXPANSION、MAINLINE_EXPANSION_SURPLUS：原融资迁出，不因当时净负就贴“结构失败”。
- 新A/B票出生：是否允许仍由原事件逻辑和此处当时结构决定，不受旧轮本金盈亏影响。
- 晚到股息或会计修正仅按发现日处理，不改过去等待、通过或取消决策。

## 10. 可反证点与不成立的强解释

以下强解释已不能成立，不能把候选包装成它们：
1. “只让被市场单独确认的个股进成熟阶段”：F通路并无该股CP，所以不成立。
2. “原信号后全部是新增个股信息”：receipt可能沿用信号前anchor/credit，所以不成立。
3. “确认保护线即可避免本金亏损”：OPEN跳空、费用、后续亏损和原I线仍使本金承担风险，所以不成立。
4. “没有CP的MATURE都是劣质迟到票”：9/24和10/24真实主线中的大批S-only说明必须逐票验证，不能从晚期合计亏损推断。
5. “原MATURE无ADD已经缺少试仓退出”：原trial sectorfalse/M0融资机制已有，不应再加一个重复退出。

本假设的窄可反证标准：在原决策时点，它必须确实产生与原门槛不同的资格集合；同时必须把真实主线启动中的延迟、永久取消和买入价恶化作为首要成本，而非只报被挡原亏损。若新增证据在同日几乎必然存在，门槛只是重复；若大量真主线被延迟而晚期坏轮同样有CP，该假设缺乏鉴别力。没有任何本金或盈利硬保障承诺。

后续若获准只做一次描述诊断，应预先报告9/24的28个MATURE、9/23—9/30全部启动、10/24光伏30个MATURE、10/23—10/29光伏固定机会集合、全窗和晚期，并保留closed/open分层。固定窗口均按实际OPEN交易日，不能混入相应计划CLOSE窗口；光伏沿原“光伏风电设备”行业。固定机会集合取原基线该窗全部实际SEED轮，不按后来盈利、ADD或知名赢家筛选。

若另行批准账户候选回放，必须同时报全账户现金闭环结果，以及上述固定机会集合按原票身份的捕获比例、截至原窗口末的捕获比例、延迟交易间隔、等待后首次合法/实际入场的同尺度价格差、因原false取消和期末仍unknown/wait的比例；实际成交捕获与只有候选可恢复要分开。还应披露延后post-SEED CP/ADD及融资迁出的影响。不得以“还抓住至少几个赢家”或“不是所有赢家都错过”作为验收条件。逐票标明signal、F/S知识、CP形成区间/确认日、门槛、最早可恢复CLOSE/nextOPEN、取消/unknown原因和原成交价差。原路径净损益只是机会成本对照，不能当过滤后的账户净增益。描述诊断不能宣称重分配资金、后续ADD、融资迁出或反事实NAV已验证。

本稿未运行这些诊断。若同目录外后续出现描述结果，不修改本稿条款择优。是否进入独立候选实现/一次账户回放仍需另行决定。

## 11. 最小测试清单（未执行）

1. 9格OR真值表；S=T/F=U/CP=F必须U；F=T/CP=U必须T，原M/E不符永不通过。
2. kind=ADD与EVENT/RESIDUAL门槛旁路，原决定、排序及预算一致。
3. signal之前receipt拒绝、signal同日有效receipt接受；不运行严格>第二版本。
4. 当日OPEN低于新receipt floor但CLOSE在线上：新证据成立；下一OPEN才检查。
5. 后续OPEN或CLOSE等于floor永久失效；后来价格反弹不得复活。
6. 新有效receipt替换旧slot；新floor较低仍按原语义接受；不挑历史更低slot。
7. 新receipt当晚已破不替换仍有效旧slot；receipt=True但candidate无效为U并留异常证据。
8. receipt=False保留旧slot；缺receipt行不补False；已知unprepared/False与缺失分开。
9. 未知价格/更新缺口使CP=U；恢复单根价格不追认未破；新有效receipt可建立新的可核后缀。
10. I/stock/sector任一已知false优先取消，即使同日F/CP为T；unknown不重生。
11. EVENT初始资本拒绝后转MATURE时，保留signal以来CP，而非从MATURE才启动观察。
12. MATURE→RESIDUAL仅回原小额机制，不再借成熟额度；再转MATURE重核G。
13. 同源已准入纯现金factor桥接，floor保持连续尺度、q0权益始终0；双倍调整必须失败。
14. 缺桥接/未准入行动保持原BLOCK；source变化取消，不借CP通过。
15. 缺报价恢复OPEN不补旧单，只有恢复CLOSE新计划可在nextOPEN执行。
16. OPEN跌破CP但未破I：仅结构等待；同时破I按原取消；冻结F=T旁路CP不旁路I。
17. OPEN跳高造成超预算、dated lot变化、容量/一字板等原拒绝，全保持原执行语义。
18. WAIT/UNKNOWN的D=0，不为其规划donor；OPEN失效receiver不触发虚假融资卖出。
19. 结构等待的票在现金充足时也能存续，不能伪造“资本拒绝”取得retained身份。
20. 原NAV/2%预算、原signal/event_id、event spent/priority、代表排序不因等待重置；重复调用不重复造票或花钱。
21. 等待中出现第二个A/B不得并行造同股重复票；取消后的新票不能复用新signal之前的旧CP。
22. 成交后active.cp=None、confirmed_history=False；实际SEED日新CLOSE receipt仍按原持仓规则处理，不把入场receipt消费为ADD。
23. 原子异常后新增所有状态/日志与现金/订单同步回滚；重放同一天结果幂等。
24. 合成慢推、跳升后横盘、永不再生CP路径：不依赖持仓生成receipt，允许长期等待，不加超时放行。
25. 对两个未来完全不同但截至t输入相同的合成前缀，门槛/票状态/证据身份必须相同；当日CLOSE证据不得用于当日OPEN。
26. 同一候选新旧数据文件只追加未来行，过去receipt身份/决定不改变；源文件hash是provenance而非随追加重生的证据ID。
27. 关闭本新增门槛时，与原候选所有经济执行方法等价；开启时差异只来自资格/等待及其后续资金路径，不能混入新退出或本金约束。

## 12. 已检查的本地源码定位

- mainline_seed_entry_diagnostic_v1/READOUT.md：已知否证与真实SEED/retained说明。
- mainline_candidate_v1/engine.py:20—52：M/S/F/Q三值公式；122—138：信息确认；355—362：retained刷新。
- mainline_candidate_v3_core_reference/engine.py:53起：真实持仓CP创建、净利检查、次日执行；成交时新SEED真实cp为空。
- mainline_candidate_v4_known_sector_fix_v2/engine.py:29—45、89—112、142—177、214—248：事件身份、phase、经济量/排序、资金及一次优先权。
- mainline_candidate_v5_expansion_competition/engine.py:13—35：MATURE SEED=EXPANSION、W_alloc、原融资角色。
- mainline_candidate_v7_demand_capped/engine.py:43—95：独立合法需求D与目标封顶。
- allocation_ablation_v1/allocation_rules.py：immutable identity、False取消/Unknown暂停、原资本拒绝保留范围。
- mainline_candidate_v2_pending_quote_pause/engine.py:50—100：Q0缺报价、原源/因子桥接、恢复后等待CLOSE。
- joint51_candidate_v9_facts/engine.py:124—151：cpvalid、OPEN/CLOSE失效与factor桥接；只读定义，未实例化loader。
- mainline_m7_cash_batch_design_v6/engine.py：当前既有基线的准入/执行继承关系；只读代码，未调用其中PDF/CNINFO验证分支。
- 原CP model.py、case-stock-cp1-warmup-20261031/generate.py:frame、universe-cp1-inputs-20261031/prepare.py与PROTOCOL.txt、cp1-evidence-trace-20261031/trace.py：原CP数学、I映射、连续暖机/前缀和receipt身份。

SOURCE_HASHES.json记录实际读取的设计依据。此交付是设计合同与审查，不是已实现或已通过的策略。

## 13. 实施前状态与未决点

公式、日期包含边界、单slot更新、OPEN/CLOSE失效、三值逻辑、phase降级、无持仓利润约束、原ADD隔离均已明确，不保留多版本让结果择优。

尚未完成而必须如实区分的工作：
- 未创建候选引擎，也未执行上列合成测试。获准后只能在新独立目录实现，以本合同为唯一参数/语义来源，完成合成与原规则旁路等价核验后再申请历史执行。
- 当前本地资料并不提供所有市场receipt的真实发布时刻，继承not-PIT限制；不能升级为实盘可执行性证明。
- 实现必须逐入口检查M7合法需求与OPEN receiver融资校验均接入新门槛，并把所有新状态加入原子回滚。只在最终BUY分支加一行if并不满足合同。
- 原终点缺下一交易日时，只能输出待定票/未执行计划，不虚构nextOPEN、自动清仓或取消。
- 本稿没有给“可接受牺牲多少主线捕获”的事后收益阈值，也不据晚期净亏推导阈值。先完整展示固定机会成本与全账户结果，再判断假设是否值得继续，不能边看结果边修公式。
