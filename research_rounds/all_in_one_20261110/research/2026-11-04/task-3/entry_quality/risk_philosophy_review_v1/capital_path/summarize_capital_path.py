"""Read aggregate original No60 evidence only; no financial engine or account."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,hashlib
HERE=Path(__file__).resolve().parent;E=HERE.parents[1];A=E/'structural_failure_v1/accounting/results_v2';S=E/'structural_failure_v1/scale_concentration/results_v3';W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');SRC={};Z=D(0)
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest()
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def save(n,x):
 with (HERE/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
fmt=lambda x:f'{D(x):,.2f}'
pct=lambda x:f'{D(x)*100:.2f}%'
stages={x['period']:x for x in read(A/'STAGE_WEALTH_CAPITAL_MATRIX.json')};daily=read(E/'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair/daily.jsonl.gz',gz=True,lines=True);raw={x['at'][:10]:x for x in daily};risk={x['day']:x for x in read(S/'2022_2024_DAILY_CAPITAL_RISK_CONTEXT.json')};campaigns=read(A/'2022_2024_CAMPAIGNS_FULL_ACCOUNTING.json');act=read(A/'ACTUAL_ACT_EPISODES.json');scale=read(S/'SUMMARY.json');levels=read(S/'2022_2024_ALL_LAYER_SCALE_CONTEXT.json')
dates=['2022-01-04','2022-06-30','2022-11-30','2022-12-30','2023-04-28','2023-07-20','2023-07-21','2024-05-06','2024-09-23','2024-10-08','2024-12-23','2024-12-25','2024-12-31'];boundaries=[]
for day in dates:
 d=raw[day];r=risk[day];inv=D(d['inventory']);nav=D(d['nav']);stockmarks=[D(x['mark']) for x in r['stocks'].values()];sectormarks=[D(x['mark']) for x in r['sectors'].values()]
 boundaries.append(dict(day=day,NAV=nav,inventory=inv,exposure=inv/nav,ACT_on=d['on'],stocks=len(d['positions']),sectors=len(r['sectors']),layers=len(d['layers']),known_paid_basis_to_reference_line_pct_NAV=r['paid_basis_to_known_line_pct_NAV'],marked_giveback_to_reference_line_pct_NAV=r['marked_giveback_to_known_line_pct_NAV'],largest_stock_mark_over_NAV=max(stockmarks,default=Z)/nav,largest_sector_mark_over_NAV=max(sectormarks,default=Z)/nav,stock_mark_HHI=None if not inv else sum(((v/inv)**2 for v in stockmarks),Z),sector_mark_HHI=None if not inv else sum(((v/inv)**2 for v in sectormarks),Z)))
example=next(c for c in campaigns if c['sid']=='000620.SZ' and c['opened'][:10]=='2022-01-11');el=[x for x in levels if x['key'] in example['entry_keys']];core=[x for x in el if x['role']=='core'];mobile=[x for x in el if x['role']=='mobile'];assert len(core)==1 and len(mobile)==5
example.update(actual_CORE_buycash=sum((D(x['actual_buycash']) for x in core),Z),actual_mobile_buycash_turnover=sum((D(x['actual_buycash']) for x in mobile),Z),CORE_endpoint_net=sum((D(x['outcome_lifecycle_net']) for x in core),Z),mobile_endpoint_net=sum((D(x['outcome_lifecycle_net']) for x in mobile),Z))
selected=['P01_2022H1','P02_2022JulNov','P03_Dec2022','P04_2023JanApr','P05_2023MayJul','P06_2023Aug_2024Jan','P07_2024FebMay','P08_2024Jun_Sep23','P09_2024Sep24_Oct8','P10_after2024Oct8'];minimum=min(daily,key=lambda d:D(d['nav']));meta=read(E/'trend_exit_controls_v1/runs/BASELINE/2022_2024/RUN_METADATA.json')
sources=[W/'account-risk-ablation-20261031/adapter.py',W/'account-risk-ablation-20261031/model_without_account_check.py',W/'account-risk-ablation-20261031/route_without_account_check.py',W/'case-stage-ledger-20261031/v3/joint_v3.py',RR/'lot-risk-allocation-20261029/code/study.py']
for p in sources:
 h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==meta['source_freeze'][str(p)];SRC[str(p)]=h
facts=dict(status='PASS_AGGREGATE_READ_ONLY_CAPITAL_PATH',baseline='Original No60 BASELINE, not H2/eta',full=stages['FULL_2022_2024'],YEAR2022=stages['YEAR2022'],stages={k:stages[k] for k in selected},boundaries=boundaries,actual_ACT_episodes=act,early_trial_example=example,minimum_NAV_day=minimum['at'][:10],minimum_NAV=minimum['nav'],new_accounts=0,new_backtests=0,new_parameters=0,new_basis_or_hypothetical_account=0)
save('CAPITAL_PATH_FACTS.json',facts)
L=['小CORE与全户大回撤：原No60资金路径，只读复盘','',
'结论：小CORE只限制这一笔早期仓位，并不封住后续mobile、全组合持仓市值或长期累积损失。原No60三年期末637989.61（−36.20%），最大DD38.09%；2022年末704487.85（−29.55%）。这两个结果不与单笔CORE很小矛盾。以下不新增回测、账户或参数。','',
'代码事实（冻结代码与原RUN_METADATA SHA核同）',
f'1. CORE原all-in保护线名义预算为NAV×0.0025，且整手/名义cap会进一步缩小实际买款；不是账户终身只允许亏0.25%。[study.py]({sources[-1]}:42)。',
f'2. 原新mobile按当前NAV×2% gross与单股余量规划，不按首笔CORE实际本金同比例授权；2%是买款目标，不是2%风险预算。[joint_v3.py]({sources[3]}:259)。',
f'3. 此No60实际启用NoAccountBudget；其有效route/request保留现金、probe/confirmed池、行业资本/风险和单股约束，但没有全户3%名义风险admission检查。confirmed池60%不是全户20%/30%回撤上限。[adapter.py]({sources[0]}:9)、[route]({sources[2]}:13)、[request]({sources[1]}:240)。',
f'4. shared_loss_budget虽记录20000，exhausted_policy却是record_only，累计亏损记录并不自动拒绝所有新尝试；ACT另按收盘NAV/episode峰值工作，收盘触发后才提出退出，实际执行在后续OPEN。[joint_v3.py]({sources[3]}:16)、[planning]({sources[3]}:221)。','',
'账户事实：小试单之后可以出现大得多的连续出资',
f'盈新发展000620的2022Jan11-Feb8完整campaign：CORE实买{fmt(example["actual_CORE_buycash"])}，随后5个mobile实买款合计{fmt(example["actual_mobile_buycash_turnover"])}，整个campaign净{fmt(example["endpoint_net"])}。这是买款周转，不是同一时刻投资92622元；原实际并发mark峰{fmt(example["peaks_on_actual_held_CLOSE_only"]["values"]["mark"])}、basis峰{fmt(example["peaks_on_actual_held_CLOSE_only"]["values"]["basis"])}另保留。小CORE没有按比例约束后来总资金，也没有证明后续趋势正确。','',
'长期资金桥（原互斥阶段；三组连续路径，非新回测）：',
'阶段 | 期初NAV→期末NAV | 阶段财富 | 新买款周转 | 前收盘平均仓位 | old/first/add/reentry财富']
for k in selected:
 x=stages[k];g=x['cohort_summary']['cohort'];components=[g.get(c,{}).get('net',0) for c in ['old_inventory_previous_CLOSE','new_first','new_add','new_reentry']]
 L.append(' | '.join([k,fmt(x['NAV_begin'])+'→'+fmt(x['NAV_end']),fmt(x['net_wealth_change']),fmt(x['actual_buycash']),pct(x['mean_previous_CLOSE_exposure']),'/'.join(fmt(v) for v in components)]))
L+=['2022H1先亏181223.46，Jul-Nov另亏19482.05，Dec再亏94806.65，故年末约−29.55%；Dec包含旧87层−53407.03和新122层−41399.61，不只是初始CORE失败。2023Jan-Apr赚173259.71后May-Jul亏132320.60；2024Sep23→Oct8赚179319.69后至年末亏167054.32，后段同时有旧75层−54596.72及新303层−112457.60。','',
'当时实际暴露与同时风险参考（pct_NAV字段为百分数，不是比例）：',
'日期 | NAV | 市值/仓位 | 股数/行业数/层数 | 已付basis至参考线%NAV | 市值至参考线%NAV | 最大股/行业市值占NAV']
for x in boundaries:
 L.append(' | '.join([x['day'],fmt(x['NAV']),fmt(x['inventory'])+'/'+pct(x['exposure']),f'{x["stocks"]}/{x["sectors"]}/{x["layers"]}',fmt(x['known_paid_basis_to_reference_line_pct_NAV']),fmt(x['marked_giveback_to_reference_line_pct_NAV']),pct(x['largest_stock_mark_over_NAV'])+'/'+pct(x['largest_sector_mark_over_NAV'])]))
L+=['这些已知线仅是原尺度风险参考，不保证能按线成交，也不是永久保护最初本金。每日股/行业数、实际mark及现成HHI列于CAPITAL_PATH_FACTS；类别多不证明收益独立，同行业或不同行业仍可同涨同跌，此处没有估计协方差或把65行业当65份独立风险。','',
'ACT实际时钟，而非20%硬损失保证：']
for x in act:
 L.append(x['pause_request']['at']+'收盘暂停（NAV '+fmt(x['pause_request']['nav'])+'，本episode DD '+pct(x['pause_request']['episode_drawdown'])+'），首次实际flat CLOSE '+str(x['first_flat_CLOSE'])+'、NAV '+fmt(x['first_flat_NAV'])+'；恢复 '+(x['resume_close']['at'] if x['resume_close'] else '期末未恢复')+'。')
L+=['2022Apr20的退出在Apr21已平；2023Jul20在Jul21已平；2024Dec23到Dec25才全部flat（Dec24还有原持仓余量），不能一律写触发次OPEN全平。原暂停后flat至恢复NAV不变；市场机会格虽仍记录，但去掉ACT后究竟哪些原信号可获资未识别，不造潜在无买账户或补计市场上涨。','',
'推断（不冒充已识别因果份额）',
'单笔名义风险控制的是一次当前出资/当前参考线。持仓陆续止损并释放资源后，系统可以再给其他原合法CP出资；重复小亏可以累积，盈利后的市值回吐也会产生大阶段财富下降。高至约90%的实际股票暴露使全户财富对共同下跌敏感；分行业上限与记录性共享亏损计数不能推出长期DD上限。',
'ACT是事后收盘episode回撤制动器，存在观察/下单/可售执行时差，并在恢复后开始新的episode峰值；它没有把最初100万元的累计损失永久封在20%。这解释了“有小CORE、仍可全户20—30%甚至38%DD”的允许路径，不证明每笔亏损可提前识别或某条替代规则有效。','',
'核查入口：原[阶段桥]('+str(A/'STAGE_WEALTH_CAPITAL_MATRIX.json')+')、[ACT原时钟]('+str(A/'ACTUAL_ACT_EPISODES.json')+')、[全部campaign]('+str(A/'2022_2024_CAMPAIGNS_FULL_ACCOUNTING.json')+')、[原日风险参考]('+str(S/'2022_2024_DAILY_CAPITAL_RISK_CONTEXT.json')+')。0finance/0新账户/0参数。']
(HERE/'READOUT.md').open('x').write('\n'.join(L)+'\n');SRC[str(Path(__file__).resolve())]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();save('SOURCE_SHA256.json',SRC);save('COMPLETION.json',dict(status='COMPLETE_READ_ONLY_CODE_FACT_ACCOUNT_FACT_INFERENCE_SEPARATE',new_accounts=0,new_backtests=0,new_parameters=0,new_basis=0,hypothetical_no_buy_account=0))
print('CAPITAL_PATH_COMPLETE',len(boundaries),'boundaries',example['actual_mobile_buycash_turnover'])
