from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal
import json,csv,hashlib,math
import numpy as np
R=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1');O=R/'mainline_daily_industry_startup_opportunity_v1';OLD=R/'mainline_daily_industry_evidence_v1';TAIL=R/'mainline_tail_capture_baseline_v1';B=R/'mainline_m7_cash_batch_design_v6/once_20260630'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rd(p):return json.loads(Path(p).read_text())
def save(n,x):
 (O/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n')
 if isinstance(x,list) and x:
  with (O/(n+'.csv')).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in x for k in r)));w.writeheader();w.writerows(x)
oldseal=rd(O/'ORIGINAL_OUTPUT_SEAL.json');assert oldseal==rd(OLD/'OUTPUT_SEAL.json') and all(sha(OLD/n)==h for n,h in oldseal.items())
contract=rd(O/'APPENDIX_CONTRACT.json')
expected=(OLD/'build_evidence.py').read_text().replace("O=R/'mainline_daily_industry_evidence_v1'","O=R/'mainline_daily_industry_startup_opportunity_v1'")
a=expected.index('windows=[');b=expected.index('targetsecs=',a)
expected=expected[:a]+'windows='+repr([tuple(x) for x in contract['windows']])+'\n'+expected[b:]
expected=expected.replace("cal=known.index[(known.index>='2024-08-01')&(known.index<='2025-01-20')]","cal=known.index[(known.index>='2024-09-18')&(known.index<='2024-09-30')]")
assert expected==(O/'build_startup.py').read_text()
hashes=rd(O/'SOURCE_HASHES.json')
tailseal=rd(TAIL/'OUTPUT_SEAL.json')
for name in ['COHORT_OPPORTUNITY_MEMBERSHIP.json','CLOSED_POSITIVE_RANKING.json','BASELINE_DEFINITIONS.json','READOUT.md']:
 p=TAIL/name;assert sha(p)==tailseal.get(name,tailseal.get(str(p))),('TAIL_DRIFT',name);hashes[str(p)]=sha(p)
cohort=[x for x in rd(TAIL/'COHORT_OPPORTUNITY_MEMBERSHIP.json') if x['cohort']=='SEPT_STARTUP_SEED_OPEN_0923_0930']
top=[x for x in rd(TAIL/'CLOSED_POSITIVE_RANKING.json') if x['cohort']=='SEPT_STARTUP_SEED_OPEN_0923_0930' and x['in_top10pct_positive']]
assert len(cohort)==222 and len(top)==19
fixed={x['round_id']:x for x in cohort}
entries=rd(O/'FIXED_WINDOW_ENTRY_CLASSIFICATION.json');daily=rd(O/'DAILY_EVIDENCE.json');atom=rd(O/'MEMBER_DAILY.json');members=rd(O/'EVENT_MEMBERS.json')
assert len(entries)==222 and {x['round_id'] for x in entries}==set(fixed)
orders=rd(B/'ORDERS.json');seed={x['round_id']:x for x in orders if x['side']=='BUY_SEED'}
events=rd(B/'EVENT_REGISTRY.json')
primary={(x['sector51'],x['close_day']):x for x in daily if x['cohort']=='BIRTH_PRICE_KNOWN'}
for x in entries:
 ref=fixed[x['round_id']];s=seed[x['round_id']];d=primary[(x['sector51'],x['plan_day'])]
 assert s['event_id']==x['event_id']==d['event_id']
 assert ref['opportunity_key']==x['sid']+'|'+x['signal_day']
 assert ref['actual_seed_OPEN']==x['seed_day']
 x.update(opportunity_key=ref['opportunity_key'],original_frozen_cohort=ref['cohort'],event_birth_day=d['birth_day'],N_birth_price_known=d['N_fixed'],
  positive_count=d['positive_n'],profitable_advance_count=d['profitable_advance_n'],profitable_advance_unknown=d['profitable_advance_unknown'],event_return_median_exact=d['event_return_median_exact'],
  CP_receipt_count=d['CP_receipt_n'],CP_frontier_count=d['CP_frontier_advance_n'],
  later_ticket_survival='NOT_CHECKED_IN_THIS_FIXED_OPPORTUNITY_AUDIT',later_GATE_recovery='NOT_CHECKED_IN_THIS_FIXED_OPPORTUNITY_AUDIT',
  original_next_OPEN_classification_not_new_account_execution=True)
 assert x['G']==d['G']
