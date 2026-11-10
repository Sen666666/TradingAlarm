"""Assemble read-only saved-path findings. No strategy/history/network."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter, defaultdict
import json,csv,hashlib
O=Path(__file__).resolve().parent;R=O.parent;B=R/'mainline_m7_cash_batch_design_v6/once_20260630'
load=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs=load(O/'SOURCE_HASHES.json');basehash=load(B/'OUTPUT_HASHES.json')
def source(n):
 p=B/(n+'.json');assert sha(p)==basehash[p.name];inputs[str(p)]=sha(p);return load(p)
def write(n,x):
 (O/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
 if isinstance(x,list) and x:
  fields=list(dict.fromkeys(k for r in x for k in r))
  with (O/(n+'.csv')).open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
   for r in x:w.writerow({k:json.dumps(v,ensure_ascii=False,default=str) if isinstance(v,(list,dict)) else v for k,v in r.items()})
S=load(O/'FIXED_COHORT_GROUPS.json');DAYS=load(O/'DAILY_OPEN_FLOWS.json');ROUNDS=load(O/'FIXED_ROUND_CLASSIFICATION.json');DONORS=load(O/'DONOR_LOT_OBSERVATIONS.json');GIVE=load(O/'ACTUAL_HEALTHY_DONOR_GIVEBACKS.json')
orders=source('ORDERS');sectors=source('SECTOR_DAILY');eventlog=source('EVENT_LOG');eventreg=source('EVENT_REGISTRY');refs=source('REFERENCE_REQUESTS');eventplans=source('EVENT_REQUEST_PLANS');confirm=source('INFORMATION_CONFIRMATIONS');cps=source('CP_EVENTS');fund=source('FUNDING_REQUESTS');trans=source('TRANSFERS')
sm=lambda xs,k:sum((D(x[k]) for x in xs),D(0))
fmt=lambda x:f'{D(x):,.2f}'
byday={x['open_day']:x for x in DAYS}
robot=[r for r in ROUNDS if r['actual_seed_OPEN']=='2024-12-05'];assert len(robot)==10
robotids={r['round_id'] for r in robot};rorders=[o for o in orders if o['round_id'] in robotids]
compact=[]
for r in robot:
 oo=[x for x in rorders if x['round_id']==r['round_id']];bo=next(x for x in oo if x['side']=='BUY_SEED');adds=[x for x in oo if x['side']=='BUY_ADD'];rr=[x for x in confirm if x['round_id']==r['round_id']]
 compact.append(dict(sid=r['sid'],name=r['name'],sector51=r['sector51'],round_id=r['round_id'],birth_type=r['birth_type'],signal_day=r['original_signal_date'],event_id=bo['event_id'],event_birth_day=eventreg[bo['event_id']]['birth_day'],actual_seed_OPEN=r['actual_seed_OPEN'],seed_buy_cost=r['seed_all_in'],ADD_count=len(adds),ADD_buy_cost=-sm(adds,'cash_delta'),ADD_orders=adds,actual_postseed_information_records=rr,final_exit_day=r['exit_day'],exit_reasons=r['exit_reasons'],whole_round_PnL=r['marked_net_pnl'],all_orders=oo))
write('ROBOTICS_1205_TEN_ROUNDS',compact)
robotcase=dict(day_flow=byday['2024-12-05'],rounds=compact,totals=dict(seed_cost=sm(compact,'seed_buy_cost'),later_ADD_cost=sm(compact,'ADD_buy_cost'),later_ADD_orders=sum(x['ADD_count'] for x in compact),whole_round_PnL=sm(compact,'whole_round_PnL')),sector_days=[x for x in sectors if x['sector51']=='自动化与机器人' and '2024-12-02'<=x['day']<='2024-12-05'],event_at_1204_CLOSE=[x for x in eventlog if x['event_id']=='自动化与机器人|2024-12-03' and x['day']<='2024-12-04'],reference_requests_1204_CLOSE=[x for x in refs if x['day']=='2024-12-04'],actual_requests_1205_OPEN=[x for x in fund if x['day']=='2024-12-05'],transfer_logs=[x for x in trans if x['day'] in ['2024-12-04','2024-12-05'] and x['event'] in ['DEMAND_PLAN','TRANSFER_CASH','RECEIVER_FUNDING']],proof='At the SAME baseline snapshot full candidate has zero optional donor sells, and no ADD/EVENT requests exist. Thus y_H=0<=y0_H and qA constraints are empty; this rule cannot force seed retreat on this snapshot. No claim about altered account history.',not_strategy_replay=True)
assert len(robotcase['reference_requests_1204_CLOSE'])==139
assert not [x for x in robotcase['reference_requests_1204_CLOSE'] if x['kind']=='ADD' or x['allocation_phase']=='EVENT']
write('ROBOTICS_1205_BLINDSPOT',robotcase)
# Daily group statistics and qualified subcases. Counts of buying days exclude zero cost.
aggregates=[]
for window,pred in [('FULL',lambda d:True),('LATE_1107_0120',lambda d:d['open_day']>='2024-11-07')]:
 for group in ['ALL','NO_OPTIONAL_FUNDING','FUNDING_NO_H','H_FUNDING_WITH_NEW_MATURE','H_FUNDING_WITHOUT_NEW_MATURE']:
  ds=[d for d in DAYS if pred(d) and (group=='ALL' or d['observed_day_group']==group)];ae=[d for d in ds if D(d['actual_ADD_EVENT_buy_cost'])>0]
  aggregates.append(dict(window=window,group=group,days=len(ds),MATURE_buy_count=sum(d['MATURE_SEED_count'] for d in ds),MATURE_buy_cost=sm(ds,'MATURE_SEED_buy_cost'),ADD_buy_count=sum(d['ADD_count'] for d in ds),ADD_buy_cost=sm(ds,'ADD_buy_cost'),EVENT_buy_count=sum(d['EVENT_SEED_count'] for d in ds),EVENT_buy_cost=sm(ds,'EVENT_SEED_buy_cost'),RESIDUAL_buy_count=sum(d['RESIDUAL_SEED_count'] for d in ds),RESIDUAL_buy_cost=sm(ds,'RESIDUAL_SEED_buy_cost'),funding_net=sm(ds,'funding_net'),H_common_OPEN_funding_net=sm(ds,'H_OPEN_funding_net'),days_with_actual_ADD_EVENT=len(ae),days_cash_enough_for_observed_ADD_EVENT=sum(d['cash_alone_covers_actual_ADD_EVENT'] for d in ae),days_cash_not_enough_for_observed_ADD_EVENT=sum(not d['cash_alone_covers_actual_ADD_EVENT'] for d in ae)))
write('DAILY_GROUP_TOTALS',aggregates)
blind=[]
for d in DAYS:
 if not d.get('same_snapshot_no_financing_and_no_A_requests'):continue
 actual_ref=[x for x in refs if x['day']==d['previous_close']]
 assert not [x for x in actual_ref if x['kind']=='ADD' or x.get('allocation_phase')=='EVENT']
 rr=[r for r in ROUNDS if r['actual_seed_OPEN']==d['open_day'] and r['seed_phase']=='MATURE']
 blind.append(dict(day=d,matched_fixed_rounds=rr,total_matched_seed_cost=sm(rr,'seed_all_in'),whole_round_PnL=sm(rr,'marked_net_pnl'),all_CLOSE_request_counts=dict(Counter(x['allocation_phase'] for x in actual_ref)),mechanism_constraints_empty_at_same_snapshot=True))
write('NO_FINANCING_NO_A_SNAPSHOTS',blind)
# Explicit real-path givebacks, preserving actual lot path and excluding any future buys.
casekeys=[('2024-11-14','688778.SH'),('2024-12-12','002315.SZ'),('2024-11-14','002709.SZ'),('2024-10-08','002244.SZ')]
givecases=[]
for day,sid in casekeys:
 g=next(x for x in GIVE if x['open_day']==day and x['sid']==sid and x['strict_no_future_buy_remaining_position']);d=next(x for x in DONORS if x['order_seq']==g['actual_donor_order_seq'])
 givecases.append(dict(summary=g,common_OPEN_H_snapshot=d,whole_round_orders=[x for x in orders if x['round_id']==g['round_id']],interpretation='Actual remaining position later gave back after healthy profitable OPEN; this is not a counterfactual return from preserving the financed shares.'))
write('HEALTHY_OLD_ROUND_GIVEBACK_CASES',givecases)
# Both-time and common-OPEN distinctions are explicit and same-day first confirmations are not borrowed.
qa=load(O/'QA.json')
method={
 'primary_H':'One common OPEN snapshot after mandatory exits, dividends/accrual, and real info_open, before any optional financing or buys. Same-round optional sale proceeds and fragmented fees cannot alter primary H.',
 'H_strict_evidence':'Post-SEED CREATED_AFTER_SEED receipt and same cp_id actual INFORMATION_CONFIRMED; round liquidation net>0; current I and effective lot protection intact; original source/factor bridge/state known, no exit lock. Uses isinstance(x,(bool,np.bool_)). Never substitutes M3/M=1.',
 'same_day_confirmation':'60 newly confirmed OPEN donor orders in full sample. One other OPEN-only H (Jilin Aodong 11/11) moved from negative CLOSE liquidation to positive OPEN. 174 satisfy carried CLOSE-and-OPEN design helper; total common-OPEN H235.',
 'no_H_caveat':'No observed H funding only removes the supply-side observed intersection; qA shadow guarantee may still bind. It is NOT a proof that the entire proposal cannot act. No-financing AND zero original ADD/EVENT requests is the stronger same-snapshot empty-constraint example.',
 'coverage':'Only baseline realized donor/new-seed same-day intersections. No shadow run, no marginal causal dollar attribution, no claims of tickets blocked or money saved, and no strategy PnL.',
 'cash':'For every day, prior-CLOSE cash plus actual non-financing sell proceeds equals common-OPEN pre-funding cash; plus funding minus all buys equals saved OPEN cash; plus saved equity payments equals CLOSE cash. Reserve recovered exactly from two saved OPEN cash fields. Enough for actual ADD/EVENT quantities is not proof of no-N shadow max quantities.',
 'cohort':'Baseline round identities fixed by original first SEED OPEN. 924=09/23-09/30 all sectors; PV=10/23-10/29 光伏风电设备; late=11/07-01/20. No identity re-selection. MATURE479+EVENT473+RESIDUAL2=954.',
 'PnL':'Actual whole-round trade cashflows+dividend entitlements+cutoff mark, including later ADD/funding/exits. 130 late rounds still open at cutoff, so their final realized PnL is unknown. All reported cutoff marks are known.',
 'bounds':'Only actual sold donors were scanned, not all potential donors or counterfactual eligibility. No donor unknown in scanned819; that does not prove all no-N shadow inputs complete.',
 'scope':'M7 single-factor only. V11 is not run or overlaid. Existing V11v2 later segment benefit509.26 is not used as evidence of this rule. Local-only, no history/strategy import/new candidate/internet/CNINFO.'}
write('METHOD_AND_LIMITATIONS',method)
labels={'NO_OPTIONAL_FUNDING':'无可选融资','FUNDING_NO_H':'融资但无H','H_FUNDING_WITH_NEW_MATURE':'H供资+新MATURE同日','H_FUNDING_WITHOUT_NEW_MATURE':'H供资但无新MATURE','ALL':'合计'}
lines=['# 赢家供资提案：真实账户作用域，而非挡票结果','',
'仅封存M7实际路径，2024-09-02至2025-01-20。没有运行策略/history/影子，没有新候选、联网或改原封存。M7+单因素是唯一对照；不叠V11。','',
'## 结论','',
'晚期954个新round的SEED本金808.98万元。原MATURE479轮、417.11万元；其中323轮、286.81万元与真实H融资同日，156轮、130.29万元没有这个供给端交集。323占954轮的33.86%、占全部SEED买款35.45%，是已观察的宽松交集，不是可挡323轮。',
'晚期EVENT/RESIDUAL为475轮、391.88万元，原全轮-63,596.34元，不是提案直接退让的新MATURE对象。提案保留合法ADD，其失败不由该规则自动解决。',
'无H不能直接说整个提案无效：另一个qA数量约束可能仍生效。12/5机器人是更强反例：无融资、ADD/EVENT请求也为空，两个不等式在同一账户快照都无从迫使10笔MATURE退让，原SEED成本105,683.35元，后续全轮合亏4,180.03元。',
'保护当时盈利且结构未破也不是只赚不赔：厦钨新能、焦点科技等留下的真实仓位随后回吐；924和光伏的同日交集中又有大量真正盈利新票。','',
'## 主H口径及核验','',
'主H固定在共同OPEN：原强制退出、股息权益及真实info_open之后，任何可选融资和买入之前。819笔真实融资lot中235笔H；174笔同时满足前晚CLOSE与OPEN，60笔在当日OPEN才首次真实确认，另1笔吉林敖东11/11从CLOSE净亏转为OPEN净利。逐单实际H作为旁列，26笔净利数值因此前同轮卖出/费用分拆不同，但资格差异为0。',
'逐lot用了真实post-SEED receipt→同cp_id INFORMATION_CONFIRMED、整轮当时清算净利、当前I/抬升后的有效CP保护、来源/因子桥、退出锁。没有把M3/M=1当H。所有819笔已核，未知0；这不等于潜在影子候选池无未知。22层光伏和9/25原6层双时点H均逐项回对旧设计产物。',
'9/25共同OPEN H供资28笔279,770.90元，包含当日首次确认22笔；旧设计9/25的6笔99,880.59元只是“前晚已确认”的子集，不能继续当全体OPEN H。','',
'## 晚期954轮按首次SEED日固定分组','',
'下列PnL是原整轮至共同终点的实际结果，包含后来ADD、融资和退出；130轮仍持仓，属于截止标记而非已实现。现金共池，任何一行都不是供资逐元归因。','',
'|原阶段|首次SEED日资金组|轮数|SEED成本|全轮买款含ADD|全轮PnL|期末未平|','|---|---|---:|---:|---:|---:|---:|']
for phase in ['ALL','MATURE','EVENT_OR_RESIDUAL']:
 for s in S:
  if s['cohort']=='NEW_SEED_OPEN_FROM_1107' and s['original_seed_phase']==phase and s['rounds']:
   lines.append(f"|{phase}|{labels[s['observed_day_group']]}|{s['rounds']}|{fmt(s['seed_buy_cost'])}|{fmt(s['all_round_buy_cost'])}|{fmt(s['whole_round_PnL_at_common_cutoff'])}|{s['open_at_cutoff']}|")
lines+=['','H+MATURE混合日的323个原MATURE里也有69个截止正收益轮，合+31,335.95元；净额-90,166.87不是可以兑现的节省。1/20新增70个MATURE仍全在终点持仓，不能拿其短期标记当最终失败。','',
'## 每日真实资金与现金','',
'93日逐日表含MATURESEED、ADD、EVENT、RESIDUAL笔数/买款，融资金额、两套H、共同OPEN现金/储备及原CLOSE计划。晚期52日中41日无融资、1日融资无H、9日H+MATURE、1日H但无MATURE。晚期总融资4,659,557.47元，H部分1,288,130.26元。','',
'所有93日现金双向闭合通过。晚期有真实ADD/EVENT买款的30日，22日原融资前现金扣保存储备足够支付其实际数量，8日不足；9个H+MATURE混合日中3日足够、6日不足。这只是观察量比较，不能说不足的H融资都是新SEED造成，也不能把足够说成删N影子已求解。','',
'## 无H现金扩张与强反例','',
'12/3无融资买41个MATURE，340,244.39元，原轮合-10,019.08元；12/27无融资买23个MATURE，174,382.25元，原轮合-5,598.45元。这些是供给端盲区，因仍有A请求，不把它们称为整个双约束必然不作用。',
'12/5是完整的同快照空约束案例。12/4 CLOSE全139个REFERENCE_REQUESTS仅10 MATURE PASS+129 RESIDUAL EVENT_CAP，没有ADD/EVENT。DEMAND_PLAN只含10 MATURE，计划106,115.11元、donor0。12/5原储备后现金725,759.61元，实际10笔105,683.35元且融资0：full候选yH=0≤任何非负y0，qA为空；因此该规则不能在该快照逼退这些新票。不是宣称改动之前历史后12/5一定仍同账户。',
'行业均自动化与机器人，event出生12/3、原信号12/3且A，12/5实际MATURESEED。12/3行业M0；12/4 CLOSE M1/Q1/S1/F0、E2.058496862、M_streak1、n16/K28/U3、真实已确认股票0/历史ADD0。12/4 OPEN该出生事件刚成交3个INITIAL EVENT种子24,706.74元，翌日MATURE扩张无需共享风险池或后见标签即可发生。','',
'|sid/名称|SEED成本|后来ADD笔数/成本|最后退出|全轮PnL|','|---|---:|---:|---|---:|']
for r in compact:lines.append(f"|{r['sid']} {r['name']}|{fmt(r['seed_buy_cost'])}|{r['ADD_count']} / {fmt(r['ADD_buy_cost'])}|{r['final_exit_day']}|{fmt(r['whole_round_PnL'])}|")
lines+=['',f"10轮后来6笔ADD共{fmt(robotcase['totals']['later_ADD_cost'])}元，合计亏损包含这些ADD，不是10.57万元SEED层单独损益。11/15另1个无融资且无A的同类空约束案例，后来全轮+245.59元，证明空约束也会留下盈利票。",'',
'## 盈利旧仓回吐：实际路径反例','',
'以下在H时点确实post-SEED真实确认、整轮净利正、该lot保护未破；融资部分后仍余仓，且以后没有新买入。不模拟保留已卖部分，不把全轮最终差当成规则反事实收益。','',
'|H时点/股票|共同OPEN整轮清算净利|实际融资净额|该笔后剩余股数|原最终全轮PnL|最终退出|','|---|---:|---:|---:|---:|---|']
for c in givecases:
 g=c['summary'];d=c['common_OPEN_H_snapshot'];lines.append(f"|{g['open_day']} {g['sid']} {g['name']}|{fmt(d['round_liquidation_net_common_prefunding_OPEN'])}|{fmt(g['actual_sold_net'])}|{g['round_qty_after_sale']}|{fmt(g['baseline_final_round_PnL'])}|{g['exit_day']}|")
lines+=['','厦钨新能11/14的正净利2,867.11后来变全轮-3,535.04；焦点科技12/12正204.41后来全轮-2,329.03。它们不是“最终是赢家”证明；保留旧健康仓存在回吐风险，亦不能由这些原路径差值推出保留的反事实必亏。','',
'## 924与光伏固定窗口：机会成本','',
'沿原固定身份：924窗口=9/23—9/30首次SEED，光伏=光伏风电设备10/23—10/29首次SEED，不重新挑赢家。','',
'|固定组/阶段|首次SEED日资金组|轮数|SEED成本|原全轮PnL|正轮数/正PnL|','|---|---|---:|---:|---:|---:|']
for s in S:
 if s['cohort']!='NEW_SEED_OPEN_FROM_1107' and s['original_seed_phase'] in ['ALL','MATURE'] and s['rounds']:
  lines.append(f"|{s['cohort']}/{s['original_seed_phase']}|{labels[s['observed_day_group']]}|{s['rounds']}|{fmt(s['seed_buy_cost'])}|{fmt(s['whole_round_PnL_at_common_cutoff'])}|{s['positive_rounds']} / {fmt(s['positive_whole_round_PnL'])}|")
lines+=['','924固定MATURE中与H同日71轮，原全轮+36,641.99元；59个正轮合+47,982.92元。今世缘9/25新MATURE全轮+5,200.51，不能先判该退。9/24本日28笔MATURE融资0，原本金212,746.87，不加等待并不等于9/25以后无代价。',
'光伏固定MATURE31轮里30轮与H融资同日，原全轮+35,358.06元。包括聚和+21,655.88、禾望+10,845.52、协鑫+9,410.52、钧达+9,169.43；这些新种子也可能进入退让集合。规则不应只陈列后来的证券白酒亏损而隐藏这面。','',
'## 文件及严格限制','',
'- DAILY_OPEN_FLOWS.{json,csv}：93日真实买卖现金、主H、旧双时点H、逐单H旁列。',
'- DONOR_LOT_OBSERVATIONS.{json,csv}：819笔来源、CP证明、当前保护、共同及逐单净利、真实卖款。',
'- FIXED_ROUND_CLASSIFICATION / FIXED_COHORT_GROUPS：固定1210个入组身份、三个窗口分层（晚期954+924222+光伏34）。',
'- ROBOTICS_1205_BLINDSPOT / ROBOTICS_1205_TEN_ROUNDS：强盲区完整请求、事件、行业、10轮及后来ADD。',
'- HEALTHY_OLD_ROUND_GIVEBACK_CASES / ACTUAL_HEALTHY_DONOR_GIVEBACKS：回吐反例与全量实际路径诊断。',
'- METHOD_AND_LIMITATIONS / QA / SOURCE_HASHES / ARTIFACT_SEAL：口径、逐项核验、输入与产物哈希。',
'',
'本研究只量化现提案作用域，不发明新限制。没有影子就没有“被挡多少票/可省多少钱/策略改进多少”的答案。反例说明它不是假主线通用过滤器；宽松交集也不足以替代对已有合法ADD、现金充裕的新MATURE和真正fat-tail机会的分别检验。']
(O/'READOUT.md').write_text('\n'.join(lines)+'\n')
for p,h in inputs.items():assert sha(Path(p))==h,('INPUT_CHANGED',p)
write('SOURCE_HASHES',inputs)
write('ARTIFACT_SEAL',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='ARTIFACT_SEAL.json'})
print(json.dumps(dict(directory=str(O),files=len(list(O.iterdir())),robot_totals=robotcase['totals'],late_daily=next(x for x in aggregates if x['window']=='LATE_1107_0120' and x['group']=='ALL'),readout_sha=sha(O/'READOUT.md')),ensure_ascii=False,default=str))
