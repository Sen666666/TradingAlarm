# 2022-01-05 原PVR首日52只：买入信号与行业先验追踪

## 范围与结论

本审计仅读取原PVR的2022-01-04 CLOSE决策、2022-01-05 OPEN成交及既存日线事实。没有重跑账户，没有更改策略，没有用未来收益筛选或补写当时信号。原数据属于固定1709股研究池，历史可交易性UNKNOWN、公司行动条款假定预知，因此这是原回放的日线因果证据，不是完整PIT实盘可投资性认证。

- 1月4日收盘产生421条意图：259 core、162 mobile，去重294股。
- 1月5日开盘真正成交52股：原始成交journal为3 core/probe与49 mobile/confirmed。
- 三只core：002246.SZ、000999.SZ、002603.SZ。不能把1月5日收盘全部confirmed的快照回填为成交pool。
- 52股的E0与I结构均已在2021年开启且当时仍有效。51股有1月4日I_buy新机会，300182.SZ没有当天I_buy或G fresh_up，但I仍有效，加上当日CP1，mobile_Q通过。
- G等级：46股为4/扩张、2股为3/热、4股为2/暖。G是个股指标；原行业入口未计算或使用G1/I。
- 52股当日均有CP1收据，但只有49只实际mobile订单消费CP1。三只core虽有收据，也不能把其成交理由改写为CP1。
- 49只mobile中48只先试core，因probe_risk等拒绝后，才走mobile/confirmed；300182只有mobile候选。mobile在此原策略不要求先持有该股core，所以空仓账户首日可以直接建立mobile仓位。
- 25行业的E0及当前attempt都起源于2021。2021末为21 expanded、4 confirmed；1月4日为24 expanded、1 confirmed。行业先验不是空白启动，也不是“整体牛市”标签。

## 交付文件

- FIRST_DAY_52_SIGNAL_EVIDENCE.csv / .json：52股逐行信号、E0/I起点、G证据、CP1形成与确认日期、保护线、H1/PVR两种排名、实际成交角色/pool、相关行业先验。
- FIRST_DAY_52_ORIGINAL_RECEIPTS.json：每股原fill、intent、opportunity、rank、funding、CP1收据和行业证据的逐单对应。
- INDUSTRY_25_PRIOR_TRACE.csv / .json：25行业独立追踪，含2021末stage、1月4日stage、E0/attempt起点、原事件确认日与pivot日。
- CHECKS.json：核验结果；SOURCE_SHA256.json：所读取源文件哈希。
- trace_first_day.py：可复核的提取程序，仅在本审计目录写输出，不导入或运行账户引擎。

主表可以按sid与名单/金额/最终结局表连接；本表未写任何未来盈亏字段。rank及candidate_slot均为原代码0基序号；展示人类第几名时加1。priority_rank保留原候选H1数值槽位的间隙，PVR_candidate_slot才是候选稠密顺序。

## 指标与原执行链

### 1. E0：原量价转折事件维护价格结构

来源：pv-strength-b5-20261025/code/evidence.py::_event_facts 与 policy.py::e0_policy，native-I-cache-interface-20261031/cache.py::derive。

令r_t=ln(C_t/C_{t-1})。原E0事件尺度不同于PVR/CP1：sigma_t=max(sqrt(mean(前63个r²)), 1e-8)，量基准为前21个有效volume中位数。当前腿极点为a，方向d∈{-1,+1}；从极点后至t的平均volume除以极点已知量基准，再开平方并截到[0.5,2]，得到activity。确认值为：

confirmation = (-d) × ln(C_t/C_a) × activity / (sqrt(5) × sigma_a)

确认值达到1时，在当天产生event=-d，记录此前极点价格与极点日期。事件当天才是可观察日；pivot日不是当时就可交易的信号日。每段来源历史单独暖机。

E0先检查已有保护线：C<=floor则退出。event=+1时，若原来有效，floor提升到max(old floor,pivot)；若原来无效且当天未先退出，则开启E0，floor=pivot。本链显式decline_candidate=False，因此没有pending reclaim增强入口。

