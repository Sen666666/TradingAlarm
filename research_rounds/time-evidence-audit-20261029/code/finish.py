from pathlib import Path
import sys,json,importlib.util,datetime,time
O=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/time-evidence-audit-20261029');sp=importlib.util.spec_from_file_location('time_finish',O/'code/audit.py');S=importlib.util.module_from_spec(sp);sys.modules[sp.name]=S;sp.loader.exec_module(S);H=S.H
summary=H.read(O/'diagnostic/summary.json');daily=H.read(O/'diagnostic/daily-summary.json');verify=H.read(O/'diagnostic/verification.json');agg=H.read(O/'diagnostic/aggregate-verification.json');plan=H.read(O/'RUN_PLAN.json')
contract='''时间确认最小实验合同草案：低时间分散首次机会，立即/同钟等待/同钟确认
状态：待审查，当前未实现、未运行经济路径。只有一个新增时间条件，不扫3/5/7日或其他阈值。

诊断支持的问题
原E0首次建态约20.7%在低点后一个有效观察确认；首次合法I机会约13.9%如此，35.1%的记录前沿有效贡献数不足2。原I已过滤部分冲动，但没有保证时间分散。87.6%的I信号是同E0内刷新，不应把所有刷新都再等一周。当前要检验的是低时间分散的首次资金参与，不是强迫每次新高重新排队。

唯一候选及机制根据
对每个E0机会的原合法I事件，使用当时最近已确认的E0上行枢轴，计算从该枢轴到信号日的记录价格前沿增量 f_j；回落/横盘不产生重复信用，允许它们存在。N_eff=(sum f)^2/sum(f^2)。2表示至少“两次等量推进”的有效贡献，不是两根红K、不是多数股必须连涨，也不保证两次贡献就是真趋势；该自然最小复数界限只检验一次。
若起点已有N_eff>=2，三臂当日完全沿原I，不新增等待（当前首次Q约64.9%属于此类）。仅不足2者进入等待研究。
等待窗固定5个该股有效C/V观察，包含起点，截止第5个收盘（t0+4）；5只取现有G1短节奏span5的单一尺度作为研究约定，不冒称由公式推导最优天数，也不是“必须连续上涨一周”。停牌不推进该股观察钟。

三臂与共同条件
A：原I，立即提交原日单；只读复用实验一I控制并核对身份。
W：对低N_eff起点保存意图，无额外时间证据筛选，固定到t0+4按共同继续资格提交日单。
T：同一固定起点、同一t0+4截止时钟；仅当从起点已知枢轴（窗口中冻结，不借未来新枢轴换锚）至截止的N_eff>=2时提交，其余结束该意图。
W/T等待中同样要求原I/E0及来源存续；原结构失效即取消。截止必须满足当日非“新买事件”的原证券/行业/行情/排名准备资格、I结构及G1暖资格；不要求截止恰好又有一个I新事件，否则把等待和新触发混在一起。两臂使用截止当时相同原I支持及合法股数/预算。这里“单纯等待”仍遵守共同合法/结构条件，不等于买失效股票。
两臂收盘决策后下一可执行开盘，日单于指定执行日收盘失效；不能无限等成交。未获准、取消或零成交意图结束后，只能用随后另一个有效观察中的新原I事件重建，重新判断当时N_eff，不能消费同一信号/每日滚动续期。T首次不通过不是永久删除该股；后续可有合法晚参与。每E0同时最多一个待确认意图，首次实际入场后不再新增该单元仓位。

单位、边界与成本
保持原5349共同E0机会（5169新起点、180 carry-in），不因成交/闭合换分母。无Q的1290个机会三臂都是同一份现金未启动，不称算法失败；它们与“匹配不到对照”不同。每机会独立同额100万元、全成本/双成本，原I/E0退出；没有共享现金、ACT、排序竞争、S1.5、F、CP1/PVR新条件。不外部注资、不重置实际持有本金。
这是原I/E0首次参与机制；原退出下各段自然失败全部计入，等待/零成交/重建意图全记录。被F/ACT强制提前卖出后的同段真实资金重试不在此轮，不能冒充完整组合。末端未确认意图列待确认，不叫永久过滤；已持仓和应收权益全部估值入主账。

主效应与必须拆分
主指标：T−A、W−A、T−W的全部共同事件等额净贡献，已实现/期末持仓/待收分列；尾部沿任一比较边净收益率>=30%及连续贡献分布，普通与全部负损耗都报告，胜率非门槛。
W−A包含等待导致的入场价格、资格失效和执行路径影响，不能全称“新增信息”。T−W先看首个共同窗口同一时钟下的信息筛选；后续意图重建会产生额外参与路径，须单列，不能把全部总差都叫纯信息收益。
复用S实验的派生静态诊断：以W首次实际入场对应意图的当时规则，若T时间证据会通过则复制W全账，否则记该派生臂不入场。它只用于“当次拒绝省损失/丢正收益”的诊断，不是实际T政策，不另跑第四资金臂。精确列出(T−W)=(派生静态筛选−W)+(真实T−派生静态筛选)，第二项含后来恢复/改变参与，不能按实际事后确认天数反配一个等待组。

频率与容量验收
报告全部原I/Q信号流保持多少、标准化首次机会流、等待队列、准入/日单/实际成交及同段意图重建次数。候选均值/分位/同日峰值及拥挤日期都列，独立资金诊断不因没钱减少交易。原35,316信号不可当作35,316次开仓；减少首次单元成交也不直接等于真实组合容量改善。持仓收盘数、实际投入及资金占用同列，不机械年化。

正确性与经济裁决
先无收益核验固定观察钟、冻结枢轴、无滚动延长、日单失效、G1/原I条件、来源/停牌/权息前缀与对照身份；固定样例通过后全量计算<=300秒，复用现有索引/执行/核账。开发计划15分钟作为实施目标、单独计时，超时先报告瓶颈不扩框架；不安装依赖。
已有充分时间证据者三臂须逐笔一致；W/T相同起点窗口须截止同日；费用现金/股数/NAV及全失败、各分解精确对账。
T相对A的净价值、尾部覆盖与成本稳定性是主裁决。若只有少开仓而尾部损失更大、或W已解释改善而T无信息增量，不晋升时间筛选；混合符号如实报告取舍，不以胜率或信号变少通过。若T有价值也只支持这条窄时间条件，不证明最优5天/必不漏肥尾。失败或无识别就收口，不加3/7天、连涨数、量能或更强阈值补救。
'''
(O/'TIME_CONTRACT_DRAFT.txt').write_text(contract)
report='''E0/I时间积累审查：只诊断，经济路径0

代码事实
1 当前E0-NR1：原事件核以低点到当前的净对数位移，乘相对量参与（区间均量/枢轴前21量中位数开方，截0.5—2），除sqrt(5)×枢轴时过去63收益RMS尺度确认。63/21是历史估计，sqrt(5)是位移尺度，没有最少经过5/21/63天的要求；大幅单日波动可直接达标。先检旧支持失效、再收新事件；新上行事件可建态或抬支持。
2 NR1在desk/refresh.py prepare_facts把decline_candidate置False，关闭独立“高参与下跌后收复直接建态”。原上行确认、B4/G1证据及正常快启动保留；不能把当前单日启动误怪已关闭的收复通道。
3 G1并非没有历史信息：5/21 EW净节奏、21/63前沿位移与量信用、63尺度与21量参考，升级须有新凭据；这些跨度均不等于最少历时。grade.py的acute_up且新E0事件且mu5>0可把不足暖的提案直接升暖，包括mu21尚不正。I entry-only以E0存续且暖且(E0刚建态或fresh_up)给买事件；fresh_up还含新S21/S63确认或已确认上行结构中的新价格前沿。I可在已经参与时重复发buy_event，实际是否再买由资金/持仓消费者决定。
4 CP1有新前沿信用，PVR有21观察加权；同样没有多天最小确认承诺。原I并未用PVR分数作持续性准入。已有S1.5只放大双向摆动尺度再与原I交集；旧W23/W2H/C3是等级迁移，C3不是三天，W3/W10是意图延续而不是三/十天趋势证明。不能重复命名为时间确认已验证。

量化口径
只按当时数据、全407股统计，不用未来收益/多倍股分组挑规则。枢轴到信号间，只给严格新价格前沿增量f_i记推进信用，回撤/反弹重走旧路不重复累加。N_eff=(sum f)^2/sum f²，最大单日占比=max f/sum f；>50%只是“单日过半”的描述边界，不直接入场规则。低点后1观察确认、只有1个推进日、最大占比和有效天数分别报告，不能把所有跨阈值当日的必然作用称单日主导。I刷新用其当时最近已确认的E0上行腿，不把结构真实年龄混成该腿年龄。

全样本结果（2023-12-29—2026-10-27，完整更早历史准备）
新E0建态5169：低点后1观察1069（20.7%），仅1前沿推进日1077（20.8%）；有效推进天数中位1.995，单日贡献过半3547（68.6%），触发日贡献中位50.1%。另有180个跨期存续E0，共5349原机会，全部列入生命周期表。
首次原I买事件4375：低点后1观察854（19.5%），有效天数中位2.291；不足2有1928（44.1%）。
首次完整合法Q机会4059：低点后1观察566（13.9%），仅1推进日571（14.1%）；有效天数中位2.611，不足2有1425（35.1%），单日贡献过半2078（51.2%）。G1和实际资格已过滤一部分单日启动，仍有明确的时间集中缺口。
全部原I事件35316：首次4375、重复30941（87.6%）；重复事件的结构年龄中位24观察、有效推进天数中位3.973，触发日贡献中位14.9%。因此不能把全部I刷新都解释成只涨一天就新开仓。
首次Q的暖龄中位1观察、3823（94.2%）刚进入这次连续暖状态；这表示暖状态没有被强制等待，并不表示此前只读了一天行情。原G1原因缓存可读的首次Q中有2169个fast_launch，其中609个z21<=0，显示快速例外确实存在；最新3交易日24个首次Q的原因字段未知，不能填造。原I所有原因未知121个；核心E0/I及前沿统计仍覆盖全期。
5349原机会中974没有I事件、1290没有完整Q；不能把无资格当资金拒绝，不能从统计里删除。

候选密度与真实开仓
681个市场收盘，全部Q共32899，中位31、p95为146、峰值362（2024-10-08）；首次Q流共4059，中位2、p95为22、峰值143（2026-04-08）。原I全信号中位35、p95为149、峰值362；新E0建态峰值224（2024-02-06）。候选集中会影响配置，但成熟结构刷新占多数，缩减原始信号不等于按比例减少真实试错或解决容量。

判断与唯一待审方向
用户的观察部分成立：公式没有最低历时，首次机会中单日/集中推进并不少；历史窗口不能当多日右侧已证明。但大多数每日I信号已有较久结构背景。优先仅检查首次资金参与中N_eff<2的低分散机会；已有N_eff>=2者不新增等待，不给所有I刷新排队一周。提议三臂立即/同钟纯等待/同钟分散确认，固定5观察只借现有mu5尺度作一个研究约定，详情TIME_CONTRACT_DRAFT.txt。不是连续红K规则，也不预设减少交易能保住肥尾；正负需未来受控实验裁决。

核验与预算
没有重算全B4/G1或新策略；只补原纯E0事件缓存，验证NR1建态必须来自原上行事件、全部I买事件定义精确，旧G1 grade/fresh/acute_down缓存前缀逐值一致。8股样例0.627秒、全407诊断13.827秒，低于120秒；样例全量一致。全部5349机会、首次/重复拆分、35316原I和32899原Q对账，1231输入SHA不变。开发/阅读与计算分开：RUN_PLAN从实现记录阶段开始计墙钟，先前代码阅读未单独计时；实际阶段耗时见COMPLETION，计算及核验日志另列。经济/新交易策略路径0、交易账户0、产品更改0；最新G1原因字段缺口明确保留，不为补它扩重算。

源码入口
TradingAlarm/desk/refresh.py:prepare_facts
research_rounds/pv-strength-b5-20261025/code/evidence.py:_event_facts
research_rounds/pv-strength-b5-20261025/code/policy.py:e0_policy
research_rounds/pv-strength-b4-20261025/code/model.py:run_valid
research_rounds/b5-g1-20261025/code/grade.py:classify
research_rounds/b5-g1-20261025/code/policies_g1.py:project
research_rounds/ix-a-share-entry-20261025/code/entry_rules.py:events

产物：ROADMAP.txt、TIME_CONTRACT_DRAFT.txt、diagnostic/summary.json、daily-counts.csv、daily-summary.json、all-5349-opportunities.csv、event-timing.parquet、source-checks.csv及核验。本轮止于路线/诊断/待审合同，不自动执行。
'''
(O/'DIAGNOSTIC_REPORT.txt').write_text(report)
elapsed=(datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(plan['implementation_clock_started_at'])).total_seconds()
H.save(O/'COMPLETION.json',dict(status='route_and_diagnostic_completed_contract_pending_parent_review',economic_paths=0,new_policy_runs=0,product_changes=0,accounts=0,blockers=[],known_field_gap='G1 reason/phase cache ends2026-10-22;121 rawI/24 firstQ at latest3 sessions unknown, full E0/I diagnostics included',inputs_unchanged=1231,first_Q_low_neff=1425,first_Q_total=4059,core_diagnostic_seconds=verify['seconds'],sample_seconds=H.read(O/'sample/verification.json')['seconds'],aggregate_seconds=agg['aggregate_seconds'],implementation_stage_wall_seconds=elapsed,development_plan_minutes=15,earlier_reading_not_timed=True,roadmap=str(O/'ROADMAP.txt'),report=str(O/'DIAGNOSTIC_REPORT.txt'),contract=str(O/'TIME_CONTRACT_DRAFT.txt')))
print(json.dumps(dict(completed=True,implementation_stage_wall_seconds=elapsed,economic_paths=0),ensure_ascii=False))
