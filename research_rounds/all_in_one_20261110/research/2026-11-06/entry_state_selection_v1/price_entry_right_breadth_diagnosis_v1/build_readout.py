from pathlib import Path
import json,hashlib,itertools
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent
x=pd.read_csv(O/'GROUPED_DESCRIPTIVE.csv'); c=json.loads((O/'COVERAGE.json').read_text());qa=json.loads((O/'QA.json').read_text());cases=pd.read_csv(O/'FIXED_CASES.csv')
def fmt(v):return '—' if pd.isna(v) else f'{v:,.2f}'
def pct(v):return '—' if pd.isna(v) else f'{100*v:.2f}%'
def md(rows,heads):return '| '+' | '.join(heads)+' |\n|'+'|'.join(['---']*len(heads))+'|\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows)+'\n'
lines=['# PRICE初仓与同业右侧人数：两窗因果时钟归因\n',
'## 结论先行\n',
'预定的“同业至少半数M3右侧且固定全N当日可证净扩张”，在两窗池内都对应较高的独立初仓CORE均净和胜率；这是真实存在的描述性关联，不应抹掉。但它不能直接升级为统一首仓门：只看至少半数的方向跨窗反转，组合关系在新根/参与历史/月度分层并不一致，且2022有62.4%、2024有43.7%的实际买入无法判定全N日变化。未知不能当OFF，也不能改用已知成员方向替它作主结论。\n',
'这不是用“追涨杀跌、保护洗出”否决右侧交易。证据不足之处在于：同一信号定义是否在参与路径与行情阶段变化后仍稳定区分初仓质量，以及是否把先走的个股误当无效。这里没有新的交易执行、过滤后策略收益、门槛调优或因果alpha证明。\n',
'## 人群、费用与缺失分母\n',
'单位是原independent_channel_joint_economic_v1联合A+B+PRICE/PVR的PRICE登记/实际buy_core。未用generation gate或DMI新臂。原COMMON沿原A+B对联合策略的共同可比股票集合1245/1577只，不能换成后续gate比较集合。FULL是完整回合；CORE是原core_independent_dated_fee_diagnostics的独立首仓费用/权益口径，绝非旧PROBE_realized拆腿。复用已审表，未重算任何费用。\n']
rows=[]
for q in qa['ledger']:
 p=q['economic_partition'];rows.append([q['year'],q['registered'],q['actual_buy'],p['COVERED_CLOSED'],p['ECONOMIC_UNKNOWN'],p['KNOWN_BUT_FINANCIAL_UNCOVERED'],p['NO_BUY'],q['common_actual']])
lines.append(md(rows,['窗','PRICE登记','实际买','财务覆盖闭合','经济UNKNOWN','非UNKNOWN但财务未覆盖','未买','原COMMON实际买']))
lines.append('互斥分母把经济UNKNOWN置于财务未覆盖之前。2024的15个财务未覆盖flag中1个也UNKNOWN，故实际买=1101+83+14，不是1101+83+15；2022无交叠。未买16/12中，UNKNOWN未买13/3、q0未提交3/9。无结果不是零收益。\n')
rows=[]
for z in c:
 rows.append([z['year'],z['scope'],z['CORE_financial']['n'],fmt(z['CORE_financial']['mean_net']),fmt(z['CORE_financial']['total_net']),pct(z['CORE_financial']['win_rate']),fmt(z['FULL_financial']['mean_net']),fmt(z['FULL_financial']['total_net']),pct(z['FULL_financial']['win_rate'])])