for d in daily:
 scope={x['sid'] for x in members if x['event_id']==d['event_id'] and (d['cohort']=='ALL_FIXED' or x['in_'+d['cohort']])}
 aa=[x for x in atom if x['event_id']==d['event_id'] and x['close_day']==d['close_day'] and x['sid'] in scope]
 assert len(aa)==len(scope)==d['N_fixed']
 for fld in ['positive','advance','decline','profitable_advance','new_event_high','CP_receipt','CP_frontier_advance']:
  k=sum(x[fld]==1 for x in aa);u=sum(x[fld]==-1 for x in aa)
  assert k==d[fld+'_n'] and u==d[fld+'_unknown']
  g=-1 if not len(aa) else 1 if 2*k>len(aa) else 0 if 2*(k+u)<=len(aa) else -1
  assert g==d[fld+'_majority']
 assert d['G']==d['profitable_advance_majority']
 if d['event_return_known']==d['N_fixed']:assert math.isclose(float(np.median([x['event_return'] for x in aa])),d['event_return_median_exact'],rel_tol=1e-12,abs_tol=1e-12)
lookup={x['round_id']:x for x in entries}
toprows=[]
for t in top:
 x=lookup[t['round_id']]
 toprows.append(dict(frozen_positive_rank=t['positive_rank'],frozen_top10pct_label=True,label_for_evaluation_only_not_admission=True,**x,original_marked_net_pnl=t['marked_net_pnl']))
mature=[x for x in entries if x['phase']=='MATURE'];open924=[x for x in mature if x['seed_day']=='2024-09-24']
assert len(mature)==122 and len(open924)==28
group=defaultdict(list)
for x in mature:group[(x['sector51'],x['event_id'],x['event_birth_day'])].append(x)
sector=[]
for (sec,eid,birth),rows in sorted(group.items()):
 sector.append(dict(sector51=sec,event_id=eid,birth_day=birth,total=len(rows),T=sum(x['G']==1 for x in rows),F=sum(x['G']==0 for x in rows),U=sum(x['G']==-1 for x in rows),actual_OPEN_days=sorted({x['seed_day'] for x in rows}),original_plan_CLOSE_days=sorted({x['plan_day'] for x in rows})))
byday=[]
for day in sorted({x['seed_day'] for x in entries}):
 a=[x for x in entries if x['seed_day']==day]
 byday.append(dict(original_OPEN=day,all_rounds=len(a),EVENT_unmodified=sum(x['phase']=='EVENT' for x in a),MATURE_T=sum(x['phase']=='MATURE' and x['G']==1 for x in a),MATURE_F=sum(x['phase']=='MATURE' and x['G']==0 for x in a),MATURE_U=sum(x['phase']=='MATURE' and x['G']==-1 for x in a)))
summary=dict(frozen_total=222,EVENT_unmodified=100,MATURE_total=122,MATURE_T=sum(x['G']==1 for x in mature),MATURE_F=sum(x['G']==0 for x in mature),MATURE_U=sum(x['G']==-1 for x in mature),
 original_OPEN0924_MATURE=28,OPEN0924_T=sum(x['G']==1 for x in open924),OPEN0924_F=sum(x['G']==0 for x in open924),OPEN0924_U=sum(x['G']==-1 for x in open924),
 frozen_top19=19,top19_EVENT_unmodified=sum(x['phase']=='EVENT' for x in toprows),top19_MATURE_T=sum(x['phase']=='MATURE' and x['G']==1 for x in toprows),top19_MATURE_F=sum(x['phase']=='MATURE' and x['G']==0 for x in toprows),
 top19_WAIT_names=[x['name'] for x in toprows if x['decision']=='MARKET_PROGRESS_WAIT'],no_PnL_savings_or_portfolio_claim=True)
qa=rd(O/'QA.json');qa.update(dict(original_frozen_222_identity_set_exact=True,original_frozen_19_evaluation_members_exact=True,
 all_original_event_ids_and_births_matched=True,earliest_required_birth='2024-09-18',not_reanchored_to_window_start=True,
 independent_aggregate_rows=len(daily),original_formula_and_primary_cohort_unchanged=True,
 allowed_builder_changes=['output directory','fixed 40 sector date spans','local raw read extent covering original birth'],
 primary_price_missing_rows=sum(x['positive_unknown']>0 or x['advance_unknown']>0 for x in primary.values()),
 original_18_artifacts_and_seal_unchanged=True,original_tail_cohort_artifacts_unchanged=True,
 no_later_ticket_survival_or_reentry_claim=True,W_audit_same_left_boundary_caveat_as_original=True))
