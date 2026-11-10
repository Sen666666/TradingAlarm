"""Render audited findings only; no strategy execution or source changes."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import csv,json,hashlib
O=Path(__file__).resolve().parent;R=O/'result_02'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
seeds=read(R/'SEED.json');rounds=read(R/'ROUNDS.json');summaries=read(R/'SUMMARY.json');pairs=read(R/'PAIRS.json');metrics=read(R/'METRICS.json')
arms=['CP_CONTROL_COMMON_I_SIZE','I_PROBE_COMMON_I_SIZE'];ids=[27,17,28,1527,1542,2891,2893,343,361,1942,1952,2898,2905,2897]
def num(x):return '未入场' if x is None else f'{D(str(x)):,.2f}'
def pct(x):return 'NA' if x is None else f'{D(str(x))*100:.2f}%'
rows=[]
for cid in ids:
 cpi,ii=[next(s for s in seeds if s['case_id']==cid and s['arm']==arm)for arm in arms]
 out=dict(case_id=cid,sid=cpi['sid'],name=cpi['name'])
 for short,arm,s in zip(['CP','I'],arms,[cpi,ii]):
  rr=[r for r in rounds if r['case_id']==cid and r['arm']==arm];seedr=[r for r in rr if r['origin']=='SEED_MOBILE'];later=[r for r in rr if r['origin']!='SEED_MOBILE']
  sm=next(r for r in summaries if r['case_id']==cid and r['arm']==arm)
  out.update({short+'_first_status':s['status'],short+'_first_net':s['net'],short+'_first_cost':s.get('buy_cost'),short+'_first_hold_closes':s.get('holding_closes'),
   short+'_seed_round_status':seedr[0]['status']if seedr else 'NO_ENTRY',short+'_seed_round_net':seedr[0]['net']if seedr else None,
   short+'_seed_round_buy_cost':seedr[0]['buy_cost']if seedr else None,
   short+'_later_round_count':len(later),short+'_later_W':sum(r['status']=='CLOSED_WIN'for r in later),short+'_later_L':sum(r['status']=='CLOSED_LOSS'for r in later),
   short+'_later_open_positive':sum(r['status']=='OPEN_POSITIVE'for r in later),short+'_later_open_negative':sum(r['status']=='OPEN_NEGATIVE'for r in later),
   short+'_case_marked_net':sm['marked_net'],short+'_unpaid_dividend':sm['ending_unpaid_dividend']})
 rows.append(out)
with (O/'THREE_LEVEL_CASES.csv').open('x')as f:w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
counts={}
for arm in arms:
 sr=[s for s in seeds if s['arm']==arm];rr=[r for r in rounds if r['arm']==arm]
 wins=[D(s['net'])for s in sr if s['status']=='CLOSED_WIN'];loss=[D(s['net'])for s in sr if s['status']=='CLOSED_LOSS']
 aw=sum(wins)/len(wins);al=sum(loss)/len(loss)
 counts[arm]=dict(first_status=dict(Counter(s['status']for s in sr)),whole_round_status=dict(Counter(r['status']for r in rr)),
  seed_whole_status=dict(Counter(r['status']for r in rr if r['origin']=='SEED_MOBILE')),
  later_whole_status=dict(Counter(r['status']for r in rr if r['origin']!='SEED_MOBILE')),
  first_average_win=str(aw),first_average_loss=str(al),first_payoff_ratio=str(aw/abs(al)),
  first_tail30_closed=sum(bool(s.get('closed_tail_30pct'))for s in sr))
(O/'DESCRIPTIVE_COUNTS.json').write_text(json.dumps(counts,ensure_ascii=False,indent=2)+'\n')
lines=['# 固定14例条件路径：独立经济核算最终报告',
'',
'结论：本轮足以证明“空仓MOBILE首层按I持有”能在部分已知败例保住反弹，也证明它会扩大亏损、延长占资并吞掉部分右尾。它不是已经找到更好的入场公式。保留为机制研究假设有意义，但没有依据宣布成熟、进入35%目标验证，或直接推广为完整账户方案。',
'',
'## 1. 独立审计结果与边界',
'',
'- 封存28路径全部通过。独立重建14,886个共同收盘的股数、含买费剩余成本K、现金/预约/售款应收/股息应收、raw行情库存和NAV；逐笔929成交重新计算dated费率及费用组件。',
'- 52次分红权益与原始公司行动旧股数×现金条款×0.8净额代理匹配。全部没有付款记录，保留为应收；不当成到账现金。已闭W中没有仅靠未付股息把现金亏损翻正的回合，但金额仍须区分。',
'- 两个拆股事件是钢研高纳同一次源事件在两臂各出现一次。合计及分层股数、成本单位变化均匹配；没有拆股取整令库存归零。审计代码对该分支给split_fraction_writeoff结案，但本样本未覆盖该实证边界。',
'- 独立929次raw OPEN±5bp及前20正量1%容量核对、575个卖出分层先买日检查均通过。实际没有同订单多次成交，故部分成交身份/累计最低佣金的实证覆盖为0；不把代码具备该逻辑当已有样本证明。',
'- 输入冻结342项、run封存产物36项全部hash一致。未import或运行任何策略引擎、未改参数/合同、未重跑账户。result_01是最初算术版本；最终使用result_02，补入了真实代理卖出端点，避免漏掉隔夜跳空损失。',
'- 此审计不独立重演I/CP资格、行业/池预算或每笔拒单决策，不重新证明partial/订单失效/拆股新增份额可卖时钟。真实撮合、涨跌停与官方停牌仍UNKNOWN；固定1709背景NON-PIT；条款预知与费用/股息均沿原代理合同。',
'',
'## 2. 三层必须拆开',
'',
'初层是种子原始订单全部成交层；种子完整回合包含后来ADD直到该股0→0；后续回合保留每次新信号重入，不与对臂强行一一配对。所有数字为元，未闭数字为含应收的原生收盘账面值，绝非强平收益。',
'',
'| 原case | 名称 | 首层CP / I | 种子整轮CP / I | 后续回合数CP / I | 首层占资收盘CP / I |',
'|---|---|---|---|---|---|']
for r in rows:
 def val(short,scope):
  v=r[short+'_'+scope+'_net'];st=r[short+'_'+scope+'_status']
  return num(v)+('（未闭）'if st.startswith('OPEN')else'')
 lines.append(f"| {r['case_id']} | {r['name']} | {val('CP','first')} / {val('I','first')} | {val('CP','seed_round')} / {val('I','seed_round')} | {r['CP_later_round_count']} / {r['I_later_round_count']} | {r['CP_first_hold_closes'] if r['CP_first_hold_closes'] is not None else 'NA'} / {r['I_first_hold_closes'] if r['I_first_hold_closes'] is not None else 'NA'} |")
lines+=['',
'逐例费用、累计买入含费支出、净额、平均赢亏/盈亏比、尾部数、开平/新信号日、回本与等待、最大不利路径、成本日详见METRICS/SEED/ROUNDS/FIRST_INTENTS/REENTRIES文件；THREE_LEVEL_CASES.csv是三层扁平表。',
'',
'## 3. 计数而非外推胜率',
'',
'- 固定14个种子：CP首层6W/7L/1未入；I首层8W/4L/1未闭正/1未入。共同13个实际首填的股数两臂完全相等；变化不是缩股带来的胜率“提升”。',
'- 7个原快败：新集、格力、烽火首层转成已闭赢；天山、华东、三花、岩山4个仍亏且全部扩大。岩山由-11.85%扩至-22.43%，可见low/实际成交端点最不利为-22.68%，占资1→28个共同收盘；华东-14.04%→-16.89%。',
'- 首层已闭平均赢/平均亏：CP +4496.09 / -1030.54，金额盈亏比4.36；I +4956.27 / -1841.61，金额盈亏比2.69。这些均为历史挑选开发例的描述，不能当总体期望。',
'- 尾部固定为已闭净额/累计买入含费成本≥30%。CP首层6例，I首层4例；中国动力I浮盈47.12%仍未闭，不计尾部胜例。中国银河和湖南白银原首层右尾均回吐到30%以下。',
'- 种子含ADD完整0→0：CP 5W/8L；I 5W/7L/1未闭正。首层“8W”不能替代整轮“5W”。',
'- 所有真实后续回合全保留后，CP共119轮=24W/85L+10未闭，I共109轮=20W/79L+10未闭。这些含不同年份长度、可变回合身份和挑选样本，不是可直接因果比较的策略胜率。',
'- 同case全路径同截止账面差：I比CP高7例、低6例、相同1例。没有将14条独立现金路径加成一个组合收益。',
'',
'## 4. 最重要的反例与成功代价',
'',
'### 烽火通信：首层救回，整轮更亏',
'首层CP -414.59 → I +419.53，但I种子含ADD整轮为-3721.28。I后续ADD合计净额约-4140.81，累计新增买入含费支出40652.92。控制首层退出后另有CORE重入；到同截止，全路径CP -2865.87、I -4308.09。首层多守67个共同收盘，无法只按卖日位移解释。',
'',
'### 湖南白银：两臂首层均赢，两臂整轮均亏',
'CP首层+2698.03、种子整轮-615.80；I首层+1172.45、种子整轮-642.04。仅有V>K盈利门并不能保证追加后的盈利。CP之后新CORE轮2026-03-03至3/20再亏2303.51；I仍处原轮而没有同一笔新CORE，因此不得逐笔配对。',
'',
'### 2024中国银河：漏尾与后续宽I亏损',
'首层收益从CP +39.13%降到I +23.16%，多占资4个共同收盘。两臂2024-11-05信号、11/06买入的真正CORE重入，首层均亏2112.68（-14.66%）；含ADD整轮均亏3511.63。保留该失败，不能只展示9月赢家。此CORE本来就使用I退出，不能算首MOBILE新方案单独造成。',
'',
'### 2024润泽科技：大赢家不能代替成熟证据',
'首层CP +5805.96（48.95%）→I +13940.67（117.53%），首层占资21→141共同收盘，多120日；种子含ADD整轮CP +18062.40，I +24716.42。I整轮累计买入支出85949.44，按整轮成本口径回报28.76%，不是首层117.53%。CP在其间归零再CORE重入，不能把两臂序号相同回合硬配。I后续2025-11-27新MOBILE轮仍未闭，浮盈不能算又一胜。',
'',
'### 2026江丰电子：种子完全没有买入',
'两臂1/15首MOBILE因为I风险与最小单位合同不能入场。之后2026-02-06新CORE信号、2/09才首次成交，标LATER_FIRST_CORE而不是获救/重入的首MOBILE。两臂同一后续路径到截止含ADD浮盈7241.51，未闭；原CORE首层浮盈6473.95也未闭。不能把历史原股数轨迹套到这条条件路径。',
'',
'### 中国动力：末日触发，尚未卖出',
'控制首层3/12收盘触发、3/13卖出；候选首层5/15收盘才触发，截止没有下个OPEN。I首层+5932.90及整轮+19261.10均未闭；CP后续CORE轮-2418.72也未闭。两臂末日均有待卖，不能强平后打上输赢。',
'',
'## 5. 回本、等待、缺价与单位解释',
'',
'- 经济回本为收盘时累计卖净款+已获股息权益+剩余持仓按raw close×0.9995减当日卖费≥累计买含费支出。只是当日纸面回本，后面仍可能亏；不等于卖出或持续获利。现金本金回收只计已结算售款与已付股息，另列日期。',
'- 例如新集I首层2024-01-09已纸面回本，最终本金现金回收在7/15；烽火I首层2/10纸面回本、5/06现金回收，但含ADD整轮最终亏且未回收全部累计本金。日期是首次共同收盘确认，不声称盘中最早时刻。',
'- 13个首填的首层已闭退出均在首触发后的第一个共同OPEN代理成交；周末和节假日会使日历天间隔变长，例如烽火4/30→5/06。中国动力I只有末日触发，等待未完。整轮最早ADD退出不等于首层退出，分别记录。',
'- 润泽2026-02-06、2/09–2/13共6个持仓共同收盘缺当日raw OPEN/close，两臂使用2/05最近可见mark计NAV，路径极值在这些日UNKNOWN。江丰1/30、2/02–2/05共5个缺OPEN日两臂仍空仓；没有虚构成交，也不称官方停牌。',
'- 最大不利分开提供：持仓可见收盘与实际买卖端点、加入持仓当日raw low的代理极值。开盘已卖出的层不使用随后日内low；卖出端点计入，所以岩山/华东等隔夜跳空损失不会被low指标漏掉。低点参考含5bp/卖费但不宣称可成交。',
'- 本独审不用adjusted total-return low充作可交易跌幅。美元金额（实际为CNY）与raw持股×raw价、拆股后合法股数、权益分别算；总剩余成本K拆股不减少，每股成本随股数变化。调整因子只在源策略的入场/线责任审查中，不作为本审计收益单位。',
'- 初层首填占资中位数CP 13、I 42个共同收盘，均值约20.15→59.46。延长持有与更大亏损是真实代价，而非更高入场质量证据。',
'',
'## 6. 是否值得继续，以及下一步应改哪里',
'',
'值得保留“首次进入理由与后续追加责任分离”的机制假设，但不应据本14例直接扩账户或宣告更好入场。没有新事前预测信息；改变的是持有责任、占资和后续原生风险预算。',
'最先需要审视的是追加责任而非给首层结果换名：V>K仅证明下单时已有库存按同OPEN清算高于成本，没有证明新增ADD的边际胜率、出场损失或整轮风险收益。烽火/湖南已给出具体反例。可在下一份事先冻结合同里先分解首层与每笔ADD现金流、触发与风险消耗，明确评价单位是首层还是完整0→0；不要因看到本次结果就调一组新阈值。',
'真正CORE重入必须继续作为原10%/.25%/I责任单列；它贡献大量后续失败，也有收益，不能把其结果算成首MOBILE改动带来的胜率。若后续要检验入场公式，需另行冻结未用于本轮选例/调规则的前向或时间外验证方案，并恢复完整账户约束。当前没有完成这一步。',
'',
'## 7. 文件与复现',
'',
'- audit_outcomes.py：独立只读核算入口。result_02/RESULT.json为最终PASS；result_02/OUTPUT_HASHES.json列全部逐例、逐轮、逐日数据hash。',
'- result_02/SEED、FIRST_INTENTS、ROUNDS、METRICS、REENTRIES、BRIDGE、PAIRS各有JSON/CSV。全部失败及后续赢家均保留。',
'- execution_source_check.json：929 OPEN价格/容量、575卖出分层日期及缺价覆盖补核；check_execution_sources.py为独立脚本。',
'- THREE_LEVEL_CASES.csv：每case两臂三层逐例表。DESCRIPTIVE_COUNTS.json：计数与首层平均盈亏。',
'- FINAL_HASHES.json：本独审文件最终hash。上述审计只重算封存记录，经济引擎运行次数为0。',
'']
report='\n'.join(lines).replace('美元金额（实际为CNY）','CNY金额')
(O/'REPORT.md').write_text(report)
paths=[p for p in O.rglob('*') if p.is_file() and '__pycache__'not in str(p) and p.name!='FINAL_HASHES.json']
(O/'FINAL_HASHES.json').write_text(json.dumps({str(p.relative_to(O)):sha(p)for p in paths},ensure_ascii=False,indent=2)+'\n')
print('REPORT',sha(O/'REPORT.md'));print('FINAL_HASHES',sha(O/'FINAL_HASHES.json'));print('RESULT',sha(R/'RESULT.json'));print('ROUNDS',len(rounds),'FIRST',len(seeds))