lines.append(md(rows,['窗','范围','金融n','CORE均净','CORE总净','CORE胜率','FULL均净','FULL总净','FULL胜率']))
lines+=['所有净额为元，胜率为净额>0的闭合比例。两窗独立、长度不同，不合并成账户收益。完整JSON同时保留ALL条件闭合（2022 n2055、2024 n1115）与财务覆盖闭合，避免只用net非空当完整覆盖。\n',
'## 固定定义与可见时钟\n',
'- 特征已知时点为信号T收盘，成交代理为next-common开盘；不会用成交日高低收盘或未来收益判定特征。\n- 个股M3沿原native μ5，α=1/3、64个有效收益暖机。三个连续共同交易日μ严格>0且原量价与源身份有效为ON；三日可知但有μ≤0为OFF；缺失为UNKNOWN。原底层μ不是完全源隔离重暖版本。\n- 独立M3的KNOWN3/RIGHT3不附PVR共同known筛选。先拼真实2021/12/29–31前缀，2022/1/4日变化对应12/31。原静态1709股90行业成员非PIT；对每个目标永久留一。\n- 同业N固定、K已知、n右侧、U=N−K。比例区间[n/N,(n+U)/N]；2n≥N为AT_LEAST_HALF，2(n+U)<N为BELOW_HALF，其余UNKNOWN。N=0一律UNKNOWN。它不是原candidate：原candidate还含n≥3及1/3+三日扩散支路。\n- 全N当日人数变化界L=n_T−n_prev−U_prev，H=n_T+U_T−n_prev；L>0可证净增，H<0可证净减，L=H=0确切持平，其余UNKNOWN。代码逐成员算边界并校验H−L=U_T+U_prev。\n- 副表paired J只取两个端点都已知同业，entered−left除以J。它仅是“共同已知成员净变化”，不是全行业。未知多时不提升副表。\n- 原行业四事实及sector_E0对全部实际买入均真，没有样本内区分能力；old_fast_market_state按原字段保留而不另造行业冷热。\n',
'## 预定主命题：两窗池内关联\n',
'初始合同先于任何分组结果。父级预期假设补充在首个分析进程已启动、但任何结果取回/查看之前落盘，准确时间顺序见HYPOTHESIS_AND_QA_ADDENDUM.md；这不是盲法预注册。唯一预定比较为“至少半数且全N净增”对其它可判主cells，机制不可判者单列，不从最佳cell倒选命题。\n']
g=x[x.grouping.eq('intended_hypothesis_cell')]; rows=[]
for z in g.itertuples():rows.append([z.year,z.scope,z.intended_hypothesis_cell,z.actual_buy,z.CORE_financial_n,fmt(z.CORE_financial_mean_net),fmt(z.CORE_financial_total_net),pct(z.CORE_financial_win_rate),fmt(z.FULL_financial_mean_net),fmt(z.scale_CORE_financial_mean_initial_core_buy_cash),fmt(z.scale_CORE_financial_mean_entry_risk)])
lines.append(md(rows,['窗','范围','预定类别','实际买','金融n','CORE均净','CORE总净','CORE胜率','FULL均净','初仓平均buy_cash','平均计划风险']))
lines.append('该组相对其它可判组的CORE均净差：2022约+369.13元，2024约+466.49元；原COMMON约+413.95/+498.58元。同方向不等于已建立因果效应或统计显著性。初仓规模与风险并不完全相同，日期、行业及已入选队列也未随机化。\n')
lines.append('## 全部固定主cells\n')
full=[]
for year,scope in itertools.product([2022,2024],['ALL','ORIGINAL_COMMON']):
 subset=x[x.year.eq(year)&x.scope.eq(scope)&x.grouping.eq('peer_half__peer_delta1_robust')]
 for half,direction in itertools.product(['AT_LEAST_HALF','BELOW_HALF','UNKNOWN'],['POSITIVE','FLAT','NEGATIVE','UNKNOWN']):
  hit=subset[subset.peer_half.eq(half)&subset.peer_delta1_robust.eq(direction)]
  if len(hit):row=hit.iloc[0].to_dict()
  else:
   row={col:np.nan for col in x.columns}
   counts=[col for col in x.columns if col.endswith('_n') or col.endswith('_wins') or col.endswith('_actual') or col in ['registered','actual_buy','no_buy','stocks']]
   row.update({col:0 for col in counts})
   row.update(year=year,scope=scope,grouping='peer_half__peer_delta1_robust',peer_half=half,peer_delta1_robust=direction)
  full.append(row)
 forreport=[q for q in full if q['year']==year and q['scope']==scope]
 if scope=='ALL':
  lines.append(f'### {year} ALL：原登记分组，不是筛选后策略\n')
  lines.append(md([[q['peer_half'],q['peer_delta1_robust'],int(q['actual_buy']),int(q['CORE_financial_n']),fmt(q['CORE_financial_mean_net']),fmt(q['CORE_financial_total_net']),pct(q['CORE_financial_win_rate']),fmt(q['FULL_financial_mean_net'])] for q in forreport],['同业半数','全N日变化','实际买','金融n','CORE均净','CORE总净','CORE胜率','FULL均净']))
