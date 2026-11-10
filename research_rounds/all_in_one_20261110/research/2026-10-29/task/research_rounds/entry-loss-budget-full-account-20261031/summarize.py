import wire as w
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import csv,json,gzip,time
from datetime import datetime
O=w.O;T=time.monotonic();Z=D(0)
def csvrows(p):return list(csv.DictReader(Path(p).open()))
def gz(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def save(p,x):w.K.save(p,x)
def export(p,x):w.K.export(p,x)
def dt(s):return datetime.fromisoformat(s)
def recovery(ds):
 peak=D(1000000);peakday=dt(ds[0]['at']);under=None;trough=None;troughv=None;longest=0;completed=0
 for d in ds:
  t=dt(d['at']);v=D(d['nav'])
  if v>=peak:
   if under is not None:longest=max(longest,(t-under).days);completed=max(completed,(t-trough).days)
   peak=v;peakday=t;under=trough=None;troughv=None
  else:
   if under is None:under=peakday;trough=t;troughv=v
   if v<troughv:trough=t;troughv=v
 current=(dt(ds[-1]['at'])-under).days if under else 0;longest=max(longest,current)
 return dict(longest_underwater_calendar_days=longest,longest_completed_trough_recovery_calendar_days=completed,current_underwater_calendar_days=current,current_unrecovered=bool(under))
matrix=[];structure=[];trials=[];casecycles=[];stockdiffs=[];transmission=[];actevents=[];unknown=[];reentries=[];proof=[]
for sec in ['TECH','DRUG']:
 for stage in ['off','on','prefix']:assert w.read(O/sec/stage/'TIMING.json')['status']=='complete'
 assert w.read(O/sec/'off/IDENTITY.json')['passed'] and w.read(O/sec/'prefix/IDENTITY.json')['passed'];assert w.read(O/sec/'on/analysis/accounting.json')['passed'];assert w.read(O/sec/'on/STRUCTURE_GATE.json')['passed']
 root=w.RR/('pvr-local-finite-capital-20261029/baseline' if sec=='TECH' else 'innovative-drug-local-recovery-20261028/S0');mode='I' if sec=='TECH' else 'ACT';on=O/sec/'on';base_summary=csvrows(root/'analysis/summary.csv');basecamps=csvrows(root/'analysis/campaigns.csv');newsummary=csvrows(on/'analysis/summary.csv');newcamps=csvrows(on/'analysis/campaigns.csv');dsa=gz(root/'accounts-v2/daily.jsonl.gz');dsb=gz(on/'accounts-v2/daily.jsonl.gz');dea=gz(root/'accounts-v2/decisions.jsonl.gz');deb=gz(on/'accounts-v2/decisions.jsonl.gz');bds={};bcp={};bdec={};bstocks={}
 for st in ['base','delay1']:
  aid=f'{mode}__S0_{st}';row=dict(next(r for r in base_summary if r['account']==aid));ds=[x for x in dsa if x['account']==aid];obj=w.read(root/'accounts-v2'/f'{aid}.json');bds[st]={x['at']:x for x in ds};bcp[st]={x['at']:x for x in obj['audit_log'] if x['kind']=='risk_checkpoint'};bdec[st]={x['at']:x for x in dea if x['account']==aid};caps=[c for c in basecamps if c['account']==aid];ss=defaultdict(lambda:Z)
  for c in caps:ss[c['symbol']]+=D(c['net_pnl'])
  bstocks[st]=dict(ss);row.update(sector=sec,policy='A',pressure=st,status='reference_full_off_exact',**recovery(ds));matrix.append(row)
 for row0 in newsummary:
  row=dict(row0);aid=row['account'];st=aid.rsplit('_',1)[-1];policy=aid.split('__')[1].split('_')[0];ds=[x for x in dsb if x['account']==aid];obj=w.read(on/'accounts-v2'/f'{aid}.json');logs=obj['audit_log'];caps=[c for c in newcamps if c['account']==aid];start={(r['sid'],dt(r['at'])):r for r in logs if r['kind']=='loss_start'};ends={r['cycle']:r for r in logs if r['kind']=='loss_end'};stock=defaultdict(lambda:Z);bygroup=defaultdict(list)
  for c in caps:
   rr=start[c['symbol'],dt(c['entry_at'])];c=dict(c,sector=sec,model=policy,pressure=st,group=rr['group'],entry_cycle=rr['cycle'],exit_reason=ends.get(rr['cycle'],{}).get('reason','still_open'));bygroup[rr['group']].append(c);trials.append(c);stock[c['symbol']]+=D(c['net_pnl'])
   if c['symbol'] in ['605118.SH','301486.SZ','688143.SH','300903.SZ','300814.SZ']:casecycles.append(c)
  for group,cc in bygroup.items():
   closed=sorted([c for c in cc if c['closed']=='True'],key=lambda x:x['exit_at']);running=low=Z
   for c in closed:running+=D(c['net_pnl']);low=min(low,running)
   structure.append(dict(sector=sec,account=aid,policy=policy,pressure=st,group=group,symbol=cc[0]['symbol'],name=cc[0]['name'],attempts=len(cc),closed=len(closed),net=sum((D(c['net_pnl']) for c in cc),Z),closed_running_min=low,negative_closed_total=sum((min(Z,D(c['net_pnl'])) for c in closed),Z),fees=sum((D(c['buy_fees'])+D(c['sell_fees']) for c in cc),Z),budget_exit_cycles=sum(c['exit_reason']=='loss_budget' for c in closed)))
  last={};entry_count=0
  for x in logs:
   if x['kind']=='loss_end':last[x['sid']]=x
   elif x['kind']=='loss_start' and x['sid'] in last:
    e=last[x['sid']]
    if e['reason']=='loss_budget':
     same=e['group']==x['group'];reentries.append(dict(sector=sec,account=aid,policy=policy,pressure=st,symbol=x['sid'],same_structure=same,previous_exit=e['at'],new_entry=x['at'],group=x['group'],previous_group=e['group'],decision=x['decision_at'],new_K=x['K']));entry_count+=int(same)
   elif x['kind']=='loss_checkpoint' and not x['known']:unknown.append(dict(sector=sec,account=aid,symbol=x['sid'],at=x['at'],cycle=x['cycle']))
  cp={x['at']:x for x in logs if x['kind']=='risk_checkpoint'};actdiff=[t for t in cp if cp[t]['on']!=bcp[st][t]['on']];de={x['at']:x for x in deb if x['account']==aid};firststate=next((d['at'] for d in ds if any(d[k]!=bds[st][d['at']][k] for k in ['positions','available','order_reserved','pending_buys','pending_sells'])),None);firstaccept=next((t for t in de if de[t]['accepted']!=bdec[st][t]['accepted']),None)
  transmission.append(dict(sector=sec,account=aid,policy=policy,pressure=st,first_state_difference=firststate,first_ACT_on_difference=actdiff[0] if actdiff else None,ACT_on_difference_days=len(actdiff),first_acceptance_difference=firstaccept,A_accept=bdec[st][firstaccept]['accepted'] if firstaccept else None,C_accept=de[firstaccept]['accepted'] if firstaccept else None,A_available=bds[st][firstaccept]['available'] if firstaccept else None,C_available=next(d['available'] for d in ds if d['at']==firstaccept) if firstaccept else None,A_occupancy=bdec[st][firstaccept]['occupancy'] if firstaccept else None,C_occupancy=de[firstaccept]['occupancy'] if firstaccept else None,C_rejected=de[firstaccept]['rejected'] if firstaccept else None,first_ACT_A=bcp[st][actdiff[0]] if actdiff else None,first_ACT_C=cp[actdiff[0]] if actdiff else None))
  for x in cp.values():
   if x.get('event') in ['pause','resume','recover']:actevents.append(dict(x,sector=sec,account=aid,model=policy,pressure=st))
  diffs={s:stock.get(s,Z)-bstocks[st].get(s,Z) for s in set(stock)|set(bstocks[st])};expected=(D(ds[-1]['nav'])-D(1000000))-(D(list(bds[st].values())[-1]['nav'])-D(1000000));res=sum(diffs.values(),Z)-expected;assert abs(res)<D('1e-12');proof.append(dict(account=aid,stock_difference_sum=sum(diffs.values(),Z),NAV_difference=expected,residual=res))
  for s,v in sorted(diffs.items(),key=lambda kv:-abs(kv[1])):stockdiffs.append(dict(sector=sec,account=aid,policy=policy,pressure=st,symbol=s,A_net=bstocks[st].get(s,Z),C_net=stock.get(s,Z),difference=v))
  worst=min((D(c['net_return']) for c in caps if c['closed']=='True'),default=Z);sg=[x for x in structure if x['account']==aid];worstgroup=min(sg,key=lambda g:g['closed_running_min']) if sg else None;events=Counter(x.get('event') for x in cp.values());row.update(sector=sec,policy=policy,pressure=st,status='full_run_accounting_and_prefix_validated',same_E0_reentry_after_budget=entry_count,budget_requests=sum(x['kind']=='loss_budget_request' for x in logs),budget_exits_completed=sum(x['kind']=='loss_end' and x['reason']=='loss_budget' for x in logs),worst_closed_cycle_return=worst,worst_structure_closed_cumulative=worstgroup['closed_running_min'] if worstgroup else Z,worst_structure=worstgroup['group'] if worstgroup else None,worst_structure_attempts=worstgroup['attempts'] if worstgroup else 0,ACT_events=dict(events),**recovery(ds));matrix.append(row)
export(O/'MATRIX_16.csv',matrix);export(O/'STRUCTURE_TRIALS.csv',structure);export(O/'ALL_CAMPAIGNS.csv',trials);export(O/'KEY_CASE_CYCLES.csv',casecycles);export(O/'STOCK_PNL_DIFFERENCE.csv',stockdiffs);export(O/'REENTRIES.csv',reentries);save(O/'TRANSMISSION.json',transmission);save(O/'ACT_EVENTS.json',actevents);save(O/'UNKNOWN.json',unknown);save(O/'STOCK_BRIDGE.json',dict(passed=True,rows=proof));save(O/'SUMMARY.json',dict(matrix=matrix,seconds=time.monotonic()-T,off_accounts_exact=4,challenger_accounts=12,prefix_accounts_exact=12,stock_bridge_max_residual=max(abs(r['residual']) for r in proof)));print('SUMMARY_COMPLETE',len(matrix),time.monotonic()-T)
