import sys
sys.path.insert(0,'/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/entry-loss-budget-full-account-20261031')
import wire as w
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
from types import SimpleNamespace
import csv,json,pandas as pd
O=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/entry-loss-budget-cost2-funnel-20261031');Z=D(0)
def rows(p):return list(csv.DictReader(Path(p).open()))
mm=rows(O/'MATRIX_8_COST2.csv');ss=[x for x in rows(O/'STRUCTURE_TRIALS.csv') if x['policy']!='A'];reference=[]
for sec,root,mode,prep in [('TECH',w.RR/'pvr-local-finite-capital-20261029/baseline','I',Path(w.read(w.RR/'pvr-act-comparison-20261027/input.json')['snapshot']['path'])),('DRUG',w.RR/'innovative-drug-local-recovery-20261028/S0','ACT',w.RR/'innovative-drug-sfw3-20261028/prepared')]:
 camps=rows(root/'analysis/campaigns.csv');holder=SimpleNamespace(facts=SimpleNamespace(f={}))
 for stress in ['cost2']:
  aid=f'{mode}__S0_{stress}';obj=w.read(root/'accounts-v2'/f'{aid}.json');buys={(x['receipt']['security_id'],x['receipt']['at']):x for x in obj['audit_log'] if x['kind']=='fill' and x['receipt']['side']=='buy'};contracts={x['order_id']:x for x in obj['audit_log'] if x['kind']=='entry_contract'};by=defaultdict(list);cs=[c for c in camps if c['account']==aid]
  for c in cs:
   s=c['symbol']
   if s not in holder.facts.f:holder.facts.f[s]=pd.read_parquet(prep/'facts'/f'{s}.parquet')
   buy=buys[s,c['entry_at']];co=contracts[buy['order_id']];ctx=w.context(holder,s, __import__('datetime').datetime.fromisoformat(co['decision_at']));group=ctx['structure_id'] or f'{s}|reference_unknown|{c["entry_at"]}';by[group].append(c)
  rr=[]
  for g,cc in by.items():
   closed=sorted([c for c in cc if c['closed']=='True'],key=lambda x:x['exit_at']);net=low=Z
   for c in closed:net+=D(c['net_pnl']);low=min(low,net)
   rr.append(dict(sector=sec,account=aid,policy='A',pressure=stress,group=g,symbol=cc[0]['symbol'],name=cc[0]['name'],attempts=len(cc),closed=len(closed),net=sum((D(c['net_pnl']) for c in cc),Z),closed_running_min=low,negative_closed_total=sum((min(Z,D(c['net_pnl'])) for c in closed),Z),fees=sum((D(c['buy_fees'])+D(c['sell_fees']) for c in cc),Z),budget_exit_cycles=0))
  ss.extend(rr);worst=min(rr,key=lambda x:x['closed_running_min']);row=next(x for x in mm if x['sector']==sec and x['pressure']==stress and x['policy']=='A');row.update(worst_closed_cycle_return=min((D(c['net_return']) for c in cs if c['closed']=='True'),default=Z),worst_structure_closed_cumulative=worst['closed_running_min'],worst_structure=worst['group'],worst_structure_attempts=worst['attempts']);reference.append(dict(sector=sec,pressure=stress,groups=len(rr),cycles=len(cs),net=sum((r['net'] for r in rr),Z)))
proof=w.read(O/'NO_EXPOSURE_IDENTITY.json');equalids={x['account'] for x in proof['accounts']}
for row in mm:
 if row['account'] in equalids:row['status']='actually_run_and_legacy_event_identical_to_A'
w.K.export(O/'MATRIX_8_COST2.csv',mm);w.K.export(O/'STRUCTURE_TRIALS.csv',ss);su=w.read(O/'SUMMARY.json');su['matrix']=mm;su['reference_structure_checks']=reference;w.K.save(O/'SUMMARY.json',su);print('reference structure accounting added; zero-exposure statuses explicit')