for path,h in hashes.items():assert sha(path)==h
for f in ['build_evidence.py','READOUT.md','OUTPUT_SEAL.json']:hashes[str(OLD/f)]=sha(OLD/f)
save('ALL_222_FIXED_OPPORTUNITIES',entries);save('MATURE_122_OPPORTUNITIES',mature);save('OPEN_0924_28_MATURE',open924);save('TOP19_FIXED_OPPORTUNITIES',toprows);save('SECTOR_EVENT_SUMMARY',sector);save('OPEN_DAY_SUMMARY',byday);save('SUMMARY',summary);save('QA',qa);save('SOURCE_HASHES',hashes)
def pct(v):return '未知' if v is None else f'{100*v:+.2f}%'
def status(x):return 'EVENT不改' if x['phase']=='EVENT' else {1:'T：继续原审查',0:'F：WAIT',-1:'U：暂停'}[x['G']]
lines=['# 全市场924固定机会检查：原G方向的主线机会成本','',
'## 结论先行','',
'**不能把“软件首EVENT及9/25的5个MATURE不延迟”推广为全市场924不延迟。** 沿完全相同的已封存G公式，固定222个原机会中，100个EVENT不改；122个MATURE有76个T、46个F/WAIT、0个U。',
'',
'尤其9/24 OPEN原28个MATURE：只有汽车整车5个T，房地产开发13个与证券保险10个均F/WAIT；9/23 OPEN的另23个证券MATURE也F/WAIT。原固定19个强正收益机会里，新华保险、大名城、浦东金桥、新城控股4个在原决策CLOSE被WAIT，另13个EVENT不改、2个MATURE通过。',
'',
'这是与用户“抓主线、不能为过滤反弹一味延迟924”直接相关的不利证据。机器人12/5盲区能被G等待，不足以抵消这一机会成本。本检查不支持宣称原G已经保住全市场924；**建议暂停直接冻结该方向，不因结果再改多数门槛、分母或回看天数。**',
'',
'这里的WAIT只表示原当晚不能把该票加入成熟新种子需求，不代表永久未参与或必然损失原轮全部盈利。没有追踪这46票后续原false取消/恢复，没有新账户重放，也没有把原PnL当作损失或节省。',
'',
'## 1. 事前固定身份与不变公式','',
'- 机会集合直接复用 mainline_tail_capture_baseline_v1/COHORT_OPPORTUNITY_MEMBERSHIP.json 中 SEPT_STARTUP_SEED_OPEN_0923_0930 的222条，原实际SEED OPEN 9/23—9/30。机会键是sid＋original_signal_date，不因任何潜在延迟换组。',
'- 19个强机会直接复用 CLOSED_POSITIVE_RANKING.json 同组既有 in_top10pct_positive 标记，没有重新按本次结果挑名单。这个事后盈利标签只用于机会成本评价，未参与G、行业成员、日期或分母计算。',
'- 全体原订单的event_id、birth_day逐项对齐；最早事件出生为9/18（证券），房地产出生9/19。原决策窗最早9/20；按原出生读本地价格，没有把出生改为9/20、9/23或9/24。',
'- G=出生可观察固定行业集合中，严格多数同股满足 C(t)>C(birth) 且 C(t)>C(t−1)。价格有效性、来源连续性、未知三值、严格多数和出生固定集合全与主研究一致。',
'- 只对原phase=MATURE的新SEED分类，EVENT按原规则不改；表里EVENT的原始G即使F，也不表示会挡EVENT。已有持仓ADD、退出及资金竞争均未修改。',
'- 本次读取40个行业、1,286只原名单股票，70个实际相关行业CLOSE×三集合=210行；每个待评估CLOSE只用当时及之前价格/原CP。当前分类和价格输入的非PIT局限与主报告相同。','',
'## 2. 全体原实际OPEN分解','',
'| 原实际OPEN | 总轮数 | EVENT不改 | MATURE T | MATURE F/WAIT | MATURE U |',
'|---|---:|---:|---:|---:|---:|']
for x in byday:lines.append(f"| {x['original_OPEN']} | {x['all_rounds']} | {x['EVENT_unmodified']} | {x['MATURE_T']} | {x['MATURE_F']} | {x['MATURE_U']} |")
lines+=['',
'因此当原市场9/24开盘大涨时，这个只读前一CLOSE的条件不会“看到9/24新收盘再补回9/24开盘”。9/25之后已通过的机会不能替9/23和9/24受影响机会辩护。',
'',
'## 3. 122个MATURE按行业/event汇总','',
'| 行业 | 原出生CLOSE | 原机会数 | T | F/WAIT | U | 原实际OPEN |',
'|---|---|---:|---:|---:|---:|---|']
for x in sector:lines.append(f"| {x['sector51']} | {x['birth_day']} | {x['total']} | {x['T']} | {x['F']} | {x['U']} | {', '.join(x['actual_OPEN_days'])} |")
lines+=['',
'### 9/24原28个MATURE为什么被分开','',
'三个行业都只能用9/23 CLOSE，而非9/24当日收盘：',
'| 行业 / 原出生 | 固定可观察N | 出生正收益数 | 同股今日继续推进数 | 出生收益中位 | 原9/24MATURE | G |',
'|---|---:|---:|---:|---:|---:|---|']
for sec in sorted({x['sector51'] for x in open924}):
 x=primary[(sec,'2024-09-23')];count=sum(r['sector51']==sec for r in open924)
 lines.append(f"| {sec} / {x['birth_day']} | {x['N_fixed']} | {x['positive_n']} | {x['profitable_advance_n']} | {pct(x['event_return_median_exact'])} | {count} | { {1:'T',0:'F',-1:'U'}[x['G']] } |")