pd.DataFrame(full).to_csv(O/'MAIN_CELLS_ALL12.csv',index=False)
lines.append('无样本的UNKNOWN半数×确切FLAT明确列0、结果空，未隐藏。原COMMON全部12 cells在MAIN_CELLS_ALL12.csv；其它单变量、paired副表、固定分层在GROUPED_DESCRIPTIVE.csv/json。\n')
lines+=['## 为何不能只读池内均值\n',
'1. 单纯高广度不重复。至少半数 vs 不足半数，2022 CORE均净−284.16 vs−879.42，胜率31.91% vs21.71%；2024反为+967.37 vs+1925.73，胜率45.82% vs48.41%。不能说“越多股票已右侧，初仓就越优”。\n',
'2. 组合关系并不跨生命周期一致。旧root续frontier组两窗目标cell都较其它可判者均净高；新root组2022−281.39 vs−471.57，但2024+1534.31 vs+1602.48。2022首次PRICE-after-AB目标cell−1420.33 vs−259.19；2024重复PRICE目标cell−1445.93 vs−766.63。不能后验留下旧root/首次等赢家层，把其余另设门。\n',
'3. 日期混杂显著。2024目标cell金融n198中140在9月，其CORE总净+409398.81元超过该组整窗+337431.91元；11/12月目标cell均净−1896.87/−1774.48，均低于当月其它可判−1450.80/−1073.98。2022一季度目标cell逐月同样更低。完整月份全列，不按月份重写规则，不预判未来行情长度。\n',
'4. 缺失传播必须算进去。全N Δ1 UNKNOWN实际买1495/2395和524/1198；半数UNKNOWN368/2395和37/1198；任一主维度不可判1530/2395和533/1198。N=0注册共10条。共同已知方向几乎可算不意味着全行业变化可证。机制UNKNOWN与经济UNKNOWN是不同轴，均保留。\n',
'5. 当下股票M3 ON本身也不稳定占优：2022 ON/OFF均净−659.81/−712.22；2024股票OFF均净更高。stockM3、出生/晚首次、重参与只是事前状态，不是“错单”标签。原已买同root跨初仓复用0，不存在可用该身份门自动修复的实例。\n',
'## 固定正反例与早行情\n']
rows=[]
for z in cases.itertuples():rows.append([z.name,z.signal_day,f'{z.peer_n}/{z.peer_N} ({z.peer_K} known)',f'[{fmt(z.peer_fixed_lower)},{fmt(z.peer_fixed_upper)}]',z.peer_half,f'[{int(z.peer_delta1_L_count)},{int(z.peer_delta1_H_count)}]',z.peer_delta1_robust,z.paired_known_direction,z.stock_M3,fmt(z.probe_closed_net)])
lines.append(md(rows,['股票','信号日','右侧/固定N','比例区间','半数','全N变化人数界','主方向','共同known方向','本股M3','独立CORE净额']))
lines+=['- 海能达9/20原行业up=false，无PRICE买入；9/23虽全N可证净扩张，但仍不足半数，原AB合法且优先约束不能改变。实际PRICE信号9/25满足半数+净增，9/26买。该固定早例与主组合相容。9/24已知成员净增但全N仍UNKNOWN，二者不能混称。\n',
'- 电气风电9/25固定11只同业，已知9只右侧0、全N变化[−2,+2]，仍有独立CORE +41265.77；巨轮6/13和银轮12/25也在不足半数/全N变化UNKNOWN下盈利。福莱9/30已满员右侧但当日净0，CORE +21893.54。成熟右侧成员留存、先走个股与新成员继续净进入不是一回事。结构上当全体同业已经右侧时，人数没有继续增加的空间，Δ1不可能永远>0；福莱10/10、当日净0就是这种自然饱和，不是因盈利才指定的白名单。只记录这个限制，不新造饱和豁免或修改公式。\n',
'- 反面也保留：歌尔9/30至少半数、paired净增，却不能证明全N净增，CORE−1548.59；华电辽能至少半数但全NUNKNOWN，CORE−1660.22。游族和南网为主组合中的正例，不是以后白名单。\n',
'- 江丰四日均来自原independent_channel_probe_preflight_v1/FIXED_DAILY信号事实，2025/12/15原root出生且E0/I都off、PROBE；12/17量确认且E0 on/I off；2026/1/5和1/15延续同2025/12/15根。四日同业均不足半数、全N日变化均UNKNOWN，因此硬门会改变此先行路径。没有2026成交、持仓或收益核算。12/15与12/17的旧行业四事实在本轮可用case join中缺失，保持空值；独立sector_E0来自原M3表且为真，不能用它冒充四事实。\n',
'## 交付与边界\n',
'本轮新增的是将原PRICE实际初仓与独立留一M3右侧人数、严格全N当日净变化按同一收盘时钟连接，并给出覆盖边界和独立初仓费用结果。M3、固定N未知区间、留一法本身早已存在；本轮不声称发明新指标。旧ENTRY_FACTS使用PVR共同known的M3已全部加OLD_COMMON_K前缀，避免继承错误分母。\n',
'能保留的是一个两窗池内同向的支持性关联；尚未建立可重复、可执行、对早先行个股适用的统一质量条件。不可据此宣称新策略优于原基线，也不反向选低广度、改阈值或拼接月份来补救。未知信息只允许表达不确定，不能悄悄否决交易。\n',
'主要文件：FEATURE_CONTRACT.md、HYPOTHESIS_AND_QA_ADDENDUM.md、ALL_PRICE_ENTRY_FACTS.csv（3621登记）、COVERAGE.json、GROUPED_DESCRIPTIVE.csv/json、MAIN_CELLS_ALL12.csv、FIXED_CASES.csv、FIXED_PEER_COMPONENTS.csv、QA.json、SOURCE_HASHES.json。读取源哈希均未变；新经济执行0、费用重算0、参数搜索0、过滤后策略收益0。独立复算已通过全部3621特征、790分组/4覆盖、22病例/1155同业贡献及原buy_core/退出溯源，见INDEPENDENT_RECOMPUTATION_AUDIT.json。\n']
(O/'READOUT.md').write_text('\n'.join(lines))
(O/'FINAL_OUTPUT_HASHES.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.iterdir() if p.is_file() and p.name not in ['FINAL_OUTPUT_HASHES.json','OUTPUT_HASHES.json']},indent=2)+'\n')
print('READOUT and complete 12-cell grids written')