### 2. G1：非补偿分级，不是简单涨幅或均线打分

来源：pv-strength-b4-20261025/code/model.py，b5-g1-20261025/code/grade.py。

G的底层尺度s=max(1.4826×前63个|r|中位数,1e-8)。mu5与mu21为收益r的EMA，alpha=2/(h+1)，从首个收益暖机；z5=sqrt(5)mu5/s，z21=sqrt(21)mu21/s。

S21/S63是事件锚定方向。每个候选冻结锚点、sqrt(h)×s阈值和前21量基准；只对当日方向收益为正的新价格前沿累计位移与量权credit，量权为clip(sqrt(V_t/V_ref),0.5,2)。新位移和credit同时越过阈值才确认方向，并重置对向候选。

acute的qeff=(r/s)×sqrt(clip(V_t/median(前21 V),1,4))，qeff>=2为acute_up，<=-2为acute_down。

G proposal按以下顺序形成：
1. S21=S63=0为0；
2. mu21<0且mu5<=0：若双尺度都向下为-3，否则-2；
3. mu21<0但mu5>0：S21向上为1，否则-1；
4. mu21>0：双尺度向上为3；仅S21向上为2；否则mu5>0为1，其余-1；
5. mu21=0按mu5方向给1/-1/0；
6. 双尺度向上且z5、z21都>=1则为4；
7. acute_up且同日E0新up事件、mu5>0时，至少为2；
8. z5<=-1至少降到-2；acute_down覆盖至不高于-3。

向上升级还必须有fresh_up：当天E0 up事件、S21或S63新向上确认，或已确认S21上行结构出现新价格前沿。无fresh_up的升级冻结到旧grade，下调不受此门限制。主表保留当时缓存的G_phase、G_up_reasons、z5/z21，而不从未来走势反推等级。

### 3. I：E0之上的个股入场状态

来源：b5-g1-20261025/code/policies_g1.py::project(kind='G1_I')。

warm = G ready 且 grade>=2。
opportunity = E0有效 且 warm 且 (当天E0新开启 或 fresh_up)。

I在未激活、未当天先退出时因opportunity开启。I已激活时，只因E0失效或价格<=旧I floor退出；G1_I没有冷状态退出开关。保持有效时floor随E0 floor单调提高。i_buy=I有效且opportunity。因此“当天i_buy”可能是已有2021结构上的新证据，并不等于当天结构诞生；I有效也不保证当天有i_buy。

S0 Q还检查已知可买、ready、公司市值>100亿、stock_up、发行人/行业已知、个股原rank已知、行业当日可观察且E0有效、行业原rank已知。core_Q将buy_allowed与当天i_buy相与。mobile_Q将buy_allowed换回市场可买，仍要求存续I以及其他Q门，所以可无当天i_buy但有当日CP1。

### 4. CP1：新前沿收据，不是“当日上涨”布尔量

来源：continuous-protection-lines-20261028/code/model.py。

s_t=max(1.4826×前63个|r|中位数,1e-8)，z_t=max(s_t,ln(1.001))，B_t=前21日amount中位数。
u=tanh(r/s)，v=tanh(ln(amount/B))，m=1+0.5×|u|×v。

每个CP段冻结锚点a及尺度z_a；仅价格超越已有前沿时，fresh=log(C_t)-old_frontier>0，credit增加fresh×m_t。receipt必须同日有新前沿，且累计价格位移与credit均>=sqrt(5)×冻结尺度。candidate=C_t×exp(-sqrt(21)×冻结尺度)。

收据后重置anchor/frontier为当前价格，credit=0，冻结新尺度。E0无效清空；E0 down事件重置SEEK；SEEK下探新低重置锚点。形成起点是formation_start_exclusive，不是确认日；confirmed_day才是该收据可观察日期。本表49张实际使用收据均严格匹配原订单CP1_id，均在1月4日确认；形成日期均早于确认。

core保护线为I floor；mobile保护线为max(I floor,CP1 candidate)。表内adjusted保护线与同域close比较；raw保护线以信号日factor除回。不能把复权floor直接和原始价格比较。