lines+=['',
'房地产17/21已有出生后正收益、12/21当天上涨，但同一股票同时满足两项只有10/21，故F。不能为挽救这13笔而改成两个比例各自过半。证券43/51已有正价差却只有15/51继续推进，也为F。汽车11/21刚过严格多数，仍按原式T，不追加涨幅门槛。',
'',
'| 原9/24 MATURE股票 | sid / 原信号 | 行业 | 原决策CLOSE | G分类 |',
'|---|---|---|---|---|']
for x in open924:lines.append(f"| {x['name']} | {x['sid']} / {x['signal_day']} | {x['sector51']} | {x['plan_day']} | {status(x)} |")
lines+=['',
'## 4. 固定19个强机会完整清单','',
'下面保留原排名，只作既有评价名单的配对。所有行业分母仍是出生时可观察全成员，并非这19只股票构成的“赢家宽度”。',
'',
'| 原固定排名 | 股票 | 行业 | 原信号 | 原SEED OPEN | 原phase | 原计划CLOSE的G作用 |',
'|---:|---|---|---|---|---|---|']
for x in toprows:lines.append(f"| {x['frozen_positive_rank']} | {x['name']} / {x['sid']} | {x['sector51']} | {x['signal_day']} | {x['seed_day']} | {x['phase']} | {status(x)} |")
lines+=['',
'原软件三只EVENT保留，是正确但局部的陈述；原新华保险、大名城、浦东金桥、新城控股同样属于固定肥尾机会，不能因为它们是MATURE就从“924抓主线”的对照中移走。',
'',
'## 5. 原当晚分类与后来票状态必须分开','',
'- T只表示该因子允许继续原审查，不是候选可成交承诺；原F/CP、I、报价、容量、lot、费用、现金和排序仍需所在基准的完整检查。',
'- F表示INDUSTRY_PROGRESS_WAIT，不是永久取消。沿主报告合同保留原ticket/signal/event身份，并继续原已知false吸收取消、UNKNOWN暂停、每日source/factor/只上调I线检查；不能因行业随后转强自动复活已取消票。',
'- 本固定机会核查没有把46张未成交原票模拟到更晚日期，没有声称其恢复日、成交价或再入资格。机器行显式记录 later_ticket_survival/later_GATE_recovery=NOT_CHECKED_IN_THIS_FIXED_OPPORTUNITY_AUDIT。',
'- 若后续要评估实施代价，需要保持这222条原机会身份，对等待后真实可执行恢复、入场价/份额、后续ADD、供资与总账户闭环逐项核验。不能仅看76/122当晚通过率，也不能加减原盈利/亏损组金额来预测NAV。',
'',
'## 6. 验证、交付和限制','',
'- ALL_222_FIXED_OPPORTUNITIES：222条原固定身份、G与当晚指标；MATURE_122_OPPORTUNITIES：全部122逐个标T/F/U；OPEN_0924_28_MATURE：28个重点逐笔；TOP19_FIXED_OPPORTUNITIES：19个原封存强机会完整配对。',
'- SECTOR_EVENT_SUMMARY/OPEN_DAY_SUMMARY：行业事件与原OPEN汇总；DAILY_EVIDENCE/MEMBER_DAILY/EVENT_MEMBERS：三集合完整原子数据；SUMMARY/QA/SOURCE_HASHES/OUTPUT_SEAL：检查与追溯。',
'- 222身份、19评价标签、全部原event_id/birth_day精确匹配；210行行业集合聚合由成员原子值独立复核。原主报告18份封存文件和原tail cohort文件哈希不变。',
'- 没有修改公式、阈值、分母定义或策略，没有联网、新源、history或候选重放。原57日未重写，机器人附录结论也不被这个新结果覆盖。',
'- 已观察开发窗、非PIT行业映射/价格资料、有限样本与没有反事实账户的限制全部保留。','']
(O/'READOUT.md').write_text('\n'.join(lines))
assert all(sha(OLD/n)==h for n,h in oldseal.items())
save('OUTPUT_SEAL',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_SEAL.json'})
print(json.dumps(dict(summary=summary,qa=qa,readout_sha256=sha(O/'READOUT.md')),ensure_ascii=False))