### 5. PVR：只替换候选顺序，未发明新入场信号

来源：pvr-current-v3-information-capital-20261101/original_score_function.py 与 pvr-slot1-native-readiness-20261101/native_rank.py。

r=ln(C/Cprev)，s=max(1.4826×前63个|r|中位数,1e-8)，B=前21日amount中位数；
u=tanh(r/s)，b=tanh(ln(amount/B))；
e=u×(1+0.5×|u|×b)；
E为最近21个e按0.9衰减并归一加权；
PVR=50+50×tanh(2E)。

invalid/source change重启准备。PVR按descending round(score,12)重排可用分数候选，同分保留原候选顺序，未知PVR保留原槽位；同股core在mobile之前。意图中的score仍是原H1分数，不能将trade.pvr或intent.score当作真实PVR。真实值用PVR_score，原H1用score与original_H1_rank；主表已与rank-policy逐股完全核对。

### 6. 行业先验与容量：市场状态继承，空账户重新建仓

来源：industry-mobile-stage-20261031/stage.py 与 case-stage-ledger-20261031/v3/joint_v3.py:Runner.__init__/industry；native_adapter.py/component.py及route_without_account_check.py。

行业原输入是E0价格结构，不是行业G/I。行业CP1首次新收据启动probe，第2张不同新收据confirmed，第3张expanded，之后保持最高stage但可替换授权。E0失效、来源/episode变化或价格触及旧行业移动保护线，先终止attempt，当天新CP1不能同日重启。

连续账户开始前，代码读取START前最后行业状态，继承E0 episode、当前attempt、stage、最新证据时钟及已消费收据。它只要求账户无lots、无orders，并未把市场状态清零。25行业E0可观察起点是2021-03-16～2021-12-03，当前attempt首probe日2021-10-25～2021-12-27。

1月4日仅URFI881143、URFI881151、URFI881160从confirmed升expanded。URFI881263仍confirmed，其余24行业已expanded。不能写成“所有行业都是1月4日当天确认转强”。

原路由core仅走probe；mobile在行业financial level>0且可迁移时可走confirmed，择最大合法股数，股数相同优先probe。保留的约束包括10%现金、probe总资本10%/总名义风险0.5%、probe行业资本2%、confirmed行业资本10%或expanded20%、行业风险1%、单股资本10%。该PVR版本明确删除confirmed全池60%资本约束，也不施加原全账户风险总闸，因此不能用“总仓位本应60%”解释首日高仓位。

同一OPEN先为所有候选排序/预留，再按该顺序实际fill。前3只core预留很快占用probe风险，使后面48只core路径至少因probe_risk失败；它们的同日CP1 mobile路径仍可用confirmed容量。此处“confirmed pool”不等于每只股票已经有两次或三次CP1确认，升级依据来自所属行业市场attempt。

### 7. pool时间切片

journal real_buy_fill保留实际订单的pool。随后fill_buy的延迟cancel_ack会调用Contract.migrate；满额成交且该行业不再存在probe待单时，可在同一OPEN把lot容量归属迁到confirmed，股票数量/成本不变。

因此可证：
- fill记录：3 probe +49 confirmed；
- 下一份已存日结快照（1月5日CLOSE）：52 confirmed。

没有单独的池迁移时间戳审计，所以不把日结快照等同于“收盘才迁移”，也不使用1月5日收盘行业信息解释1月5日开盘买入。

## 日期与复核边界

所有入场解释仅使用截至2022-01-04的事实；2022-01-05 CLOSE只用于另列pool快照，不进入入场信号。事件observable_day表示当日收盘确认；pivot_day与CP1 formation_start_exclusive只是先前价格极点/形成起点。源收据明确不提供真实逐笔发布时间；这里采用原回放15:10 CLOSE与次日09:30 OPEN约定。

本次只提取既有事实和收据，不重新优化指标，不回填未来收益，不改原结果。CHECKS中的source_declared_hashes_verified核对选中来源的原冻结manifest，all_original_sources_unchanged核对本审计前后读取的源文件字节。
